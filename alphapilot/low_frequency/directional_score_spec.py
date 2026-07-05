"""Directional score specification for V13.4.33.

Scores are research explanation layers only. They are not trading signals,
orders, or Dry-run approvals.
"""

from __future__ import annotations

from typing import Any


def build_directional_score_framework() -> dict[str, Any]:
    return {
        "status": "research_only",
        "description": "Simplified 0-5 scoring framework for future low-frequency candidate explanations.",
        "interpretation": {
            "longScore": "Research context for long-side evidence completeness, not a buy instruction.",
            "shortScore": "Research context for short-side evidence completeness, not a sell or short instruction.",
            "avoidScore": "Research context for conditions where no-trade or observe-only is preferred.",
        },
        "scoreRange": {"min": 0, "max": 5},
        "longScoreInputs": [
            "trend up",
            "pullback quality",
            "reclaim of EMA20 or EMA50",
            "volume health",
            "regime supportive",
        ],
        "shortScoreInputs": [
            "trend down or rejection",
            "failed bounce",
            "momentum weakening",
            "no chase after large drop",
            "regime supportive",
        ],
        "avoidScoreInputs": [
            "crash or extreme volatility",
            "technical direction conflict",
            "data quality issue",
            "liquidity or spread unavailable",
            "entry extended beyond risk concept",
        ],
        "hardRules": [
            "Scores do not create trades.",
            "Scores do not approve Dry-run.",
            "Scores must be reported with baseline comparison before future implementation review.",
            "No single regime label is a full entry or exit rule.",
        ],
    }
