"""Bind existing offline research evidence to the adaptive-learning readiness gate."""

from __future__ import annotations

from typing import Any, Mapping

from alphapilot.evolution.registry.hashing import stable_hash


def build_offline_evidence(
    *,
    factor_benchmark: Mapping[str, Any],
    factor_shortlist: Mapping[str, Any],
    qlib_preflight: Mapping[str, Any],
) -> dict[str, Any]:
    if factor_benchmark.get("schemaVersion") != "factor_benchmark_report_v1":
        raise ValueError("Unsupported factor benchmark schema")
    if factor_shortlist.get("schemaVersion") != "factor_shortlist_v1":
        raise ValueError("Unsupported factor shortlist schema")
    if qlib_preflight.get("schemaVersion") != "v13_27_1_12_qlib_preflight_v1":
        raise ValueError("Unsupported Qlib preflight schema")

    benchmark_shortlist_id = str(factor_benchmark.get("factorShortlistId") or "")
    shortlist_id = str(factor_shortlist.get("factorShortlistId") or "")
    if not benchmark_shortlist_id or benchmark_shortlist_id != shortlist_id:
        raise ValueError("Factor benchmark and shortlist identity mismatch")

    eligible_factors = [str(item) for item in factor_shortlist.get("eligibleFactors") or []]
    eligible_count = int(factor_benchmark.get("eligibleFactorCount") or 0)
    if eligible_count != len(eligible_factors):
        raise ValueError("Factor benchmark and shortlist eligible counts differ")

    real_bench_ready = (
        factor_benchmark.get("status") == "completed"
        and factor_benchmark.get("controlStatus") == "passed"
        and factor_benchmark.get("readinessPassed") is True
        and int(factor_benchmark.get("formalTrialCount") or 0) > 0
    )
    validated_subset_ready = real_bench_ready and eligible_count > 0
    qlib_campaign_ready = (
        qlib_preflight.get("qlibCampaignMayRun") is True
        and qlib_preflight.get("modelCampaignRun") is True
    )

    blockers: list[str] = []
    if not real_bench_ready:
        blockers.append("real_factor_bench_not_ready")
    if not validated_subset_ready:
        blockers.append("no_validated_crypto_factor_subset")
    blockers.extend(
        f"qlib_preflight:{item}"
        for item in qlib_preflight.get("blockers") or []
    )
    if not qlib_campaign_ready:
        blockers.append("qlib_campaign_not_run")

    if not real_bench_ready:
        status = "blocked_factor_bench_not_ready"
    elif not validated_subset_ready:
        status = "blocked_no_validated_factor_subset"
    elif not qlib_campaign_ready:
        status = "blocked_qlib_campaign_not_run"
    else:
        status = "ready_for_model_validation_inputs"

    core = {
        "schemaVersion": "adaptive_learning_offline_evidence_v1",
        "status": status,
        "dataSnapshotId": factor_benchmark.get("dataSnapshotId"),
        "factorShortlistId": shortlist_id,
        "formalTrialCount": int(factor_benchmark.get("formalTrialCount") or 0),
        "eligibleFactorCount": eligible_count,
        "eligibleFactors": eligible_factors,
        "pitStatus": factor_benchmark.get("pitStatus"),
        "qlibBlockers": list(qlib_preflight.get("blockers") or []),
        "blockers": blockers,
        "evidence": {
            "realFactorBenchReady": real_bench_ready,
            "validatedCryptoFactorSubsetReady": validated_subset_ready,
            "qlibCampaignReady": qlib_campaign_ready,
            "trainingDatasetReady": False,
            "modelValidationReady": False,
        },
        "predictiveValueClaimed": False,
        "modelTrainingRun": False,
        "liveDecisionAuthorityGranted": False,
    }
    return {
        **core,
        "offlineEvidenceHash": stable_hash(core, prefix="adaptive_offline_evidence"),
    }
