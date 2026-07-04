"""Built-in V13.4.20 probability gate candidate registry.

Candidate gates are configuration artifacts for future backtest research only.
They are not connected to strategy entry, Dry-run, live trading, API keys, or
orders.
"""

from __future__ import annotations

from pathlib import Path

DEFAULT_CANDIDATE_CONFIG_DIR = Path("configs/probability_gate_candidates")

CANDIDATE_GATE_IDS = [
    "probability_gate_c1_trend_medium_safe",
    "probability_gate_d1_trend_module_low_safe",
    "probability_gate_cd_trend_research_combined",
]

REJECTED_DIAGNOSTIC_BUCKETS = [
    {
        "bucketId": "avoid_low_weak",
        "sourceTable": "reports/v13_4_19_probability_score_table_coarse_c.json",
        "status": "diagnostic_only",
        "entryAllowed": False,
        "reason": "avoid regime cannot be promoted to entry candidate from bucket-level PF.",
    },
    {
        "bucketId": "unknown_no_entry_module_low_safe",
        "sourceTable": "reports/v13_4_19_probability_score_table_coarse_d.json",
        "status": "diagnostic_only",
        "entryAllowed": False,
        "reason": "unknown regime or no_entry module cannot become an entry candidate.",
    },
]


def candidate_config_path(candidate_id: str, config_dir: Path = DEFAULT_CANDIDATE_CONFIG_DIR) -> Path:
    return config_dir / f"{candidate_id}.json"
