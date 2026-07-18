"""Deterministic overlap audit against the archived strategy identity catalog."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence


def _tokens(value: Any) -> set[str]:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True) if not isinstance(value, str) else value
    return {token for token in re.split(r"[^0-9A-Za-z_\u4e00-\u9fff]+", text.lower()) if len(token) >= 2}


def _overlap(left: Any, right: Any) -> float:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    union = left_tokens | right_tokens
    return len(left_tokens & right_tokens) / len(union) if union else 0.0


def build_novelty_audit(
    candidates: Sequence[Mapping[str, Any]],
    history_inventory_path: Path,
) -> dict[str, Any]:
    payload = json.loads(Path(history_inventory_path).read_text(encoding="utf-8"))
    history = [dict(row) for row in payload.get("strategies") or []]
    family_ids = {str(row.get("strategyFamilyId") or row.get("strategyFamily") or "") for row in history}
    candidate_rows = []
    for candidate in candidates:
        family = str(candidate["familyId"])
        family_matches = sorted(
            str(row.get("strategyId"))
            for row in history
            if str(row.get("strategyFamilyId") or row.get("strategyFamily") or "") == family
        )
        scored = []
        for row in history:
            scored.append(
                {
                    "strategyId": str(row.get("strategyId")),
                    "semanticOverlap": _overlap(
                        [family, candidate.get("humanHypothesisZh")],
                        [row.get("strategyFamily"), row.get("strategyName")],
                    ),
                    "signalOverlap": _overlap(
                        candidate.get("entryDefinition"), row.get("definition")
                    ),
                    "exitPolicyOverlap": _overlap(
                        candidate.get("exitPolicy"), row.get("parameters")
                    ),
                }
            )
        scored.sort(
            key=lambda row: (
                -max(row["semanticOverlap"], row["signalOverlap"], row["exitPolicyOverlap"]),
                row["strategyId"],
            )
        )
        candidate_rows.append(
            {
                "candidateId": candidate["candidateId"],
                "familyId": family,
                "historicalFamilyMatches": family_matches,
                "topHistoricalOverlaps": scored[:5],
                "noveltyStatus": (
                    "overlap_recorded_frozen_candidate_retained"
                    if family_matches or any(max(row["semanticOverlap"], row["signalOverlap"], row["exitPolicyOverlap"]) > 0 for row in scored[:1])
                    else "no_material_overlap_observed"
                ),
                "candidateReplaced": False,
            }
        )
    return {
        "schemaVersion": "advisory_r_novelty_audit_v2",
        "historyStrategyIdentityCount": len(history),
        "historyStrategyFamilyCount": len(family_ids - {""}),
        "postResultCandidateReplacementAllowed": False,
        "candidates": candidate_rows,
    }
