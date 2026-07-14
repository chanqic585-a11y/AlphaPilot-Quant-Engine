"""Build formal backtest evidence from the user-approved local warehouse only."""

from __future__ import annotations

import os
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

import pandas as pd

from alphapilot.evolution.registry.hashing import sha256_file, stable_hash
from alphapilot.evolution.workflow.types import StrategyDataContractRecord

from .canonical import canonicalize_asset, write_canonical_metadata
from .catalog import discover_raw_assets
from .checkpoint import write_json_atomic
from .official_history import OfficialCollectionResult, OfficialPartition
from .types import CanonicalAsset, RawDataAsset
from .warehouse import WarehouseLayout


LOCAL_SOURCE_ENDPOINT = "local://user-approved-history"
LOCAL_PROVENANCE_STATUS = "user_approved_local"
LOCAL_EXCHANGE_LABEL = "user_local"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _asset_collected_at(asset: RawDataAsset) -> str:
    return datetime.fromtimestamp(asset.modifiedAtNs / 1_000_000_000, UTC).isoformat()


def _normalise_swap_asset(asset: RawDataAsset) -> RawDataAsset:
    instrument = asset.instrumentId
    if asset.sourceGroup == "5m" and asset.symbol:
        instrument = f"{asset.symbol}-USDT-SWAP"
    return replace(
        asset,
        marketType="swap",
        instrumentId=instrument,
        provenanceStatus=LOCAL_PROVENANCE_STATUS,
        exchange=LOCAL_EXCHANGE_LABEL,
    )


def _required_timeframes(contract: StrategyDataContractRecord) -> tuple[str, ...]:
    values = (
        contract.contract.get("signalTimeframe"),
        contract.contract.get("executionTimeframe"),
        contract.contract.get("executionFallbackTimeframe"),
    )
    return tuple(dict.fromkeys(str(value).lower() for value in values if value))


def _funding_required(contract: StrategyDataContractRecord) -> bool:
    policy = contract.contract.get("costPolicy") or {}
    return bool(
        contract.contract.get("marketType") == "swap"
        and policy.get("fundingRequiredForSwap", True)
    )


def _rank_instrument(
    instrument: str,
    assets: list[RawDataAsset],
) -> tuple[int, int, str]:
    preferred = {"BTC-USDT-SWAP": 0, "ETH-USDT-SWAP": 1, "SOL-USDT-SWAP": 2}
    return (
        preferred.get(instrument, 3),
        -sum(int(asset.sizeBytes) for asset in assets),
        instrument,
    )


def _ensure_local_provenance_columns(
    canonical: CanonicalAsset,
    asset: RawDataAsset,
) -> CanonicalAsset:
    if not canonical.outputPath or not canonical.quality:
        return canonical
    path = Path(canonical.outputPath)
    frame = pd.read_parquet(path)
    changed = False
    expected = {
        "exchange": LOCAL_EXCHANGE_LABEL,
        "market_type": "swap",
        "instrument_id": str(asset.instrumentId),
        "timeframe": str(asset.timeframe),
        "source_endpoint": LOCAL_SOURCE_ENDPOINT,
        "collected_at": _asset_collected_at(asset),
    }
    for column, value in expected.items():
        if column not in frame.columns or not (frame[column].astype(str) == str(value)).all():
            frame[column] = value
            changed = True
    if changed:
        temporary = path.with_name(f"{path.name}.local.tmp")
        frame.to_parquet(temporary, index=False, compression="zstd")
        os.replace(temporary, path)
    content_hash = sha256_file(path)
    write_canonical_metadata(
        output_path=path,
        asset=asset,
        content_sha256=content_hash,
        quality=canonical.quality,
    )
    return replace(canonical, contentSha256=content_hash)


def _canonicalize_local_ohlcv(
    asset: RawDataAsset,
    layout: WarehouseLayout,
) -> tuple[OfficialPartition | None, bool, str | None]:
    canonical = canonicalize_asset(
        asset,
        output_root=layout.canonicalRoot,
        exchange=LOCAL_EXCHANGE_LABEL,
    )
    if canonical.status not in {"created", "existing"}:
        return None, False, canonical.error or canonical.status
    canonical = _ensure_local_provenance_columns(canonical, asset)
    quality = canonical.quality
    if (
        not canonical.outputPath
        or not canonical.contentSha256
        or quality is None
        or quality.errors
        or quality.gapEventCount
    ):
        return None, False, canonical.error or "local_ohlcv_quality_invalid"
    return (
        OfficialPartition(
            instrumentId=str(asset.instrumentId),
            timeframe=str(asset.timeframe),
            status="reused" if canonical.status == "existing" else "collected",
            rows=quality.rows,
            startTime=quality.startTime,
            endTime=quality.endTime,
            outputPath=canonical.outputPath,
            outputSha256=canonical.contentSha256,
            sourceEndpoint=LOCAL_SOURCE_ENDPOINT,
            requestCount=0,
            provenanceStatus=LOCAL_PROVENANCE_STATUS,
            reused=canonical.status == "existing",
        ),
        canonical.status == "existing",
        None,
    )


def _canonicalize_local_funding(
    asset: RawDataAsset,
    layout: WarehouseLayout,
) -> tuple[str | None, bool, str | None]:
    if asset.sha256 is None:
        asset.sha256 = sha256_file(Path(asset.sourcePath))
    digest = stable_hash(
        {
            "sourcePath": asset.relativePath,
            "sourceSha256": asset.sha256,
            "schema": "user_approved_local_funding_v1",
        },
        prefix="local_funding",
    )[-16:]
    output = (
        layout.canonicalRoot
        / LOCAL_EXCHANGE_LABEL
        / "swap"
        / "funding"
        / str(asset.instrumentId)
        / f"funding-{digest}.parquet"
    )
    if output.is_file():
        try:
            frame = pd.read_parquet(output)
            if not frame.empty and {
                "instrument_id",
                "funding_rate",
                "timestamp_ms",
                "source_endpoint",
                "collected_at",
            }.issubset(frame.columns):
                return str(output), True, None
        except Exception:  # noqa: BLE001 - corrupt cache is safely rebuilt below.
            pass
    try:
        raw = pd.read_excel(asset.sourcePath)
        timestamp_column = (
            "funding_time_ms"
            if "funding_time_ms" in raw.columns
            else "timestamp_ms"
            if "timestamp_ms" in raw.columns
            else None
        )
        if timestamp_column is None or "funding_rate" not in raw.columns:
            return None, False, "local_funding_columns_missing"
        frame = pd.DataFrame(
            {
                "instrument_id": str(asset.instrumentId),
                "funding_rate": pd.to_numeric(raw["funding_rate"], errors="coerce"),
                "timestamp_ms": pd.to_numeric(raw[timestamp_column], errors="coerce"),
            }
        ).dropna()
        frame["timestamp_ms"] = frame["timestamp_ms"].astype("int64")
        frame = frame.drop_duplicates(subset=["timestamp_ms"], keep="last").sort_values(
            "timestamp_ms"
        )
        if frame.empty:
            return None, False, "local_funding_empty"
        frame["source_endpoint"] = LOCAL_SOURCE_ENDPOINT
        frame["collected_at"] = _asset_collected_at(asset)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(f"{output.name}.tmp")
        frame.to_parquet(temporary, index=False, compression="zstd")
        os.replace(temporary, output)
        return str(output), False, None
    except Exception as exc:  # noqa: BLE001 - isolate a single local asset.
        return None, False, f"local_funding_failed:{type(exc).__name__}:{exc}"


class LocalFormalHistoryCollector:
    """Create immutable evidence without constructing a network client."""

    def __init__(
        self,
        *,
        layout: WarehouseLayout,
        stop_requested: Callable[[], bool] | None = None,
    ) -> None:
        self.layout = layout
        self.stop_requested = stop_requested or (lambda: False)

    def _checkpoint(
        self,
        contract: StrategyDataContractRecord,
        payload: dict[str, object],
    ) -> Path:
        path = (
            self.layout.checkpointRoot
            / "local-formal"
            / f"{contract.strategyDataContractId}.json"
        )
        write_json_atomic(path, payload)
        return path

    def collect(
        self,
        contract: StrategyDataContractRecord,
    ) -> OfficialCollectionResult:
        generated_at = _utc_now()
        required_timeframes = _required_timeframes(contract)
        universe_policy = contract.contract.get("universePolicy") or {}
        minimum_members = max(1, int(universe_policy.get("minimumMembers", 1)))
        target_members = max(
            minimum_members,
            int(universe_policy.get("targetMembers", minimum_members)),
        )
        assets = [
            _normalise_swap_asset(asset)
            for asset in discover_raw_assets(self.layout.rawRoot)
            if asset.selected
            and asset.dataKind in {"ohlcv", "funding"}
            and (asset.marketType == "swap" or asset.sourceGroup == "5m")
        ]
        ohlcv = {
            (str(asset.instrumentId), str(asset.timeframe)): asset
            for asset in assets
            if asset.dataKind == "ohlcv" and asset.timeframe
        }
        funding = {
            str(asset.instrumentId): asset
            for asset in assets
            if asset.dataKind == "funding"
        }
        instruments = sorted({instrument for instrument, _ in ohlcv})
        complete = [
            instrument
            for instrument in instruments
            if all((instrument, timeframe) in ohlcv for timeframe in required_timeframes)
            and (not _funding_required(contract) or instrument in funding)
        ]
        complete.sort(
            key=lambda instrument: _rank_instrument(
                instrument,
                [ohlcv[(instrument, timeframe)] for timeframe in required_timeframes],
            )
        )
        if len(complete) < minimum_members:
            checkpoint = self._checkpoint(
                contract,
                {
                    "status": "blocked",
                    "reason": "local_formal_universe_too_small",
                    "availableMembers": len(complete),
                    "minimumMembers": minimum_members,
                    "requiredTimeframes": list(required_timeframes),
                    "generatedAt": generated_at,
                },
            )
            return OfficialCollectionResult(
                status="blocked",
                strategyDataContractId=contract.strategyDataContractId,
                instrumentCount=len(complete),
                completedPartitionCount=0,
                reusedPartitionCount=0,
                failedPartitionCount=max(1, minimum_members - len(complete)),
                fundingFileCount=0,
                partitions=(),
                checkpointPath=str(checkpoint),
                generatedAt=generated_at,
            )

        selected_instruments: list[str] = []
        partitions: list[OfficialPartition] = []
        funding_paths: list[str] = []
        rejected: dict[str, str] = {}
        paused = False
        inspected_count = 0
        for instrument in complete:
            if len(selected_instruments) >= target_members:
                break
            if self.stop_requested():
                paused = True
                break
            inspected_count += 1
            candidate_partitions: list[OfficialPartition] = []
            failed_reason: str | None = None
            for timeframe in required_timeframes:
                partition, _reused, error = _canonicalize_local_ohlcv(
                    ohlcv[(instrument, timeframe)],
                    self.layout,
                )
                if partition is None:
                    failed_reason = error or "local_ohlcv_invalid"
                    break
                candidate_partitions.append(partition)
            funding_path: str | None = None
            if failed_reason is None and _funding_required(contract):
                funding_path, _funding_reused, failed_reason = _canonicalize_local_funding(
                    funding[instrument],
                    self.layout,
                )
            if failed_reason:
                rejected[instrument] = failed_reason
                self._checkpoint(
                    contract,
                    {
                        "status": "running",
                        "source": "user_approved_local_market_data",
                        "selectedInstruments": selected_instruments,
                        "requiredTimeframes": list(required_timeframes),
                        "rejectedInstruments": rejected,
                        "inspectedInstrumentCount": inspected_count,
                        "generatedAt": generated_at,
                    },
                )
                continue
            selected_instruments.append(instrument)
            partitions.extend(candidate_partitions)
            if funding_path:
                funding_paths.append(funding_path)
            self._checkpoint(
                contract,
                {
                    "status": "running",
                    "source": "user_approved_local_market_data",
                    "selectedInstruments": selected_instruments,
                    "requiredTimeframes": list(required_timeframes),
                    "rejectedInstruments": rejected,
                    "inspectedInstrumentCount": inspected_count,
                    "generatedAt": generated_at,
                },
            )

        status = "paused" if paused else "completed"
        if not paused and len(selected_instruments) < minimum_members:
            status = "blocked"
        checkpoint = self._checkpoint(
            contract,
            {
                "status": status,
                "source": "user_approved_local_market_data",
                "selectedInstruments": selected_instruments,
                "requiredTimeframes": list(required_timeframes),
                "rejectedInstruments": rejected,
                "inspectedInstrumentCount": inspected_count,
                "generatedAt": generated_at,
            },
        )
        completed_partitions = len(partitions) if status == "completed" else 0
        return OfficialCollectionResult(
            status=status,
            strategyDataContractId=contract.strategyDataContractId,
            instrumentCount=len(selected_instruments),
            completedPartitionCount=completed_partitions,
            reusedPartitionCount=sum(1 for item in partitions if item.reused),
            failedPartitionCount=(
                0 if status in {"completed", "paused"} else max(1, minimum_members - len(selected_instruments))
            ),
            fundingFileCount=len(funding_paths) if status == "completed" else 0,
            partitions=tuple(partitions),
            checkpointPath=str(checkpoint),
            generatedAt=generated_at,
            fundingPaths=tuple(funding_paths),
        )
