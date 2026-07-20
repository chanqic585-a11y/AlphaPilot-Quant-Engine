"""Freeze and write bounded portfolio rescue evidence."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .contracts import CampaignContract
from .replay import PolicyReplayResult, replay_policy


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze_preregistration(
    output_dir: str | Path,
    campaign: CampaignContract,
    ledger_dir: str | Path,
) -> dict[str, Any]:
    root = Path(output_dir)
    path = root / "preregistration.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing.get("campaignHash") != campaign.campaign_hash:
            raise ValueError("existing_preregistration_campaign_hash_mismatch")
        return existing

    ledgers = []
    for sleeve in campaign.sleeves:
        ledger = Path(ledger_dir) / f"{sleeve.candidate_id}.parquet"
        if not ledger.is_file():
            raise FileNotFoundError(ledger)
        ledgers.append(
            {
                "candidateId": sleeve.candidate_id,
                "path": ledger.resolve().as_posix(),
                "sha256": _sha256(ledger),
            }
        )
    payload = {
        "campaignHash": campaign.campaign_hash,
        "campaignId": campaign.campaign_id,
        "contract": campaign.to_dict(),
        "formalCandidateCount": 0,
        "frozenAt": _utc_now(),
        "frozenBeforeResultRead": True,
        "ledgers": ledgers,
        "lockedOosReadCount": 0,
        "releaseCount": 0,
        "status": "development_only",
    }
    _write_json(path, payload)
    return payload


def _load_campaign_trades(campaign: CampaignContract, ledger_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sleeve in campaign.sleeves:
        path = ledger_dir / f"{sleeve.candidate_id}.parquet"
        frame = pd.read_parquet(path)
        for row in frame.to_dict(orient="records"):
            if row.get("candidateId") != sleeve.candidate_id:
                raise ValueError(f"ledger_candidate_mismatch:{sleeve.candidate_id}")
            rows.append(row)
    return rows


def _qualification(result: PolicyReplayResult) -> tuple[dict[str, bool], float]:
    metrics = result.metrics
    stress = result.stress_metrics.get("plus_0.10R", {})
    monthly = result.monthly_consistency
    attribution = result.sleeve_attribution
    trade_count = int(metrics.get("tradeCount") or 0)
    largest_trade_share = max(
        (int(row.get("tradeCount") or 0) / trade_count for row in attribution.values()),
        default=1.0,
    )
    checks = {
        "minimumTradeCount100": trade_count >= 100,
        "minimumProfitFactor1_20": float(metrics.get("profitFactor") or 0) >= 1.20,
        "positiveExpectancy": float(metrics.get("expectancyR") or 0) > 0,
        "maximumDrawdown20R": float(metrics.get("maxDrawdownR") or 0) <= 20,
        "stressProfitFactor1_05": float(stress.get("profitFactor") or 0) >= 1.05,
        "positiveMonthRatio55Pct": float(monthly.get("positiveMonthRatio") or 0) >= 0.55,
        "largestSleeveTradeShare75Pct": largest_trade_share <= 0.75,
        "everySleevePositive": bool(attribution)
        and all(float(row.get("expectancyR") or 0) > 0 for row in attribution.values()),
    }
    score = (
        float(metrics.get("profitFactor") or 0) * 100
        + float(metrics.get("expectancyR") or 0) * 50
        + float(monthly.get("positiveMonthRatio") or 0) * 25
        - float(metrics.get("maxDrawdownR") or 0)
    )
    return checks, round(score, 6)


def _manifest(root: Path) -> dict[str, Any]:
    rows = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "artifact_manifest.json":
            continue
        rows.append(
            {
                "bytes": path.stat().st_size,
                "path": path.relative_to(root).as_posix(),
                "sha256": _sha256(path),
            }
        )
    return {
        "artifactCount": len(rows),
        "artifacts": rows,
        "generatedAt": _utc_now(),
        "status": "development_only",
    }


def run_and_write_portfolio_rescue(
    output_dir: str | Path,
    campaign: CampaignContract,
    ledger_dir: str | Path,
) -> dict[str, Any]:
    root = Path(output_dir)
    prereg_path = root / "preregistration.json"
    if not prereg_path.exists():
        raise ValueError("preregistration_must_be_frozen_before_result_read")
    prereg = json.loads(prereg_path.read_text(encoding="utf-8"))
    if prereg.get("campaignHash") != campaign.campaign_hash:
        raise ValueError("preregistration_campaign_hash_mismatch")

    trades = _load_campaign_trades(campaign, Path(ledger_dir))
    results = [replay_policy(trades, policy) for policy in campaign.policies]
    policy_rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    ranked: list[tuple[bool, float, PolicyReplayResult, dict[str, bool]]] = []
    for result in results:
        checks, score = _qualification(result)
        qualifies = all(checks.values())
        ranked.append((qualifies, score, result, checks))
        stress = result.stress_metrics.get("plus_0.10R", {})
        policy_rows.append(
            {
                "policyId": result.policy.policy_id,
                "policyHash": result.policy.policy_hash,
                "acceptedTrades": len(result.accepted_trades),
                "rejectedTrades": len(result.rejected_trades),
                "profitFactor": result.metrics.get("profitFactor"),
                "expectancyR": result.metrics.get("expectancyR"),
                "totalR": result.metrics.get("totalR"),
                "maxDrawdownR": result.metrics.get("maxDrawdownR"),
                "positiveMonthRatio": result.monthly_consistency.get("positiveMonthRatio"),
                "stressPlus0_10RProfitFactor": stress.get("profitFactor"),
                "qualificationPassed": qualifies,
                "developmentScore": score,
            }
        )
        failures.append(
            {
                "policyId": result.policy.policy_id,
                "failedChecks": [key for key, passed in checks.items() if not passed],
                "checks": checks,
                "rejectionCounts": dict(result.rejection_counts),
            }
        )

    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    best_qualifies, _, best, best_checks = ranked[0]

    sleeve_rows = []
    monthly_rows = []
    ledger_root = root / "policy_ledgers"
    ledger_root.mkdir(parents=True, exist_ok=True)
    for result in results:
        pd.DataFrame(result.accepted_trades).to_parquet(
            ledger_root / f"{result.policy.policy_id}.parquet", index=False
        )
        for candidate_id, metrics in result.sleeve_attribution.items():
            sleeve_rows.append(
                {
                    "policyId": result.policy.policy_id,
                    "candidateId": candidate_id,
                    **metrics,
                }
            )
        for month, net_r in result.monthly_consistency.get("monthlyNetR", {}).items():
            monthly_rows.append(
                {"policyId": result.policy.policy_id, "month": month, "netR": net_r}
            )

    _write_csv(root / "policy_matrix.csv", policy_rows)
    _write_csv(root / "sleeve_attribution.csv", sleeve_rows)
    _write_csv(root / "monthly_consistency.csv", monthly_rows)
    _write_json(root / "failure_attribution.json", failures)
    _write_json(
        root / "experiment_budget.json",
        {
            "maximumDevelopmentTrials": campaign.maximum_development_trials,
            "policyTrialCount": len(results),
            "remainingTrials": campaign.maximum_development_trials - len(results),
            "status": "within_budget",
        },
    )
    _write_json(root / "policy_results.json", [result.to_dict() for result in results])

    summary = {
        "bestPolicyChecks": best_checks,
        "bestPolicyId": best.policy.policy_id,
        "bestPolicyMetrics": dict(best.metrics),
        "campaignHash": campaign.campaign_hash,
        "campaignId": campaign.campaign_id,
        "formalCandidateCount": 0,
        "generatedAt": _utc_now(),
        "lockedOosReadCount": 0,
        "policyTrialCount": len(results),
        "releaseCount": 0,
        "status": "development_only",
        "warrantsFreshPreregisteredOos": best_qualifies,
    }
    _write_json(root / "campaign_summary.json", summary)
    markdown = [
        "# Portfolio Rescue Campaign",
        "",
        f"- Status: `{summary['status']}`",
        f"- Campaign: `{summary['campaignId']}`",
        f"- Best frozen policy: `{summary['bestPolicyId']}`",
        f"- Fresh preregistered OOS warranted: `{summary['warrantsFreshPreregisteredOos']}`",
        f"- Formal candidates created: {summary['formalCandidateCount']}",
        f"- Releases created: {summary['releaseCount']}",
        "",
        "The campaign is development-only. Its output cannot promote a strategy or retroactively change a frozen Demo release.",
    ]
    (root / "campaign_summary.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    _write_json(root / "artifact_manifest.json", _manifest(root))
    return summary
