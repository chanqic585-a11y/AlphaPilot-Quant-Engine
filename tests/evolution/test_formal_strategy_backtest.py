from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from alphapilot.evolution.evaluation.formal_strategy_backtest import (
    run_formal_strategy_backtest,
)
from alphapilot.evolution.evaluation.fixed_r_path import (
    evaluate_prepared_fixed_r_path as evaluate_prepared_fixed_r_path_real,
    prepare_fixed_r_execution_path as prepare_fixed_r_execution_path_real,
)
from alphapilot.evolution.registry.hashing import sha256_file, stable_hash
from alphapilot.evolution.registry.types import DataSnapshotRecord
from alphapilot.evolution.workflow.types import (
    EvaluationBindingRecord,
    StrategyVersionRecord,
)


class FormalStrategyBacktestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.canonical = self.root / "canonical"
        self.manifests = self.root / "manifests"
        self.contract_id = "strategy_data_contract_formal_test"
        self.snapshot_id = "data_snapshot_formal_test"
        self.binding_id = "evaluation_binding_formal_test"
        self.symbols = ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP"]
        files: list[dict[str, object]] = []
        for symbol_index, symbol in enumerate(self.symbols):
            for timeframe, minutes, rows in (
                ("4h", 240, 400),
                ("15m", 15, 6400),
                ("5m", 5, 19200),
            ):
                dates = pd.date_range(
                    "2024-01-01", periods=rows, freq=f"{minutes}min", tz="UTC"
                )
                base = 100.0 + symbol_index * 20
                sequence = pd.Series(range(rows), dtype="float64")
                close = base + (sequence % 8) * 0.05
                frame = pd.DataFrame(
                    {
                        "timestamp_ms": dates.as_unit("ms").astype("int64"),
                        "date": dates,
                        "open": close,
                        "high": close * 1.12,
                        "low": close * 0.98,
                        "close": close * 1.01,
                        "volume": 1000.0,
                        "confirmed": 1,
                        "exchange": "okx",
                        "market_type": "swap",
                        "instrument_id": symbol,
                        "timeframe": timeframe,
                    }
                )
                path = (
                    self.canonical
                    / "okx"
                    / "swap"
                    / "ohlcv"
                    / symbol
                    / timeframe
                    / "fixture.parquet"
                )
                path.parent.mkdir(parents=True, exist_ok=True)
                frame.to_parquet(path, index=False)
                files.append(
                    {
                        "path": path.relative_to(self.canonical).as_posix(),
                        "size": path.stat().st_size,
                        "sha256": sha256_file(path),
                    }
                )
            funding_path = (
                self.canonical
                / "okx"
                / "swap"
                / "funding"
                / symbol
                / "fixture.parquet"
            )
            funding_path.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(
                {
                    "instrument_id": [symbol],
                    "timestamp_ms": [1704067200000],
                    "funding_rate": [0.0001],
                }
            ).to_parquet(funding_path, index=False)
            files.append(
                {
                    "path": funding_path.relative_to(self.canonical).as_posix(),
                    "size": funding_path.stat().st_size,
                    "sha256": sha256_file(funding_path),
                }
            )
        self.snapshot = DataSnapshotRecord(
            dataSnapshotId=self.snapshot_id,
            source="okx_public_official",
            exchange="okx",
            marketType="swap",
            timeframe="multi",
            startTime="2024-01-01T00:00:00+00:00",
            endTime="2024-03-01T00:00:00+00:00",
            pointInTimeCutoff="2024-03-01T00:00:00+00:00",
            manifest={
                "dataSnapshotId": self.snapshot_id,
                "manifestHash": "snapshot_hash_formal_test",
                "files": files,
                "metadata": {
                    "formalResearchEligible": True,
                    "pointInTimeValidated": True,
                },
            },
            contentHash="snapshot_hash_formal_test",
        )
        self.version = StrategyVersionRecord(
            strategyVersionId="strategy_version_formal_test",
            strategyFamilyId="strategy_family_formal_test",
            parentStrategyVersionId=None,
            strategyCandidateId=None,
            displayName="Formal Alpha191 test",
            sourceType="test",
            status="registered",
            definition={
                "timeframe": "4h",
                "targetR": 2.0,
                "backtest": {"adapterId": "alpha191_crypto_subset_v13_5_23"},
            },
            parameters={
                "overlayId": "a191_short_exhaustion_quality_v01",
                "stopLossPct": 0.05,
                "horizonBars": 12,
            },
            modelArtifactId=None,
            contentHash="strategy_hash_formal_test",
        )
        self.manifest_dir = self.manifests / self.contract_id / self.snapshot_id
        self.manifest_dir.mkdir(parents=True)
        self.hashes = {
            "walkForwardManifestHash": "walk_forward_formal_test",
            "holdoutManifestHash": "holdout_formal_test",
            "lockedOosManifestHash": "locked_oos_formal_test",
            "regimeManifestHash": "regime_formal_test",
            "costManifestHash": "cost_formal_test",
        }
        manifests = {
            "walk-forward.json": {
                "manifestHash": self.hashes["walkForwardManifestHash"],
                "folds": [
                    {"fold": 1, "testStart": 120, "testEndExclusive": 180},
                    {"fold": 2, "testStart": 180, "testEndExclusive": 240},
                    {"fold": 3, "testStart": 240, "testEndExclusive": 300},
                ],
            },
            "holdout.json": {
                "manifestHash": self.hashes["holdoutManifestHash"],
                "trainingSymbols": self.symbols[:2],
                "holdoutSymbols": self.symbols[2:],
            },
            "locked-oos.json": {
                "manifestHash": self.hashes["lockedOosManifestHash"],
                "lockedStartIndex": 340,
                "lockedStartTimestampMs": int(
                    pd.Timestamp("2024-02-26 16:00", tz="UTC").timestamp() * 1000
                ),
            },
            "regime.json": {
                "manifestHash": self.hashes["regimeManifestHash"],
                "observedRegimes": ["bull", "range"],
            },
            "cost.json": {
                "manifestHash": self.hashes["costManifestHash"],
                "feeRate": 0.0005,
                "slippageRate": 0.0002,
                "latencyBars": [0, 1, 2],
                "stressMultipliers": [1.0, 2.0],
                "targetR": 2.0,
            },
        }
        for name, payload in manifests.items():
            (self.manifest_dir / name).write_text(
                json.dumps(payload), encoding="utf-8"
            )
        binding_core = {
            "workflowRunId": "workflow_run_formal_test",
            "strategyDataContractId": self.contract_id,
            "dataSnapshotId": self.snapshot_id,
            "walkForwardManifestHash": self.hashes["walkForwardManifestHash"],
            "holdoutManifestHash": self.hashes["holdoutManifestHash"],
            "lockedOosManifestHash": self.hashes["lockedOosManifestHash"],
            "gateProfileId": "gate_profile_formal_test",
            "runnerVersion": "formal_fixed_2r_v1",
            "costModel": {"feeRate": 0.0005, "slippageRate": 0.0002},
            "evidence": {
                "canonicalRoot": str(self.canonical),
                "regimeManifestHash": self.hashes["regimeManifestHash"],
                "costManifestHash": self.hashes["costManifestHash"],
                "signalTimeframe": "4h",
                "executionTimeframe": "15m",
            },
        }
        self.binding = EvaluationBindingRecord(
            evaluationBindingId=self.binding_id,
            contentHash=stable_hash(binding_core, prefix="evaluation_binding"),
            **binding_core,
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_adapter_uses_only_snapshot_files_and_preserves_all_manifest_hashes(self) -> None:
        def fake_signals(panel: pd.DataFrame, *, overlay_id: str) -> pd.DataFrame:
            rows = []
            for pair, group in panel.groupby("pair"):
                for index in (60, 130, 190, 250, 350):
                    row = group.iloc[index]
                    rows.append(
                        {
                            "pair": pair,
                            "timeframe": "4h",
                            "signalDate": row["date"],
                            "signalTimestampMs": int(row["date"].timestamp() * 1000),
                            "direction": "long",
                            "setupName": "fixture_signal",
                            "overlayId": overlay_id,
                        }
                    )
            return pd.DataFrame(rows)

        with patch(
            "alphapilot.evolution.evaluation.formal_strategy_backtest.build_alpha191_observer_signals",
            side_effect=fake_signals,
        ):
            result = run_formal_strategy_backtest(
                strategy_version=self.version,
                evaluation_binding=self.binding,
                snapshot=self.snapshot,
                manifest_root=self.manifests,
            )

        self.assertGreater(result.metrics["tradeCount"], 0)
        self.assertGreaterEqual(result.metrics["holdoutTradeCount"], 1)
        self.assertGreaterEqual(result.metrics["lockedTradeCount"], 1)
        self.assertEqual(result.evidence["dataSnapshotId"], self.snapshot_id)
        self.assertEqual(result.evidence["evaluationBindingId"], self.binding_id)
        for key, expected in self.hashes.items():
            self.assertEqual(result.evidence[key], expected)
        self.assertEqual(
            set(result.metrics["bySplit"]),
            {"development", "walk_forward", "holdout", "locked_oos"},
        )
        self.assertTrue(result.checks["snapshotBound"])
        self.assertTrue(result.checks["targetRFixed"])
        self.assertIn("costStress", result.checks)
        self.assertIn("stability", result.checks)
        self.assertNotIn(str(self.root / "unregistered"), json.dumps(result.evidence))

    def test_adapter_fails_closed_when_binding_hash_does_not_match_manifest(self) -> None:
        broken = EvaluationBindingRecord(
            **{
                **self.binding.__dict__,
                "holdoutManifestHash": "holdout_wrong",
            }
        )
        with self.assertRaisesRegex(ValueError, "manifest_hash_mismatch:holdout"):
            run_formal_strategy_backtest(
                strategy_version=self.version,
                evaluation_binding=broken,
                snapshot=self.snapshot,
                manifest_root=self.manifests,
            )

    def test_adapter_prepares_execution_path_once_per_instrument(self) -> None:
        source = pd.Timestamp("2024-01-02 00:00", tz="UTC")
        signals = pd.DataFrame(
            [
                {
                    "pair": "ETH/USDT:USDT",
                    "timeframe": "4h",
                    "signalDate": source + pd.Timedelta(hours=offset),
                    "signalTimestampMs": int(
                        (source + pd.Timedelta(hours=offset)).timestamp() * 1000
                    ),
                    "direction": "long",
                    "setupName": "fixture_signal",
                    "overlayId": "a191_short_exhaustion_quality_v01",
                }
                for offset in (0, 4, 8)
            ]
        )
        prepare_calls: list[int] = []

        def capture_prepare(execution_frame, funding_frame=None):
            prepare_calls.append(id(execution_frame))
            return prepare_fixed_r_execution_path_real(
                execution_frame, funding_frame
            )

        with patch(
            "alphapilot.evolution.evaluation.formal_strategy_backtest.build_alpha191_observer_signals",
            return_value=signals,
        ), patch(
            "alphapilot.evolution.evaluation.formal_strategy_backtest.prepare_fixed_r_execution_path",
            side_effect=capture_prepare,
            create=True,
        ):
            result = run_formal_strategy_backtest(
                strategy_version=self.version,
                evaluation_binding=self.binding,
                snapshot=self.snapshot,
                manifest_root=self.manifests,
            )

        self.assertGreater(result.metrics["tradeCount"], 0)
        self.assertEqual(len(prepare_calls), 1)

    def test_short_cycle_dispatch_uses_signal_stop_and_converted_horizon(self) -> None:
        version = StrategyVersionRecord(
            **{
                **self.version.__dict__,
                "displayName": "15m 放量突破测试",
                "definition": {
                    "signalEngine": "short_cycle_v1",
                    "signalFamily": "breakout_volume_long",
                    "timeframe": "15m",
                    "direction": "long",
                    "targetR": 2.0,
                },
                "parameters": {
                    "lookback": 20,
                    "breakout_buffer": 0.0,
                    "rsi_max": 100,
                    "volume_min": 1.0,
                    "stop_atr": 1.4,
                    "max_hold": 16,
                },
            }
        )
        binding = EvaluationBindingRecord(
            **{
                **self.binding.__dict__,
                "evidence": {
                    **self.binding.evidence,
                    "signalTimeframe": "15m",
                    "executionTimeframe": "5m",
                },
            }
        )
        source_timestamp = int(
            pd.Timestamp("2024-01-02 00:00", tz="UTC").timestamp() * 1000
        )
        signals = pd.DataFrame(
            [
                {
                    "pair": "ETH/USDT:USDT",
                    "timeframe": "15m",
                    "signalDate": pd.Timestamp(
                        source_timestamp + 900_000 - 1, unit="ms", tz="UTC"
                    ).isoformat(),
                    "signalTimestampMs": source_timestamp + 900_000 - 1,
                    "sourceTimestampMs": source_timestamp,
                    "signalIndex": 96,
                    "direction": "long",
                    "setupName": "breakout_volume_long",
                    "stopLossPct": 0.0125,
                }
            ]
        )
        configs = []

        def capture_path(**kwargs):
            configs.append(kwargs["config"])
            return evaluate_prepared_fixed_r_path_real(**kwargs)

        with patch(
            "alphapilot.evolution.evaluation.formal_strategy_backtest.build_short_cycle_formal_signals",
            return_value=signals,
        ) as short_builder, patch(
            "alphapilot.evolution.evaluation.formal_strategy_backtest.build_alpha191_observer_signals"
        ) as alpha_builder, patch(
            "alphapilot.evolution.evaluation.formal_strategy_backtest.evaluate_prepared_fixed_r_path",
            side_effect=capture_path,
        ):
            result = run_formal_strategy_backtest(
                strategy_version=version,
                evaluation_binding=binding,
                snapshot=self.snapshot,
                manifest_root=self.manifests,
            )

        short_builder.assert_called_once()
        alpha_builder.assert_not_called()
        self.assertGreater(result.metrics["tradeCount"], 0)
        self.assertTrue(configs)
        self.assertEqual({config.stopLossPct for config in configs}, {0.0125})
        self.assertEqual({config.horizonBars for config in configs}, {48})

    def test_opt_in_trend_runner_policy_is_passed_to_formal_execution_path(self) -> None:
        version = StrategyVersionRecord(
            **{
                **self.version.__dict__,
                "definition": {
                    **self.version.definition,
                    "exitPolicy": "two_r_half_atr_runner_v1",
                },
            }
        )
        captured = []

        def fake_signals(panel: pd.DataFrame, *, overlay_id: str) -> pd.DataFrame:
            row = panel.sort_values("date").iloc[60]
            return pd.DataFrame([
                {
                    "pair": row["pair"],
                    "timeframe": "4h",
                    "signalDate": row["date"],
                    "signalTimestampMs": int(row["date"].timestamp() * 1000),
                    "direction": "long",
                    "setupName": "fixture_signal",
                    "overlayId": overlay_id,
                }
            ])

        def capture_path(**kwargs):
            captured.append(kwargs["config"])
            return evaluate_prepared_fixed_r_path_real(**kwargs)

        with patch(
            "alphapilot.evolution.evaluation.formal_strategy_backtest.build_alpha191_observer_signals",
            side_effect=fake_signals,
        ), patch(
            "alphapilot.evolution.evaluation.formal_strategy_backtest.evaluate_prepared_fixed_r_path",
            side_effect=capture_path,
        ):
            result = run_formal_strategy_backtest(
                strategy_version=version,
                evaluation_binding=self.binding,
                snapshot=self.snapshot,
                manifest_root=self.manifests,
            )

        self.assertTrue(captured)
        self.assertEqual({config.exitPolicy for config in captured}, {"two_r_half_atr_runner_v1"})
        self.assertEqual(result.evidence["exitPolicy"], "two_r_half_atr_runner_v1")
        self.assertEqual(result.evidence["plannedTargetR"], 2.0)
        self.assertIn("averageGrossR", result.metrics)
        self.assertIn("averageNetR", result.metrics)
        self.assertIn("partialTargetCount", result.metrics)

    def test_unknown_signal_engine_fails_closed(self) -> None:
        version = StrategyVersionRecord(
            **{
                **self.version.__dict__,
                "definition": {
                    **self.version.definition,
                    "signalEngine": "unknown_engine",
                },
            }
        )

        with self.assertRaisesRegex(
            ValueError, "formal_signal_engine_not_supported:unknown_engine"
        ):
            run_formal_strategy_backtest(
                strategy_version=version,
                evaluation_binding=self.binding,
                snapshot=self.snapshot,
                manifest_root=self.manifests,
            )


if __name__ == "__main__":
    unittest.main()
