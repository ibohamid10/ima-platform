"""Brand spend-intent scoring from three configurable phase-1 signals."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

from ima.creators.scoring_config import ScoringConfig, load_scoring_config
from ima.db.models import Brand


class SpendIntentScoreResult(BaseModel):
    """Serializable breakdown of one spend-intent computation."""

    brand_id: str
    spend_intent_score: float
    branded_content_score: float
    hiring_signal_score: float
    creator_program_score: float


class BrandSpendIntentScorer:
    """Apply configurable phase-1 weights to brand spend-intent signals."""

    def __init__(self, scoring_config: ScoringConfig | None = None) -> None:
        """Create a scorer with configurable weights."""

        self.scoring_config = scoring_config or load_scoring_config()

    def compute_score(
        self,
        *,
        branded_content_score: float,
        hiring_signal_score: float,
        creator_program_score: float,
    ) -> float:
        """Compute the final weighted spend-intent score."""

        weights = self.scoring_config.brand_spend_intent
        score = (
            weights.branded_content_weight * branded_content_score
            + weights.hiring_signal_weight * hiring_signal_score
            + weights.creator_program_weight * creator_program_score
        )
        return round(min(max(score, 0.0), 1.0), 4)

    def score_brand(self, brand: Brand) -> SpendIntentScoreResult:
        """Score one brand from its current stored component signals."""

        branded = float(brand.branded_content_score or 0)
        hiring = float(brand.hiring_signal_score or 0)
        creator_program = float(brand.creator_program_score or 0)
        score = self.compute_score(
            branded_content_score=branded,
            hiring_signal_score=hiring,
            creator_program_score=creator_program,
        )
        brand.spend_intent_score = Decimal(str(score))
        return SpendIntentScoreResult(
            brand_id=str(brand.id),
            spend_intent_score=score,
            branded_content_score=branded,
            hiring_signal_score=hiring,
            creator_program_score=creator_program,
        )
