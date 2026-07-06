"""Build read-only runtime contract payloads for AlphaPilot consoles.

The runtime contract is a local file bridge. It standardizes strategy status,
signal tape, and paper observation data for the desktop and mobile consoles.
It does not call exchanges, use API keys, read accounts, create orders, or
trade automatically.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

VERSION = "V13.7.1"
SOURCE = "alphapilot_runtime_contract_v13_7_1"

DEFAULT_REPORTS_DIR = Path("reports")
DEFAULT_RUNTIME_STATUS = DEFAULT_REPORTS_DIR / "runtime_status.json"
DEFAULT_SIGNAL_TAPE = DEFAULT_REPORTS_DIR / "signal_tape.json"
DEFAULT_PAPER_LEDGER = DEFAULT_REPORTS_DIR / "paper_observation_ledger.json"

PRIMARY_PACKAGE = DEFAULT_REPORTS_DIR / "v13_5_21_local_paper_refresh_candidate_package.json"
PRIMARY_REPORT = DEFAULT_REPORTS_DIR / "v13_5_21_local_paper_refresh_candidate_report.json"
PRIMARY_SIGNALS = DEFAULT_REPORTS_DIR / "v13_5_20_best_exit_aware_policy_selected_signals.json"
PRIMARY_LEDGER = DEFAULT_REPORTS_DIR / "v13_5_21_local_paper_refresh_candidate_ledger.json"
OBSERVER_REPORT = DEFAULT_REPORTS_DIR / "v13_5_23_alpha191_crypto_subset_replay_report.json"


SAFETY_BOUNDARY = {
    "localFileBridgeOnly": True,
    "usesApiKey": False,
    "tradeApiUsed": False,
    "withdrawApiUsed": False,
    "readsRealAccount": False,
    "readsRealPositions": False,
    "createsOrders": False,
    "exchangeDryRunApproved": False,
    "liveTradingApproved": False,
    "autoTrading": False,
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def read_json(path: Path, fallback: Any = None) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return fallback


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if hasattr(value, "item"):
        try:
            return json_safe(value.item())
        except Exception:
            return str(value)
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _safe_int(value: Any) -> int | None:
    number = _safe_float(value)
    return int(number) if number is not None else None


def _latest_rows(rows: list[dict[str, Any]], date_key: str, limit: int) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda item: str(item.get(date_key) or ""), reverse=True)[:limit]


def _build_primary_strategy(package: dict[str, Any] | None, report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not package:
        return None
    metrics = (report or {}).get("ledgerMetrics") if isinstance((report or {}).get("ledgerMetrics"), dict) else {}
    gate = (report or {}).get("gate") if isinstance((report or {}).get("gate"), dict) else {}
    return {
        "strategyId": package.get("packageId") or "v13_5_21_local_paper_refresh_candidate_package",
        "strategyTitle": package.get("candidateId") or "V13.5.21 Local Paper Refresh Candidate",
        "strategyVersion": package.get("version"),
        "candidateId": package.get("candidateId"),
        "selectedPolicyId": package.get("selectedPolicyId"),
        "status": "local_paper_ready" if gate.get("passed") else "research_only",
        "timeframe": _candidate_timeframe(package.get("candidateId")),
        "direction": _candidate_direction(package.get("candidateId")),
        "targetRMultiple": package.get("targetRMultiple"),
        "stopLossPct": package.get("stopLossPct"),
        "riskPerSignalPct": package.get("riskPerSignalPct"),
        "maxConcurrentPositions": package.get("maxConcurrentPositions"),
        "selectedSignalCount": package.get("selectedSignalCount"),
        "metrics": {
            "filledSignalCount": metrics.get("filledSignalCount"),
            "winRatePct": metrics.get("winRatePct"),
            "profitFactor": metrics.get("profitFactor"),
            "rewardRiskRatio": metrics.get("rewardRiskRatio"),
            "totalReturnPct": metrics.get("totalReturnPct"),
            "maxDrawdownPct": metrics.get("maxDrawdownPct"),
            "finalEquity": metrics.get("finalEquity"),
        },
        "gate": gate,
        "sourceReport": str(PRIMARY_REPORT),
        "sourcePackage": str(PRIMARY_PACKAGE),
        "safetyBoundary": {
            "localSimulationOnly": bool(package.get("localSimulationOnly", True)),
            "exchangeDryRunApproved": bool(package.get("exchangeDryRunApproved", False)),
            "liveTradingApproved": bool(package.get("liveTradingApproved", False)),
            "orderCreationAllowed": False,
        },
    }


def _build_observer_strategy(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    candidate = report.get("bestRawCandidate") if isinstance(report.get("bestRawCandidate"), dict) else {}
    metrics = candidate.get("metrics") if isinstance(candidate.get("metrics"), dict) else {}
    decision = report.get("decision") if isinstance(report.get("decision"), dict) else {}
    return {
        "strategyId": "v13_5_23_alpha191_crypto_subset_observer",
        "strategyTitle": candidate.get("candidateId") or "V13.5.23 Alpha191 Crypto-Safe Subset Observer",
        "strategyVersion": report.get("version"),
        "candidateId": candidate.get("candidateId"),
        "selectedPolicyId": (report.get("bestExitAwarePolicy") or {}).get("policyId")
        if isinstance(report.get("bestExitAwarePolicy"), dict)
        else None,
        "status": "research_only",
        "timeframe": _candidate_timeframe(candidate.get("candidateId")),
        "direction": _candidate_direction(candidate.get("candidateId")),
        "targetRMultiple": candidate.get("targetRMultiple"),
        "stopLossPct": candidate.get("stopLossPct"),
        "riskPerSignalPct": None,
        "maxConcurrentPositions": None,
        "selectedSignalCount": (report.get("bestExitAwarePolicy") or {}).get("selectedSignalCount")
        if isinstance(report.get("bestExitAwarePolicy"), dict)
        else None,
        "metrics": {
            "tradeCount": metrics.get("tradeCount"),
            "winRatePct": metrics.get("winRatePct"),
            "profitFactor": metrics.get("profitFactor"),
            "rewardRiskRatio": metrics.get("rewardRiskRatio"),
            "maxDrawdownPct": metrics.get("maxDrawdownPct"),
        },
        "gate": {
            "rawReplayGatePassed": decision.get("rawReplayGatePassed"),
            "exitAwareGatePassed": decision.get("exitAwareGatePassed"),
            "localPaperGatePassed": decision.get("localPaperGatePassed"),
        },
        "sourceReport": str(OBSERVER_REPORT),
        "safetyBoundary": {
            "localSimulationOnly": True,
            "exchangeDryRunApproved": False,
            "liveTradingApproved": False,
            "orderCreationAllowed": False,
        },
    }


def _candidate_timeframe(candidate_id: Any) -> str | None:
    if not candidate_id:
        return None
    parts = str(candidate_id).split(":")
    return parts[0] if parts else None


def _candidate_direction(candidate_id: Any) -> str | None:
    text = str(candidate_id or "").lower()
    if "short" in text:
        return "short_research"
    if "long" in text:
        return "long_research"
    return "research_observation"


def _runtime_health(primary: dict[str, Any] | None, signal_count: int, observation_count: int) -> dict[str, Any]:
    metrics = primary.get("metrics", {}) if primary else {}
    score = 0
    reasons: list[str] = []
    if primary:
        score += 20
        reasons.append("primary_strategy_contract_available")
    if signal_count >= 100:
        score += 20
        reasons.append("signal_tape_sample_available")
    if observation_count >= 100:
        score += 20
        reasons.append("paper_observation_sample_available")
    pf = _safe_float(metrics.get("profitFactor"))
    rr = _safe_float(metrics.get("rewardRiskRatio"))
    drawdown = _safe_float(metrics.get("maxDrawdownPct"))
    if pf is not None and pf >= 1.5:
        score += 15
        reasons.append("historical_profit_factor_above_local_gate")
    if rr is not None and rr >= 1.8:
        score += 15
        reasons.append("historical_reward_risk_near_2r")
    if drawdown is not None and drawdown <= 20:
        score += 10
        reasons.append("historical_drawdown_within_local_gate")
    if score >= 80:
        label = "runtime_contract_ready"
    elif score >= 50:
        label = "runtime_contract_partial"
    else:
        label = "runtime_contract_needs_data"
    return {"score": min(100, score), "label": label, "reasons": reasons}


def build_signal_tape(selected_signals: list[dict[str, Any]], primary: dict[str, Any] | None, limit: int) -> dict[str, Any]:
    signals = []
    for index, row in enumerate(_latest_rows(selected_signals, "entryDate", limit), start=1):
        signal_id = f"sig-{str(row.get('entryDate') or index).replace(':', '').replace('-', '').replace('+', 'z')}-{row.get('pair', 'unknown')}"
        signals.append(
            {
                "signalId": signal_id,
                "strategyId": primary.get("strategyId") if primary else row.get("candidateId"),
                "strategyTitle": primary.get("strategyTitle") if primary else row.get("candidateId"),
                "candidateId": row.get("candidateId"),
                "exchange": row.get("exchange"),
                "symbol": row.get("pair"),
                "timeframe": row.get("timeframe"),
                "direction": row.get("direction"),
                "signalTime": row.get("signalDate"),
                "entryReferenceTime": row.get("entryDate"),
                "exitReferenceTime": row.get("exitDate"),
                "entryReferencePrice": row.get("entryPrice"),
                "exitReferencePrice": row.get("exitPrice"),
                "rMultiple": row.get("rMultiple"),
                "netReturnPct": row.get("netReturnPct"),
                "exitReason": row.get("exitReason"),
                "status": "historical_observation_only",
                "reason": "Imported from selected historical signal rows for console observation.",
                "riskNote": "Research signal record only. Not trading advice, not an order, and not automation.",
                "source": row.get("source") or "v13_7_1_runtime_contract",
            }
        )
    return {
        "version": VERSION,
        "source": SOURCE,
        "generatedAt": utc_now(),
        "summary": {
            "totalSourceSignals": len(selected_signals),
            "publishedSignalCount": len(signals),
            "latestSignalTime": signals[0].get("entryReferenceTime") if signals else None,
            "sourceFile": str(PRIMARY_SIGNALS),
        },
        "signals": signals,
        "safetyBoundary": SAFETY_BOUNDARY,
    }


def build_paper_observation_ledger(
    ledger: dict[str, Any] | None,
    primary: dict[str, Any] | None,
    limit: int,
) -> dict[str, Any]:
    fills = ledger.get("fills", []) if isinstance(ledger, dict) else []
    fills = fills if isinstance(fills, list) else []
    observations = []
    for row in _latest_rows(fills, "entryDate", limit):
        observations.append(
            {
                "observationId": row.get("positionId"),
                "strategyId": primary.get("strategyId") if primary else row.get("candidateId"),
                "candidateId": row.get("candidateId"),
                "symbol": row.get("pair"),
                "timeframe": row.get("timeframe"),
                "direction": row.get("direction"),
                "entryTime": row.get("entryDate"),
                "exitTime": row.get("exitDate"),
                "entryPrice": row.get("entryPrice"),
                "exitPrice": row.get("exitPrice"),
                "riskAmount": row.get("riskAmount"),
                "notionalValue": row.get("notionalValue"),
                "pnl": row.get("pnl"),
                "rMultiple": row.get("rMultiple"),
                "netReturnPct": row.get("netReturnPct"),
                "exitReason": row.get("exitReason"),
                "status": "closed_historical_local_paper",
                "notes": [
                    "Local paper observation imported from historical replay.",
                    "This is not a real position and not real trading performance.",
                ],
            }
        )
    metrics = ledger.get("metrics", {}) if isinstance(ledger, dict) else {}
    return {
        "version": VERSION,
        "source": SOURCE,
        "generatedAt": utc_now(),
        "summary": {
            "totalObservations": metrics.get("filledSignalCount") or len(fills),
            "publishedObservationCount": len(observations),
            "completedObservations": metrics.get("tradeCount") or len(fills),
            "pendingObservations": 0,
            "winRatePct": metrics.get("winRatePct"),
            "profitFactor": metrics.get("profitFactor"),
            "rewardRiskRatio": metrics.get("rewardRiskRatio"),
            "averageOutcomeR": _average_r_multiple(fills),
            "totalReturnPct": metrics.get("totalReturnPct"),
            "maxDrawdownPct": metrics.get("maxDrawdownPct"),
            "sourceFile": str(PRIMARY_LEDGER),
        },
        "observations": observations,
        "safetyBoundary": SAFETY_BOUNDARY,
    }


def _average_r_multiple(fills: list[dict[str, Any]]) -> float | None:
    values = [_safe_float(row.get("rMultiple")) for row in fills]
    values = [value for value in values if value is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 6)


def build_runtime_status(
    primary: dict[str, Any] | None,
    observer: dict[str, Any] | None,
    signal_tape: dict[str, Any],
    paper_ledger: dict[str, Any],
) -> dict[str, Any]:
    strategies = [item for item in [primary, observer] if item]
    signal_summary = signal_tape.get("summary", {})
    paper_summary = paper_ledger.get("summary", {})
    signal_count = int(signal_summary.get("totalSourceSignals") or 0)
    observation_count = int(paper_summary.get("totalObservations") or 0)
    return {
        "version": VERSION,
        "source": SOURCE,
        "generatedAt": utc_now(),
        "activeStrategy": primary,
        "strategyCount": len(strategies),
        "strategies": strategies,
        "reportCount": sum(1 for path in [PRIMARY_REPORT, OBSERVER_REPORT] if path.exists()),
        "signalTapeCount": signal_count,
        "paperObservationCount": observation_count,
        "runtimeHealth": _runtime_health(primary, signal_count, observation_count),
        "latestSignalTime": signal_summary.get("latestSignalTime"),
        "paperObservationSummary": paper_summary,
        "nextStep": (
            "Observe the standardized runtime feed in desktop and mobile consoles. "
            "Keep forward paper refresh separate from any future exchange review."
        ),
        "contractFiles": {
            "runtimeStatus": str(DEFAULT_RUNTIME_STATUS),
            "signalTape": str(DEFAULT_SIGNAL_TAPE),
            "paperObservationLedger": str(DEFAULT_PAPER_LEDGER),
        },
        "safetyBoundary": SAFETY_BOUNDARY,
    }


def generate_runtime_contract(signal_limit: int = 120, observation_limit: int = 120) -> dict[str, Any]:
    package = read_json(PRIMARY_PACKAGE, {})
    primary_report = read_json(PRIMARY_REPORT, {})
    selected_signals = read_json(PRIMARY_SIGNALS, [])
    ledger = read_json(PRIMARY_LEDGER, {})
    observer_report = read_json(OBSERVER_REPORT, {})

    selected_signals = selected_signals if isinstance(selected_signals, list) else []
    primary = _build_primary_strategy(package, primary_report)
    observer = _build_observer_strategy(observer_report)
    signal_tape = build_signal_tape(selected_signals, primary, signal_limit)
    paper_observation_ledger = build_paper_observation_ledger(ledger, primary, observation_limit)
    runtime_status = build_runtime_status(primary, observer, signal_tape, paper_observation_ledger)

    write_json(DEFAULT_RUNTIME_STATUS, runtime_status)
    write_json(DEFAULT_SIGNAL_TAPE, signal_tape)
    write_json(DEFAULT_PAPER_LEDGER, paper_observation_ledger)
    return {
        "runtimeStatus": runtime_status,
        "signalTape": signal_tape,
        "paperObservationLedger": paper_observation_ledger,
    }

