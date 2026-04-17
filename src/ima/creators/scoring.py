"""Creator growth tracking and configurable scoring services."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ima.creators.schemas import CreatorGrowthSnapshotInput, CreatorScoreResult
from ima.creators.scoring_config import ScoringConfig, load_scoring_config
from ima.db.models import Creator, CreatorContent, CreatorMetricSnapshot
from ima.logging import get_logger

logger = get_logger(__name__)


def _normalized_labels(labels: Iterable[str]) -> set[str]:
    """Normalize niche labels for case-insensitive comparisons."""

    return {label.strip().lower() for label in labels if label and label.strip()}


def _ensure_utc(value: datetime) -> datetime:
    """Normalize potentially naive datetimes into UTC-aware values."""

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def compute_niche_fit(
    creator: Creator,
    target_niche: str,
    target_sub_niches: list[str],
    *,
    primary_label_weight: float,
    sub_label_weight: float,
) -> float:
    """Compute overlap between creator niche labels and the configured target niche."""

    creator_labels = _normalized_labels(creator.niche_labels)
    if not creator_labels or not target_niche.strip():
        return 0.0

    normalized_target = target_niche.strip().lower()
    normalized_sub_niches = _normalized_labels(target_sub_niches)
    primary_match = 1.0 if normalized_target in creator_labels else 0.0
    sub_match = 0.0
    if normalized_sub_niches:
        sub_match = len(normalized_sub_niches & creator_labels) / len(normalized_sub_niches)

    total_weight = primary_label_weight + sub_label_weight
    if total_weight <= 0:
        return 0.0

    score = (primary_match * primary_label_weight + sub_match * sub_label_weight) / total_weight
    return round(min(max(score, 0.0), 1.0), 4)


def compute_growth_score(
    creator: Creator,
    snapshots: list[CreatorMetricSnapshot],
    config: ScoringConfig,
) -> float:
    """Compute trajectory-aware growth from historical snapshots."""

    valid = sorted(
        [snapshot for snapshot in snapshots if snapshot.follower_count is not None],
        key=lambda snapshot: snapshot.captured_at,
    )
    if len(valid) < 2:
        return config.growth.neutral_score

    oldest = valid[0].follower_count or 0
    newest = valid[-1].follower_count or 0
    if oldest <= 0:
        return config.growth.neutral_score

    growth_ratio = (newest - oldest) / oldest
    score = config.growth.steep_decline_score
    if growth_ratio >= config.growth.strong_growth_ratio:
        score = config.growth.strong_growth_score
    elif growth_ratio >= config.growth.solid_growth_ratio:
        score = config.growth.solid_growth_score
    elif growth_ratio >= config.growth.healthy_growth_ratio:
        score = config.growth.healthy_growth_score
    elif growth_ratio >= config.growth.mild_growth_ratio:
        score = config.growth.mild_growth_score
    elif growth_ratio >= config.growth.flat_band_ratio:
        score = config.growth.flat_band_score
    elif growth_ratio >= config.growth.decline_band_ratio:
        score = config.growth.decline_band_score

    latest_views = valid[-1].average_views_30d
    if creator.followers and latest_views:
        view_ratio = latest_views / max(creator.followers, 1)
        if view_ratio >= config.growth.healthy_view_ratio_bonus_threshold:
            score = min(score + config.growth.healthy_view_ratio_bonus, 1.0)

    return round(min(max(score, 0.0), 1.0), 4)


def compute_commercial_readiness(
    creator: Creator,
    content_items: list[CreatorContent],
    config: ScoringConfig,
) -> float:
    """Estimate how prepared a creator appears for sponsorship outreach."""

    commercial = config.commercial
    score = commercial.base_score

    if creator.bio:
        score += commercial.bio_bonus
    if creator.profile_url:
        score += commercial.profile_url_bonus
    if creator.display_name:
        score += commercial.display_name_bonus
    if creator.external_id:
        score += commercial.external_id_bonus

    if (
        creator.followers
        and commercial.target_min_followers <= creator.followers <= commercial.target_max_followers
    ):
        score += commercial.target_range_bonus
    elif creator.followers and creator.followers >= commercial.fallback_min_followers:
        score += commercial.fallback_range_bonus

    informative_content = [item for item in content_items if item.caption or item.title]
    if len(informative_content) >= commercial.strong_content_count:
        score += commercial.strong_content_bonus
    elif len(informative_content) >= commercial.medium_content_count:
        score += commercial.medium_content_bonus

    if any(item.url for item in content_items):
        score += commercial.url_bonus

    return round(min(max(score, 0.0), 1.0), 4)


def compute_fraud_risk(
    creator: Creator,
    snapshots: list[CreatorMetricSnapshot],
    content_items: list[CreatorContent],
    config: ScoringConfig,
) -> float:
    """Estimate follower or engagement irregularities where higher is riskier."""

    fraud = config.fraud
    risk = fraud.base_risk

    if not content_items:
        risk += fraud.no_content_penalty

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
        if view_ratio < fraud.low_view_ratio_threshold:
            risk += fraud.low_view_ratio_penalty
        elif view_ratio < fraud.medium_view_ratio_threshold:
            risk += fraud.medium_view_ratio_penalty

    hashtag_pool = [tag.lower() for item in content_items for tag in item.hashtags]
    if hashtag_pool and len(set(hashtag_pool)) <= max(1, len(hashtag_pool) // 3):
        risk += fraud.repetitive_hashtag_penalty

    return round(min(max(risk, 0.0), 1.0), 4)


def compute_evidence_coverage(
    creator: Creator,
    content_items: list[CreatorContent],
    config: ScoringConfig,
) -> float:
    """Estimate evidence coverage from available structured source material."""

    coverage = config.evidence_coverage
    score = 0.0

    if creator.bio:
        score += coverage.bio_weight
    if creator.profile_url:
        score += coverage.profile_url_weight
    if creator.followers is not None:
        score += coverage.followers_weight
    if len(content_items) >= coverage.minimum_content_items:
        score += coverage.content_weight
    if any(item.raw_payload for item in content_items):
        score += coverage.raw_payload_weight

    return round(min(max(score, 0.0), 1.0), 4)


class CreatorScoringService:
    """Config-driven scoring logic for week-2 creator qualification."""

    def __init__(
        self,
        session: AsyncSession,
        scoring_config: ScoringConfig | None = None,
    ) -> None:
        """Create a scoring service bound to one async DB session."""

        self.session = session
        self.scoring_config = scoring_config or load_scoring_config()

    async def record_snapshot(self, payload: CreatorGrowthSnapshotInput) -> CreatorMetricSnapshot:
        """Persist or update one creator metric snapshot per creator per UTC day."""

        creator_id = UUID(payload.creator_id)
        day_start = datetime.combine(payload.captured_at.date(), time.min, tzinfo=UTC)
        day_end = day_start + timedelta(days=1)
        snapshot = await self.session.scalar(
            select(CreatorMetricSnapshot).where(
                CreatorMetricSnapshot.creator_id == creator_id,
                CreatorMetricSnapshot.captured_at >= day_start,
                CreatorMetricSnapshot.captured_at < day_end,
            )
        )
        if snapshot is None:
            snapshot = CreatorMetricSnapshot(
                creator_id=creator_id,
                captured_at=payload.captured_at,
            )
            self.session.add(snapshot)
            logger.info(
                "creator_growth_snapshot_recorded",
                creator_id=payload.creator_id,
                source=payload.source,
            )
        else:
            logger.warning(
                "creator_growth_snapshot_upserted",
                creator_id=payload.creator_id,
                source=payload.source,
                captured_at=payload.captured_at.isoformat(),
            )

        snapshot.captured_at = payload.captured_at
        snapshot.follower_count = payload.followers
        snapshot.average_views_30d = payload.average_views_30d
        snapshot.average_likes_30d = payload.average_likes_30d
        snapshot.average_comments_30d = payload.average_comments_30d
        snapshot.engagement_rate_30d = payload.engagement_rate_30d
        snapshot.source = payload.source
        await self.session.flush()
        return snapshot

    async def score_creator(self, creator_id: str) -> CreatorScoreResult:
        """Compute and persist the creator score set against the configured target niche."""

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

        growth_score = compute_growth_score(creator, snapshots, self.scoring_config)
        niche_fit_score = compute_niche_fit(
            creator,
            self.scoring_config.target_niche,
            self.scoring_config.target_sub_niches,
            primary_label_weight=self.scoring_config.niche_fit.primary_label_weight,
            sub_label_weight=self.scoring_config.niche_fit.sub_label_weight,
        )
        commercial_score = compute_commercial_readiness(creator, content_items, self.scoring_config)
        fraud_score = compute_fraud_risk(creator, snapshots, content_items, self.scoring_config)
        evidence_coverage_score = compute_evidence_coverage(
            creator,
            content_items,
            self.scoring_config,
        )
        is_qualified, reasons = self._qualification_decision(
            creator=creator,
            growth_score=growth_score,
            niche_fit_score=niche_fit_score,
            commercial_score=commercial_score,
            fraud_score=fraud_score,
            evidence_coverage_score=evidence_coverage_score,
        )

        latest_snapshot = snapshots[-1] if snapshots else None
        recent_snapshots = [
            snapshot
            for snapshot in snapshots
            if _ensure_utc(snapshot.captured_at) >= datetime.now(UTC) - timedelta(days=90)
            and snapshot.average_views_30d is not None
        ]
        if latest_snapshot is not None:
            creator.avg_views_30d = latest_snapshot.average_views_30d
            creator.avg_engagement_30d = latest_snapshot.engagement_rate_30d
        if recent_snapshots:
            creator.avg_views_90d = int(
                sum(snapshot.average_views_30d or 0 for snapshot in recent_snapshots)
                / len(recent_snapshots)
            )

        creator.growth_score = Decimal(str(growth_score))
        creator.niche_fit_score = Decimal(str(niche_fit_score))
        creator.commercial_score = Decimal(str(commercial_score))
        creator.fraud_score = Decimal(str(fraud_score))
        creator.evidence_coverage_score = Decimal(str(evidence_coverage_score))
        creator.is_qualified = is_qualified
        creator.last_seen_at = datetime.now(UTC)
        await self.session.flush()

        logger.info(
            "creator_scored",
            creator_id=str(creator.id),
            growth_score=growth_score,
            niche_fit_score=niche_fit_score,
            commercial_score=commercial_score,
            fraud_score=fraud_score,
            evidence_coverage_score=evidence_coverage_score,
            is_qualified=is_qualified,
        )

        return CreatorScoreResult(
            creator_id=str(creator.id),
            growth_score=growth_score,
            niche_fit_score=niche_fit_score,
            commercial_score=commercial_score,
            fraud_score=fraud_score,
            evidence_coverage_score=evidence_coverage_score,
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

    def _qualification_decision(
        self,
        *,
        creator: Creator,
        growth_score: float,
        niche_fit_score: float,
        commercial_score: float,
        fraud_score: float,
        evidence_coverage_score: float,
    ) -> tuple[bool, list[str]]:
        """Turn scores into a first qualification decision for phase 1."""

        qualification = self.scoring_config.qualification
        reasons: list[str] = []
        if creator.followers is None or not (
            qualification.min_followers <= creator.followers <= qualification.max_followers
        ):
            reasons.append("followers_outside_phase_1_range")
        if growth_score < qualification.min_growth_score:
            reasons.append("growth_below_threshold")
        if niche_fit_score < qualification.min_niche_fit_score:
            reasons.append("niche_fit_below_threshold")
        if commercial_score < qualification.min_commercial_score:
            reasons.append("commercial_below_threshold")
        if fraud_score > qualification.max_fraud_score:
            reasons.append("fraud_above_threshold")
        if evidence_coverage_score < qualification.min_evidence_coverage_score:
            reasons.append("evidence_coverage_below_threshold")
        return len(reasons) == 0, reasons
