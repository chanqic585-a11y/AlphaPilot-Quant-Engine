"""Historical point-in-time investable-universe snapshots."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("PIT timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


def build_pit_snapshot(
    records: list[dict[str, Any]],
    preregistered_rule: dict[str, Any],
) -> dict[str, Any]:
    if preregistered_rule.get("sourceMode") == "current_topn_backfill":
        raise ValueError("current TopN cannot backfill historical PIT membership")
    snapshot_text = str(preregistered_rule["snapshotTimeUtc"])
    snapshot_time = _parse(snapshot_text)
    rows: list[dict[str, Any]] = []
    for source in sorted(records, key=lambda row: str(row["instrumentId"])):
        listed_at = _parse(str(source["listedAt"]))
        delisted_at = _parse(str(source["delistedAt"])) if source.get("delistedAt") else None
        available_at = _parse(str(source["availableAt"]))
        listing_age_days = max(0, (snapshot_time - listed_at).days)
        reason = "符合预注册 PIT 规则"
        included = True
        checks = [
            (available_at <= snapshot_time, "快照时点尚不可得"),
            (listed_at <= snapshot_time, "快照时点尚未上市"),
            (delisted_at is None or delisted_at > snapshot_time, "快照时点已经下架"),
            (source.get("tradingState") == "live", "快照时点不可交易"),
            (source.get("quoteCurrency") == "USDT", "不是 USDT 合约"),
            (source.get("instrumentType") == "perpetual", "不是永续合约"),
            (
                listing_age_days >= int(preregistered_rule.get("minimumListingAgeDays", 0)),
                "上市时长不足",
            ),
            (
                float(source.get("quoteVolume24h") or 0)
                >= float(preregistered_rule.get("minimumQuoteVolume24h", 0)),
                "24h 成交量不足",
            ),
            (
                float(source.get("openInterestQuote") or 0)
                >= float(preregistered_rule.get("minimumOpenInterestQuote", 0)),
                "持仓量不足",
            ),
            (
                float(
                    source["spreadBpsOrFormalProxy"]
                    if source.get("spreadBpsOrFormalProxy") is not None
                    else float("inf")
                )
                <= float(preregistered_rule.get("maximumSpreadBps", float("inf"))),
                "点差超限",
            ),
            (source.get("dataQualityStatus") == "passed", "数据质量未通过"),
            (bool(source.get("ohlcvComplete")), "核心 OHLCV 不完整"),
        ]
        for passed, failed_reason in checks:
            if not passed:
                included = False
                reason = failed_reason
                break
        rows.append(
            {
                "snapshotTimeUtc": snapshot_text,
                "instrumentId": source["instrumentId"],
                "listedAt": source["listedAt"],
                "delistedAt": source.get("delistedAt"),
                "tradingState": source.get("tradingState"),
                "quoteVolume24h": source.get("quoteVolume24h"),
                "openInterestQuote": source.get("openInterestQuote"),
                "spreadBpsOrFormalProxy": source.get("spreadBpsOrFormalProxy"),
                "listingAgeDays": listing_age_days,
                "dataQualityStatus": source.get("dataQualityStatus"),
                "included": included,
                "reasonZh": reason,
                "sourceHashes": list(source.get("sourceHashes") or []),
                "availableAt": source["availableAt"],
            }
        )
    return {
        "snapshotTimeUtc": snapshot_text,
        "sourceMode": preregistered_rule.get("sourceMode"),
        "currentTopNBackfill": False,
        "rowCount": len(rows),
        "includedCount": sum(1 for row in rows if row["included"]),
        "rows": rows,
    }
