"""Tests for creator CLI parsing helpers."""

from __future__ import annotations

from datetime import UTC

import pytest
import typer

from ima.cli.run_agent import _parse_captured_at


def test_parse_captured_at_supports_iso_offset() -> None:
    """ISO timestamps with offsets should parse for snapshot recording."""

    parsed = _parse_captured_at("2026-03-15T10:00:00+00:00")

    assert parsed is not None
    assert parsed.tzinfo == UTC
    assert parsed.isoformat() == "2026-03-15T10:00:00+00:00"


def test_parse_captured_at_rejects_invalid_values() -> None:
    """Invalid timestamps should surface a Typer-friendly parameter error."""

    with pytest.raises(typer.BadParameter):
        _parse_captured_at("not-a-date")
