from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

from alphapilot.reports.archived_strategy_evidence_index import build_evidence_index
from alphapilot.reports.archived_strategy_failure_attribution_v2 import (
    attribute_archived_failure,
)
from alphapilot.reports.archived_strategy_trade_extractor import (
    extract_freqtrade_trades,
)
from alphapilot.reports.full_archived_strategy_inventory import build_full_inventory
from alphapilot.reports.generate_full_archived_strategy_analysis import (
    REQUIRED_OUTPUTS,
    generate_full_archived_strategy_analysis,
)


def _create_registry(root: Path) -> None:
    data = root / "data"
    data.mkdir(parents=True)
    connection = sqlite3.connect(data / "evolution_registry.sqlite")
    connection.executescript(
        """
        CREATE TABLE StrategyFamilies (
          strategyFamilyId TEXT, familyKey TEXT, name TEXT, status TEXT,
          metadataJson TEXT, contentHash TEXT, createdAt TEXT
        );
        CREATE TABLE StrategyVersions (
          strategyVersionId TEXT, strategyFamilyId TEXT, parentStrategyVersionId TEXT,
          strategyCandidateId TEXT, displayName TEXT, sourceType TEXT, status TEXT,
          definitionJson TEXT, parametersJson TEXT, modelArtifactId TEXT,
          contentHash TEXT, createdAt TEXT
        );
        CREATE TABLE WorkflowRuns (
          workflowRunId TEXT, strategyVersionId TEXT, stage TEXT, status TEXT,
          attemptNumber INTEGER, gateProfileId TEXT, riskProfileId TEXT,
          idempotencyKey TEXT, progressJson TEXT, resultJson TEXT,
          startedAt TEXT, checkpointAt TEXT, completedAt TEXT, contentHash TEXT,
          createdAt TEXT, updatedAt TEXT
        );
        CREATE TABLE FailureDiagnoses (
          failureDiagnosisId TEXT, workflowRunId TEXT, category TEXT, summary TEXT,
          retryDisposition TEXT, metricsJson TEXT, suggestionsJson TEXT,
          contentHash TEXT, createdAt TEXT
        );
        CREATE TABLE LegacyEvidence (
          legacyEvidenceId TEXT, sourcePath TEXT, sourceSha256 TEXT,
          evidenceType TEXT, strategyFamilyId TEXT, familyFingerprint TEXT,
          ruleFingerprint TEXT, classificationReasonsJson TEXT, payloadJson TEXT,
          contentHash TEXT, importedAt TEXT
        );
        """
    )
    connection.execute(
        "INSERT INTO StrategyFamilies VALUES (?,?,?,?,?,?,?)",
        ("family_1", "test_family", "测试策略家族", "shadow_research", "{}", "fh", "2026-07-15T00:00:00Z"),
    )
    definition = {
        "direction": "long",
        "timeframe": "15m",
        "executionEnabled": False,
        "plannedTargetR": 2.0,
    }
    connection.execute(
        "INSERT INTO StrategyVersions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "version_1", "family_1", None, None, "测试归档策略", "fixture",
            "archived", json.dumps(definition), "{}", None, "vh",
            "2026-07-15T00:00:00Z",
        ),
    )
    metrics = {
        "tradeCount": 40,
        "profitFactor": 0.8,
        "averageNetR": -0.1,
        "maximumDrawdownR": 7.0,
        "winRate": 0.4,
        "bySplit": {"locked_oos": {"tradeCount": 10, "profitFactor": 0.7}},
        "costStress": {"tradeCount": 40, "averageNetR": -0.2},
    }
    result = {"metrics": metrics, "checks": {"costStress": False}}
    connection.execute(
        "INSERT INTO WorkflowRuns VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "run_1", "version_1", "backtest", "failed", 1, None, None, None,
            json.dumps({"phase": "evaluating_gate", "artifacts": {}}),
            json.dumps(result), "2026-07-15T00:00:00Z", None,
            "2026-07-15T00:01:00Z", "rh", "2026-07-15T00:00:00Z",
            "2026-07-15T00:01:00Z",
        ),
    )
    connection.execute(
        "INSERT INTO FailureDiagnoses VALUES (?,?,?,?,?,?,?,?,?)",
        (
            "failure_1", "run_1", "strategy_performance",
            "Backtest gates failed", "new_version_required",
            json.dumps({"failedChecks": ["minimumProfitFactor"]}), "[]", "dh",
            "2026-07-15T00:01:00Z",
        ),
    )
    connection.commit()
    connection.close()


def _create_freqtrade_artifact(root: Path) -> None:
    strategies = root / "user_data" / "strategies"
    results = root / "user_data" / "backtest_results"
    strategies.mkdir(parents=True)
    results.mkdir(parents=True)
    (strategies / "FixtureStrategy.py").write_text(
        "class FixtureStrategy:\n    timeframe = '15m'\n    can_short = True\n",
        encoding="utf-8",
    )
    stem = "backtest-result-2026-07-15_00-00-00"
    meta = {
        "FixtureStrategy": {
            "run_id": "fixture-run",
            "timeframe": "15m",
            "backtest_start_ts": 100,
            "backtest_end_ts": 200,
        }
    }
    (results / f"{stem}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    trade = {
        "pair": "BTC/USDT:USDT",
        "open_date": "2026-07-01 00:00:00+00:00",
        "close_date": "2026-07-01 01:00:00+00:00",
        "open_rate": 100.0,
        "close_rate": 104.0,
        "min_rate": 98.0,
        "max_rate": 105.0,
        "profit_ratio": 0.04,
        "profit_abs": 4.0,
        "initial_stop_loss_abs": 98.0,
        "initial_stop_loss_ratio": -0.02,
        "fee_open": 0.001,
        "fee_close": 0.001,
        "funding_fees": 0.0,
        "enter_tag": "fixture",
        "exit_reason": "roi",
        "is_short": False,
        "leverage": 1.0,
        "orders": [],
    }
    payload = {
        "strategy": {
            "FixtureStrategy": {
                "trades": [trade],
                "total_trades": 1,
                "profit_factor": 2.0,
                "profit_total": 0.04,
                "max_drawdown_account": 0.01,
                "wins": 1,
                "losses": 0,
                "pairlist": ["BTC/USDT:USDT"],
                "timeframe": "15m",
            }
        },
        "strategy_comparison": [],
    }
    with zipfile.ZipFile(results / f"{stem}.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{stem}.json", json.dumps(payload))
        archive.writestr(f"{stem}_config.json", "{}")


class FullArchivedStrategyAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "reports").mkdir()
        (self.root / "docs").mkdir()
        _create_registry(self.root)
        _create_freqtrade_artifact(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_inventory_keeps_registry_versions_and_legacy_code_identity(self) -> None:
        inventory = build_full_inventory(self.root)
        by_id = {row["strategyId"]: row for row in inventory}

        self.assertIn("version_1", by_id)
        self.assertIn("freqtrade::FixtureStrategy", by_id)
        self.assertEqual("registry_version", by_id["version_1"]["identitySource"])
        self.assertEqual("archived", by_id["version_1"]["status"])
        self.assertFalse(by_id["version_1"]["executionEligible"])

    def test_evidence_index_assigns_real_zip_level_one_and_registry_level_two(self) -> None:
        inventory = build_full_inventory(self.root)
        evidence = build_evidence_index(self.root, inventory)

        levels = {(row["strategyId"], row["evidenceLevel"]) for row in evidence}
        self.assertIn(("freqtrade::FixtureStrategy", 1), levels)
        self.assertIn(("version_1", 2), levels)
        self.assertTrue(all(row["artifactHash"] for row in evidence))

    def test_trade_extractor_calculates_r_mfe_and_mae_without_fabrication(self) -> None:
        archive = next((self.root / "user_data" / "backtest_results").glob("*.zip"))
        rows = extract_freqtrade_trades(archive, "FixtureStrategy", "artifact_1")

        self.assertEqual(1, len(rows))
        self.assertAlmostEqual(2.0, rows[0]["netRApprox"])
        self.assertAlmostEqual(2.5, rows[0]["mfeRApprox"])
        self.assertAlmostEqual(-1.0, rows[0]["maeRApprox"])
        self.assertIsNone(rows[0]["marketRegime"])

    def test_attribution_separates_signal_cost_risk_and_evidence_limits(self) -> None:
        record = {
            "strategyId": "version_1",
            "metrics": {
                "tradeCount": 40,
                "profitFactor": 0.8,
                "averageNetR": -0.1,
                "maximumDrawdownR": 7.0,
                "costStress": {"averageNetR": -0.2},
            },
            "evidenceLevel": 2,
            "evidenceCompleteness": 0.7,
            "failureSummary": "Backtest gates failed",
        }
        result = attribute_archived_failure(record)

        self.assertEqual("signal_edge_failure", result["primaryFailureType"])
        self.assertIn("cost_amplification", result["secondaryFailureTypes"])
        self.assertIn("risk_model_failure", result["secondaryFailureTypes"])
        self.assertFalse(result["causalityProven"])
        self.assertTrue(result["primaryFailureLabelZh"])

    def test_generator_creates_all_required_outputs_and_preserves_nulls(self) -> None:
        report = generate_full_archived_strategy_analysis(
            self.root, generated_at="2026-07-15T00:00:00Z"
        )

        for relative_path in REQUIRED_OUTPUTS.values():
            self.assertTrue((self.root / relative_path).exists(), relative_path)
        self.assertGreaterEqual(report["coverageAudit"]["strategyIdentityCount"], 2)
        inventory = json.loads(
            (self.root / REQUIRED_OUTPUTS["inventoryJson"]).read_text(encoding="utf-8")
        )
        fixture = next(row for row in inventory["strategies"] if row["strategyId"] == "version_1")
        self.assertIsNone(fixture["metrics"].get("feesPaid"))
        self.assertFalse(report["safetyBoundary"]["backtestExecuted"])


if __name__ == "__main__":
    unittest.main()
