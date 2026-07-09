from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.legacy_importer import import_legacy_reports
from alphapilot.evolution.registry.repositories import RegistryRepository


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class LegacyImporterTests(unittest.TestCase):
    def test_reports_are_classified_deduplicated_and_not_promoted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reports = root / "reports"
            reports.mkdir()
            write_json(
                reports / "factor_report.json",
                {
                    "reportId": "factor_eval",
                    "factorCount": 16,
                    "factorReports": [{"factorId": "momentum"}],
                    "candidateFactors": [],
                },
            )
            strategy_payload = {
                "reportId": "trend_strategy_report",
                "strategyId": "alpha_trend_v1",
                "timeframe": "1h",
                "direction": "long",
                "entryRules": ["close_above_ema"],
                "exitRules": {"takeProfitR": 2.0, "stopLossR": 1.0},
                "riskRules": {"riskPerTradePct": 0.25},
                "metrics": {"tradeCount": 120, "profitFactor": 1.4},
            }
            write_json(reports / "strategy_report.json", strategy_payload)
            write_json(reports / "strategy_report_copy.json", strategy_payload)
            write_json(reports / "summary.json", {"reportId": "summary", "profitFactor": 1.1})
            write_json(reports / "incomplete.json", {"reportId": "notes_only", "notes": ["research"]})
            (reports / "invalid.json").write_text("{invalid", encoding="utf-8")

            connection = connect_registry(root / "registry.sqlite")
            try:
                repository = RegistryRepository(connection)
                first = import_legacy_reports(reports, repository)
                second = import_legacy_reports(reports, repository)
                evidence = repository.list_legacy_evidence()
                candidate_count = repository.count("StrategyCandidates")
                release_count = repository.count("DemoReleases")
            finally:
                connection.close()

        self.assertEqual(first["scannedFileCount"], 6)
        self.assertEqual(first["invalidFileCount"], 1)
        self.assertEqual(first["classificationCounts"]["factor_asset"], 1)
        self.assertEqual(first["classificationCounts"]["strategy_candidate_evidence"], 1)
        self.assertEqual(first["classificationCounts"]["duplicate_family_member"], 1)
        self.assertEqual(first["classificationCounts"]["report_summary"], 1)
        self.assertEqual(first["classificationCounts"]["incomplete_evidence"], 1)
        self.assertEqual(len(evidence), 5)
        self.assertEqual(second["newEvidenceCount"], 0)
        self.assertEqual(candidate_count, 0)
        self.assertEqual(release_count, 0)

    def test_array_artifacts_and_utf8_bom_are_registered_as_research_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reports = root / "reports"
            reports.mkdir()
            write_json(
                reports / "historical_signal_log.json",
                [
                    {
                        "strategyId": "signal_log_only",
                        "entryRules": ["observed_entry"],
                        "exitRules": {"takeProfitR": 2.0},
                        "riskRules": {"riskPerTradePct": 0.2},
                    }
                ],
            )
            (reports / "bom_summary.json").write_text(
                json.dumps({"reportId": "bom_summary", "profitFactor": 1.2}),
                encoding="utf-8-sig",
            )

            connection = connect_registry(root / "registry.sqlite")
            try:
                repository = RegistryRepository(connection)
                summary = import_legacy_reports(reports, repository)
                evidence = repository.list_legacy_evidence()
                candidate_count = repository.count("StrategyCandidates")
            finally:
                connection.close()

        self.assertEqual(summary["scannedFileCount"], 2)
        self.assertEqual(summary["validJsonCount"], 2)
        self.assertEqual(summary["invalidFileCount"], 0)
        self.assertEqual(len(evidence), 2)
        self.assertIsInstance(evidence[1].payload, list)
        self.assertEqual(evidence[1].evidenceType, "incomplete_evidence")
        self.assertIn("top_level_array_research_artifact", evidence[1].classificationReasons)
        self.assertEqual(candidate_count, 0)

    def test_rule_variants_share_one_family_but_are_not_exact_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reports = root / "reports"
            reports.mkdir()
            base = {
                "strategyId": "trend_family_v1",
                "entryRules": ["close_above_ema"],
                "riskRules": {"riskPerTradePct": 0.25},
            }
            write_json(
                reports / "variant_a.json",
                {**base, "exitRules": {"takeProfitR": 2.0, "stopLossR": 1.0}},
            )
            write_json(
                reports / "variant_b.json",
                {**base, "exitRules": {"takeProfitR": 2.5, "stopLossR": 1.0}},
            )

            connection = connect_registry(root / "registry.sqlite")
            try:
                repository = RegistryRepository(connection)
                summary = import_legacy_reports(reports, repository)
                evidence = repository.list_legacy_evidence()
                family_count = repository.count("StrategyFamilies")
            finally:
                connection.close()

        self.assertEqual(summary["classificationCounts"]["strategy_candidate_evidence"], 2)
        self.assertNotIn("duplicate_family_member", summary["classificationCounts"])
        self.assertEqual(family_count, 1)
        self.assertEqual(len({item.strategyFamilyId for item in evidence}), 1)
        self.assertEqual(len({item.ruleFingerprint for item in evidence}), 2)

    def test_snake_case_strategy_contract_is_classified_without_name_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reports = root / "reports"
            reports.mkdir()
            write_json(
                reports / "snake_case.json",
                {
                    "strategy_id": "snake_case_family_v1",
                    "entry_rules": ["close_above_ema"],
                    "exit_rules": {"take_profit_r": 2.0, "stop_loss_r": 1.0},
                    "risk_rules": {"risk_per_trade_pct": 0.25},
                },
            )

            connection = connect_registry(root / "registry.sqlite")
            try:
                repository = RegistryRepository(connection)
                summary = import_legacy_reports(reports, repository)
                evidence = repository.list_legacy_evidence()
            finally:
                connection.close()

        self.assertEqual(summary["classificationCounts"]["strategy_candidate_evidence"], 1)
        self.assertEqual(evidence[0].strategyFamilyId, evidence[0].familyFingerprint)
        self.assertIsNotNone(evidence[0].ruleFingerprint)


if __name__ == "__main__":
    unittest.main()
