"""Creator growth tracking and heuristic scoring services."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ima.creators.schemas import CreatorGrowthSnapshotInput, CreatorScoreResult
from ima.db.models import Creator, CreatorContent, CreatorMetricSnapshot
from ima.logging import get_logger

logger = get_logger(__name__)


class CreatorScoringService:
    """Initial scoring logic for week 2 creator qualification."""

    def __init__(self, session: AsyncSession) -> None:
        """Create a scoring service bound to one async DB session."""

        self.session = session

    async def record_snapshot(self, payload: CreatorGrowthSnapshotInput) -> CreatorMetricSnapshot:
        """Persist a new creator metric snapshot."""

        snapshot = CreatorMetricSnapshot(
            creator_id=UUID(payload.creator_id),
            captured_at=payload.captured_at,
            follower_count=payload.follower_count,
            average_views_30d=payload.average_views_30d,
            average_likes_30d=payload.average_likes_30d,
            average_comments_30d=payload.average_comments_30d,
            engagement_rate_30d=payload.engagement_rate_30d,
            source=payload.source,
        )
        self.session.add(snapshot)
        await self.session.flush()
        logger.info(
            "creator_growth_snapshot_recorded",
            creator_id=payload.creator_id,
            source=payload.source,
        )
        return snapshot

    async def score_creator(self, creator_id: str) -> CreatorScoreResult:
        """Compute and persist the initial creator score set."""

        creator_uuid = UUID(creator_id)
        creator = await self.session.get(Creator, creator_uuid)
        if creator is None:
            raise ValueError(f"Creator {creator_id} wurde nicht gefunden.")

        snapshots = list(
            (
                await self.session.scalars(
                    select(CreatorMetricSnapshot)
                    .where(CreatorMetricSnapshot.creator_id == creator_uuid)
                    .order_by(CreatorMetricSnapshot.captured_at.asc())
                )
            ).all()
        )
        content_items = list(
            (
                await self.session.scalars(
                    select(CreatorContent).where(CreatorContent.creator_id == creator_uuid)
                )
            ).all()
        )

        growth_score = self._calculate_growth_score(creator, snapshots)
        commercial_readiness = self._calculate_commercial_readiness(creator, content_items)
        fraud_risk = self._calculate_fraud_risk(creator, snapshots, content_items)
        evidence_coverage = self._calculate_evidence_coverage(creator, content_items)
        is_qualified, reasons = self._qualification_decision(
            creator=creator,
            growth_score=growth_score,
            commercial_readiness_score=commercial_readiness,
            fraud_risk_score=fraud_risk,
            evidence_coverage_score=evidence_coverage,
        )

        creator.growth_score = growth_score
        creator.commercial_readiness_score = commercial_readiness
        creator.fraud_risk_score = fraud_risk
        creator.evidence_coverage_score = evidence_coverage
        creator.is_qualified = is_qualified
        creator.last_seen_at = datetime.now(UTC)
        await self.session.flush()

        logger.info(
            "creator_scored",
            creator_id=str(creator.id),
            growth_score=growth_score,
            commercial_readiness_score=commercial_readiness,
            fraud_risk_score=fraud_risk,
            evidence_coverage_score=evidence_coverage,
            is_qualified=is_qualified,
        )

        return CreatorScoreResult(
            creator_id=str(creator.id),
            growth_score=growth_score,
            commercial_readiness_score=commercial_readiness,
            fraud_risk_score=fraud_risk,
            evidence_coverage_score=evidence_coverage,
            is_qualified=is_qualified,
            qualification_reasons=reasons,
        )

    async def score_creator_by_handle(self, platform: str, handle: str) -> CreatorScoreResult:
        """Load a creator by platform and handle before scoring."""

        creator = await self.session.scalar(
            select(Creator).where(Creator.platform == platform, Creator.handle == handle)
        )
        if creator is None:
            raise ValueError(f"Creator {platform}/{handle} wurde nicht gefunden.")
        return await self.score_creator(str(creator.id))

    def _calculate_growth_score(
        self,
        creator: Creator,
        snapshots: list[CreatorMetricSnapshot],
    ) -> int:
        """Score growth momentum from historical snapshots instead of absolute size."""

        valid = sorted(
            [snapshot for snapshot in snapshots if snapshot.follower_count is not None],
            key=lambda snapshot: snapshot.captured_at,
        )
        if len(valid) < 2:
            return 50

        oldest = valid[0].follower_count or 0
        newest = valid[-1].follower_count or 0
        if oldest <= 0:
            return 50

        growth_ratio = (newest - oldest) / oldest
        score = 20
        if growth_ratio >= 0.30:
            score = 90
        elif growth_ratio >= 0.20:
            score = 80
        elif growth_ratio >= 0.10:
            score = 70
        elif growth_ratio >= 0.03:
            score = 60
        elif growth_ratio >= -0.03:
            score = 50
        elif growth_ratio >= -0.10:
            score = 35

        recent_views = valid[-1].average_views_30d
        if creator.follower_count and recent_views:
            view_ratio = recent_views / max(creator.follower_count, 1)
            if view_ratio >= 0.08:
                score = min(score + 5, 100)
        return score

    def _calculate_commercial_readiness(
        self,
        creator: Creator,
        content_items: list[CreatorContent],
    ) -> int:
        """Estimate how prepared a creator looks for sponsorship outreach."""

        score = 25
        if creator.bio:
            score += 15
        if creator.profile_url:
            score += 15
        if creator.display_name:
            score += 5
        if creator.external_id:
            score += 5
        if creator.follower_count and 100_000 <= creator.follower_count <= 1_000_000:
            score += 20
        elif creator.follower_count and creator.follower_count > 25_000:
            score += 10

        recent_content = [item for item in content_items if item.caption_text or item.title]
        if len(recent_content) >= 5:
            score += 15
        elif len(recent_content) >= 3:
            score += 10

        if any(item.url for item in content_items):
            score += 5
        return min(score, 100)

    def _calculate_fraud_risk(
        self,
        creator: Creator,
        snapshots: list[CreatorMetricSnapshot],
        content_items: list[CreatorContent],
    ) -> int:
        """Estimate creator fraud risk where a higher score means more risk."""

        risk = 15
        if not content_items:
            risk += 25

        latest_with_views = next(
            (
                snapshot
                for snapshot in sorted(snapshots, key=lambda item: item.captured_at, reverse=True)
                if snapshot.average_views_30d is not None and snapshot.follower_count
            ),
            None,
        )
        if latest_with_views is not None and latest_with_views.follower_count:
            view_ratio = latest_with_views.average_views_30d / max(latest_with_views.follower_count, 1)
            if view_ratio < 0.005:
                risk += 35
            elif view_ratio < 0.01:
                risk += 20

        hashtag_pool = [tag.lower() for item in content_items for tag in item.top_hashtags]
        if hashtag_pool and len(set(hashtag_pool)) <= max(1, len(hashtag_pool) // 3):
            risk += 10

        return min(risk, 100)

    def _calculate_evidence_coverage(
        self,
        creator: Creator,
        content_items: list[CreatorContent],
    ) -> int:
        """Estimate evidence coverage from the amount of structured source material on hand."""

        score = 0
        if creator.bio:
            score += 20
        if creator.profile_url:
            score += 20
        if creator.follower_count is not None:
            score += 20
        if len(content_items) >= 3:
            score += 20
        if any(item.raw_payload for item in content_items):
            score += 20
        return min(score, 100)

    def _qualification_decision(
        self,
        creator: Creator,
        growth_score: int,
        commercial_readiness_score: int,
        fraud_risk_score: int,
        evidence_coverage_score: int,
    ) -> tuple[bool, list[str]]:
        """Turn scores into a first qualification decision for phase 1."""

        reasons: list[str] = []
        if creator.follower_count is None or not 100_000 <= creator.follower_count <= 1_000_000:
            reasons.append("follower_count_outside_phase_1_range")
        if growth_score < 60:
            reasons.append("growth_below_threshold")
        if commercial_readiness_score < 60:
            reasons.append("commercial_readiness_below_threshold")
        if fraud_risk_score > 40:
            reasons.append("fraud_risk_above_threshold")
        if evidence_coverage_score < 60:
            reasons.append("evidence_coverage_below_threshold")
        return len(reasons) == 0, reasons
