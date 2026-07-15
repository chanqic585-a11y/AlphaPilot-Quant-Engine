"""Deterministic preregistration builder for the bounded Phase 3C campaign."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import sha256_file

from .campaign_contract import CandidateSpec, build_campaign_preregistration


UTC = timezone.utc


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def calculate_time_boundaries(
    catalog: Mapping[str, Any], timeframes: Iterable[str]
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for timeframe in timeframes:
        rows = [
            row
            for row in catalog.get("datasets", [])
            if row.get("dataType") == "ohlcv" and row.get("timeframe") == timeframe
        ]
        if not rows:
            raise ValueError(f"no OHLCV datasets for timeframe {timeframe}")
        start = max(_timestamp(str(row["startTime"])) for row in rows)
        end = min(_timestamp(str(row["endTime"])) for row in rows)
        if end <= start:
            raise ValueError(f"no common OHLCV coverage for timeframe {timeframe}")
        duration = end - start
        development_end = start + duration * 0.55
        walk_forward_end = start + duration * 0.80
        fold_duration = (walk_forward_end - development_end) / 5
        folds = []
        for index in range(5):
            fold_start = development_end + fold_duration * index
            fold_end = walk_forward_end if index == 4 else development_end + fold_duration * (index + 1)
            folds.append(
                {
                    "foldId": f"fold_{index + 1:03d}",
                    "start": _iso(fold_start),
                    "end": _iso(fold_end),
                }
            )
        result[timeframe] = {
            "developmentStart": _iso(start),
            "developmentEnd": _iso(development_end),
            "walkForwardStart": _iso(development_end),
            "walkForwardEnd": _iso(walk_forward_end),
            "holdoutStart": _iso(walk_forward_end),
            "holdoutEnd": _iso(end),
            "walkForwardFolds": folds,
            "coveragePolicy": "intersection_of_frozen_instrument_histories",
        }
    return result


def build_default_candidates() -> list[CandidateSpec]:
    candidates: list[CandidateSpec] = []
    for direction in ("long", "short"):
        candidates.append(
            CandidateSpec(
                candidateId=f"volatility_compression_breakout_1h_{direction}_v1",
                familyId="volatility_compression_breakout_1h",
                marketMechanismId="volatility_compression_breakout",
                direction=direction,
                timeframe="1h",
                causalRationale="A low-volatility state can precede directional range expansion when price and volume confirm the break.",
                eventDefinition={
                    "breakoutBars": 20,
                    "quantileWindow": 720,
                    "compressionQuantile": 0.25,
                    "minimumVolumeRatio": 1.05,
                },
                invalidation="Price reaches the fixed initial ATR stop before the target.",
                stopAtr=1.5,
                targetR=2.2,
                maximumHoldBars=48,
                requiredData=("ohlcv",),
                expectedFailureRegimes=("false_breakout", "illiquid_gap", "range_reentry"),
            )
        )
    for direction in ("long", "short"):
        candidates.append(
            CandidateSpec(
                candidateId=f"idiosyncratic_shock_reversion_4h_{direction}_v1",
                familyId="idiosyncratic_shock_reversion_4h",
                marketMechanismId="idiosyncratic_shock_reversion",
                direction=direction,
                timeframe="4h",
                causalRationale="A large asset-specific return residual may mean-revert after a same-direction exhaustion candle.",
                eventDefinition={"shockBars": 3, "zscoreWindow": 180, "zscoreThreshold": 2.0},
                invalidation="The asset-specific move continues through the fixed initial ATR stop.",
                stopAtr=1.25,
                targetR=2.0,
                maximumHoldBars=18,
                requiredData=("ohlcv", "btc_benchmark_ohlcv"),
                expectedFailureRegimes=("persistent_idiosyncratic_trend", "listing_event", "liquidity_shock"),
            )
        )
    for direction in ("long", "short"):
        candidates.append(
            CandidateSpec(
                candidateId=f"funding_crowding_reversal_4h_{direction}_v1",
                familyId="funding_crowding_reversal_4h",
                marketMechanismId="funding_crowding_reversal",
                direction=direction,
                timeframe="4h",
                causalRationale="Extreme perpetual funding can identify crowded positioning that may reverse after price exhaustion.",
                eventDefinition={"fundingWindow": 180, "fundingZscore": 1.75, "confirmationBars": 3},
                invalidation="Crowding persists and price reaches the fixed initial ATR stop.",
                stopAtr=1.25,
                targetR=2.0,
                maximumHoldBars=24,
                requiredData=("ohlcv", "funding"),
                expectedFailureRegimes=("persistent_trend", "funding_basis_shift", "cross_exchange_proxy_divergence"),
            )
        )
    return candidates


def _single_json(directory: Path, pattern: str) -> Path:
    files = sorted(directory.glob(pattern))
    if len(files) != 1:
        raise RuntimeError(f"expected exactly one {pattern} in {directory}, found {len(files)}")
    return files[0]


def preregister_campaign(repo_root: Path | str, *, code_commit: str) -> tuple[Path, dict[str, Any]]:
    repo = Path(repo_root).resolve()
    shortlist_path = _single_json(repo / "research" / "factor_shortlists", "factor_shortlist_*.json")
    shortlist = json.loads(shortlist_path.read_text(encoding="utf-8"))
    snapshot_id = str(shortlist["dataSnapshotHash"])
    snapshot_path = repo / "research" / "data_snapshots" / f"{snapshot_id}.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    catalog_path = repo / "reports" / "backtest_screening" / "data_readiness" / "dataset_catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    mechanism_path = repo / "reports" / "factor_lab" / "factor_market_mechanism_matrix.json"
    mechanism_matrix = json.loads(mechanism_path.read_text(encoding="utf-8"))
    ready = {row["mechanismId"] for row in mechanism_matrix["mechanisms"] if row.get("ready")}
    candidates = build_default_candidates()
    missing = {candidate.marketMechanismId for candidate in candidates} - ready
    if missing:
        raise RuntimeError(f"candidate mechanisms are not data-ready: {sorted(missing)}")
    source_names = (
        "campaign_contract.py",
        "campaign_metrics.py",
        "campaign_preregistration.py",
        "campaign_runner.py",
        "campaign_signals.py",
    )
    source_hashes = {
        name: sha256_file(repo / "alphapilot" / "research_screening" / name)
        for name in source_names
    }
    instruments = tuple(str(value) for value in snapshot["instruments"])
    payload = build_campaign_preregistration(
        external_reference_manifest_hash=str(shortlist["externalReferenceManifestHash"]),
        data_snapshot_hash=snapshot_id,
        factor_shortlist_hash=str(shortlist["factorShortlistId"]),
        factor_registry_hash=str(shortlist["factorRegistryHash"]),
        candidates=candidates,
        time_boundaries=calculate_time_boundaries(catalog, ("1h", "4h")),
        code_commit=code_commit,
        universe_policy={
            "mode": "frozen_time_series_instruments",
            "instruments": list(instruments),
            "pitStatus": snapshot["pitStatus"],
            "crossSectionalUse": "disabled",
        },
        implementation_source_hashes=source_hashes,
    )
    output = repo / "research" / "preregistrations" / f"{payload['campaignId']}.json"
    if output.exists():
        existing = json.loads(output.read_text(encoding="utf-8"))
        if existing != payload:
            raise RuntimeError(f"immutable preregistration already exists with different content: {output}")
    else:
        write_json_atomic(output, payload)
    return output, payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--code-commit", required=True)
    args = parser.parse_args()
    path, payload = preregister_campaign(args.repo, code_commit=args.code_commit)
    print(json.dumps({"campaignId": payload["campaignId"], "preregistrationHash": payload["preregistrationHash"], "path": str(path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
