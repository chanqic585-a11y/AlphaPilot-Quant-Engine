from __future__ import annotations

import unittest

from alphapilot.reports.v13_27_18_cross_timeframe_candidate_pack import (
    evidence_candidate_id,
    build_v13_27_18_candidate_rows,
)
from alphapilot.short_cycle.event_window_candidates import (
    cross_timeframe_workflow_candidate_pool,
)


class V132718CrossTimeframeCandidatePackTests(unittest.TestCase):
    def test_current_definitions_bind_to_prior_development_evidence(self) -> None:
        candidates = cross_timeframe_workflow_candidate_pool()
        source_rows = [
            {
                "candidateId": evidence_candidate_id(item),
                "timeframe": item.timeframe,
                "selectionTier": "rejected",
                "targetR": 2.0,
                "metrics": {"tradeCount": 40, "profitFactor": 1.1},
                "lockedOrHoldoutUsedForSelection": False,
                "executableWorkflowAvailable": False,
                "workflowBlocker": "old_adapter_pending",
            }
            for item in candidates
        ]

        rows = build_v13_27_18_candidate_rows(candidates, source_rows)

        self.assertEqual(25, len(rows))
        self.assertEqual(25, len({row["candidateId"] for row in rows}))
        self.assertTrue(all(row["executableWorkflowAvailable"] for row in rows))
        self.assertTrue(all("workflowBlocker" not in row for row in rows))
        self.assertTrue(all(row["targetR"] == 2.0 for row in rows))
        self.assertTrue(
            all(not row["lockedOrHoldoutUsedForSelection"] for row in rows)
        )
        self.assertTrue(all(row["formalPromotionEvidence"] is False for row in rows))

        four_hour = [row for row in rows if row["timeframe"] == "4h"]
        self.assertTrue(
            all(
                row["formalDataPlan"]
                == {"signal": "4h", "execution": "15m", "fallback": "1h"}
                for row in four_hour
            )
        )

    def test_missing_evidence_row_fails_closed(self) -> None:
        candidates = cross_timeframe_workflow_candidate_pool()

        with self.assertRaisesRegex(ValueError, "candidate_evidence_missing"):
            build_v13_27_18_candidate_rows(candidates, [])


if __name__ == "__main__":
    unittest.main()
