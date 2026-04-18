"""Tests for brand spend-intent scoring."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from ima.brands.spend_intent import BrandSpendIntentScorer
from ima.creators.scoring_config import ScoringConfig
from ima.db.models import Brand


def test_spend_intent_scorer_uses_configurable_weights() -> None:
    """Brand spend intent should follow the configured phase-1 weights."""

    scorer = BrandSpendIntentScorer(
        ScoringConfig.model_validate(
            {
                "brand_spend_intent": {
                    "branded_content_weight": 0.5,
                    "hiring_signal_weight": 0.25,
                    "creator_program_weight": 0.25,
                }
            }
        )
    )

    score = scorer.compute_score(
        branded_content_score=1.0,
        hiring_signal_score=0.5,
        creator_program_score=0.0,
    )

    assert score == 0.625


def test_spend_intent_scorer_updates_brand_record() -> None:
    """Scoring a brand should persist the final score onto the ORM object."""

    brand = Brand(
        id=uuid4(),
        name="Notion",
        domain="notion.so",
        niche_ids=["productivity"],
        geo_markets=["US"],
        branded_content_score=Decimal("0.5000"),
        hiring_signal_score=Decimal("1.0000"),
        creator_program_score=Decimal("0.5000"),
    )

    result = BrandSpendIntentScorer().score_brand(brand)

    assert result.spend_intent_score == 0.675
    assert brand.spend_intent_score == Decimal("0.675")
