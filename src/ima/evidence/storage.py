"""Evidence storage abstraction with a local filesystem development adapter."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Protocol

from ima.config import settings
from ima.evidence.schemas import StoredArtifact


class EvidenceStorage(Protocol):
    """Protocol for persisting evidence artifacts behind a stable URI scheme."""

    async def put_json(self, key: str, payload: dict[str, object]) -> StoredArtifact:
        """Persist one JSON artifact and return its storage metadata."""

    async def put_text(self, key: str, payload: str, content_type: str) -> StoredArtifact:
        """Persist one text artifact and return its storage metadata."""

    async def put_bytes(self, key: str, payload: bytes, content_type: str) -> StoredArtifact:
        """Persist one binary artifact and return its storage metadata."""


class LocalEvidenceStorage:
    """Local filesystem-backed adapter for evidence artifacts during development."""

    def __init__(self, root: Path | None = None, bucket: str | None = None) -> None:
        """Create the local adapter with a configurable root and bucket label."""

        self.root = root or Path(settings.evidence_storage_root)
        self.bucket = bucket or settings.evidence_storage_bucket

    async def put_json(self, key: str, payload: dict[str, object]) -> StoredArtifact:
        """Write one JSON artifact under the configured local evidence root."""

        serialized = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)
        return await self.put_text(key, serialized, "application/json")

    async def put_text(self, key: str, payload: str, content_type: str) -> StoredArtifact:
        """Write one text artifact under the configured local evidence root."""

        target_path = self.root / key
        await asyncio.to_thread(target_path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(target_path.write_text, payload, encoding="utf-8")
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return StoredArtifact(
            storage_key=key,
            source_uri=f"evidence://{self.bucket}/{key}",
            content_type=content_type,
            byte_size=len(payload.encode("utf-8")),
            sha256=digest,
            local_path=str(target_path.resolve()),
        )

    async def put_bytes(self, key: str, payload: bytes, content_type: str) -> StoredArtifact:
        """Write one binary artifact under the configured local evidence root."""

        target_path = self.root / key
        await asyncio.to_thread(target_path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(target_path.write_bytes, payload)
        digest = hashlib.sha256(payload).hexdigest()
        return StoredArtifact(
            storage_key=key,
            source_uri=f"evidence://{self.bucket}/{key}",
            content_type=content_type,
            byte_size=len(payload),
            sha256=digest,
            local_path=str(target_path.resolve()),
        )
