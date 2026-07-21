from __future__ import annotations

import unittest
import sqlite3
import tempfile
from pathlib import Path

from alphapilot.scripts.build_v59_readiness_audit import build_console_summary
from alphapilot.adaptive_learning.v59_readiness_audit import (
    audit_registry_database,
    audit_registry_evidence,
)


class V59ReadinessAuditTests(unittest.TestCase):
    def test_engineering_factor_runs_and_zero_fold_models_are_not_live_evidence(self) -> None:
        result = audit_registry_evidence(
            factor_runs=[
                {
                    "factorRunId": "factor-run-smoke",
                    "status": "completed",
                    "payload": {
                        "pointInTimeValidated": True,
                        "formalPromotionEligible": False,
                        "evidenceClass": "engineering_smoke_provenance_blocked",
                    },
                }
            ],
            models=[
                {
                    "modelId": "model-shadow",
                    "status": "shadow_candidate",
                    "payload": {
                        "artifact": {
                            "researchOnly": True,
                            "trainingEvidence": {
                                "pointInTimeValidated": True,
                                "purgedWalkForward": True,
                                "foldCount": 0,
                            },
                        }
                    },
                }
            ],
            data_snapshots=[
                {
                    "dataSnapshotId": "snapshot-mixed",
                    "pointInTimeCutoff": "2026-07-01T00:00:00Z",
                    "manifest": {
                        "metadata": {
                            "formalPromotionEligible": False,
                            "provenanceComplete": False,
                        }
                    },
                }
            ],
        )

        self.assertEqual(result["formalFactorRunCount"], 0)
        self.assertEqual(result["liveEligibleModelCount"], 0)
        self.assertEqual(result["formalDataSnapshotCount"], 0)
        self.assertIn("no_formal_factor_runs", result["blockers"])
        self.assertIn("no_live_eligible_models", result["blockers"])
        self.assertIn("no_formal_data_snapshots", result["blockers"])
        self.assertIn(
            "engineering_smoke_provenance_blocked",
            result["factorRuns"][0]["blockers"],
        )
        self.assertIn("walk_forward_fold_count_zero", result["models"][0]["blockers"])

    def test_only_formal_complete_hash_bound_records_are_eligible(self) -> None:
        result = audit_registry_evidence(
            factor_runs=[
                {
                    "factorRunId": "factor-run-formal",
                    "status": "completed",
                    "resultSha256": "a" * 64,
                    "payload": {
                        "pointInTimeValidated": True,
                        "formalPromotionEligible": True,
                        "evidenceClass": "formal_research",
                    },
                }
            ],
            models=[
                {
                    "modelId": "model-validated",
                    "status": "validated",
                    "artifactSha256": "b" * 64,
                    "payload": {
                        "artifact": {
                            "researchOnly": False,
                            "modelHash": "model-hash",
                            "trainingEvidence": {
                                "pointInTimeValidated": True,
                                "purgedWalkForward": True,
                                "foldCount": 4,
                                "sampleCount": 1000,
                            },
                        },
                        "lifecycleBoundary": "live_candidate",
                    },
                }
            ],
            data_snapshots=[
                {
                    "dataSnapshotId": "snapshot-formal",
                    "pointInTimeCutoff": "2026-07-01T00:00:00Z",
                    "contentHash": "c" * 64,
                    "manifest": {
                        "metadata": {
                            "formalPromotionEligible": True,
                            "provenanceComplete": True,
                        },
                        "universeMembers": ["BTC-USDT-SWAP"],
                    },
                }
            ],
        )

        self.assertEqual(result["status"], "registry_evidence_ready")
        self.assertEqual(result["formalFactorRunCount"], 1)
        self.assertEqual(result["liveEligibleModelCount"], 1)
        self.assertEqual(result["formalDataSnapshotCount"], 1)
        self.assertEqual(result["blockers"], [])
        self.assertTrue(result["auditHash"].startswith("v59_registry_evidence_audit_"))

    def test_formal_market_data_factor_runs_are_eligible(self) -> None:
        result = audit_registry_evidence(
            factor_runs=[
                {
                    "factorRunId": "factor-run-formal-market-data",
                    "status": "completed",
                    "resultSha256": "a" * 64,
                    "payload": {
                        "pointInTimeValidated": True,
                        "formalPromotionEligible": True,
                        "evidenceClass": "formal_market_data",
                    },
                }
            ],
            models=[],
            data_snapshots=[],
        )

        self.assertEqual(result["formalFactorRunCount"], 1)
        self.assertTrue(result["factorRuns"][0]["eligible"])
        self.assertNotIn("no_formal_factor_runs", result["blockers"])

    def test_registry_database_loader_reads_existing_records_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.sqlite"
            connection = sqlite3.connect(path)
            connection.executescript(
                """
                CREATE TABLE FactorRuns(
                    factorRunId TEXT, status TEXT, resultSha256 TEXT, payloadJson TEXT
                );
                CREATE TABLE Models(
                    modelId TEXT, status TEXT, artifactSha256 TEXT, payloadJson TEXT
                );
                CREATE TABLE DataSnapshots(
                    dataSnapshotId TEXT, pointInTimeCutoff TEXT,
                    contentHash TEXT, manifestJson TEXT
                );
                """
            )
            connection.execute(
                "INSERT INTO FactorRuns VALUES(?,?,?,?)",
                (
                    "factor-run",
                    "completed",
                    "a" * 64,
                    '{"pointInTimeValidated":true,"formalPromotionEligible":false,'
                    '"evidenceClass":"engineering_smoke_provenance_blocked"}',
                ),
            )
            connection.execute(
                "INSERT INTO Models VALUES(?,?,?,?)",
                ("model", "shadow_candidate", None, '{"artifact":{"researchOnly":true}}'),
            )
            connection.execute(
                "INSERT INTO DataSnapshots VALUES(?,?,?,?)",
                (
                    "snapshot",
                    "2026-07-01T00:00:00Z",
                    "c" * 64,
                    '{"metadata":{"formalPromotionEligible":false,'
                    '"provenanceComplete":false},"universeMembers":["BTC-USDT-SWAP"]}',
                ),
            )
            connection.commit()
            connection.close()

            result = audit_registry_database(path)

            self.assertEqual(result["factorRunCount"], 1)
            self.assertEqual(result["modelCount"], 1)
            self.assertEqual(result["dataSnapshotCount"], 1)
            self.assertEqual(result["status"], "blocked_registry_evidence")

    def test_console_summary_is_bounded_and_excludes_record_details(self) -> None:
        payload = {
            "status": "blocked_registry_evidence",
            "auditHash": "v59_registry_evidence_audit_hash",
            "factorRunCount": 10,
            "formalFactorRunCount": 0,
            "modelCount": 2,
            "liveEligibleModelCount": 0,
            "dataSnapshotCount": 166,
            "formalDataSnapshotCount": 162,
            "blockers": ["no_formal_factor_runs", "no_live_eligible_models"],
            "factorRuns": [{"factorRunId": f"factor-{index}"} for index in range(10)],
            "models": [{"modelId": "model-1"}],
            "dataSnapshots": [{"dataSnapshotId": f"snapshot-{index}"} for index in range(166)],
        }

        summary = build_console_summary(payload, output_path=Path("audit.json"))

        self.assertEqual(summary["status"], "blocked_registry_evidence")
        self.assertEqual(summary["formalFactorRunCount"], 0)
        self.assertEqual(summary["formalDataSnapshotCount"], 162)
        self.assertEqual(summary["output"], "audit.json")
        self.assertNotIn("factorRuns", summary)
        self.assertNotIn("models", summary)
        self.assertNotIn("dataSnapshots", summary)


if __name__ == "__main__":
    unittest.main()
