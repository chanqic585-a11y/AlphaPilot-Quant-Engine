"""Close the isolated V46 Demo smoke evidence chain without arming Demo."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from alphapilot.data_foundation.checkpoint import load_json, write_json_atomic
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.portfolio_provisional_demo.readiness import (
    build_engineering_smoke_compatibility_audit,
    build_exact_release_approval_request,
    build_pre_arm_readiness,
    render_exact_release_approval_request_markdown,
    render_pre_arm_readiness_markdown,
)


_REQUIRED_JSON = (
    "provisional_release.json",
    "engineering_smoke_contract.json",
    "engineering_smoke_contract_hash_audit.json",
    "engineering_smoke_approval_overlay.json",
    "engineering_smoke_private_preflight.json",
    "engineering_smoke_cancel_audit.json",
    "engineering_smoke_fill_close_audit.json",
    "engineering_smoke_restart_recovery_audit.json",
    "engineering_smoke_rest_reconciliation_audit.json",
    "engineering_smoke_private_websocket_audit.json",
    "engineering_smoke_kill_switch_audit.json",
    "engineering_smoke_strategy_evidence_isolation_audit.json",
    "engineering_smoke_final_self_check.json",
    "v46_portfolio_cooldown_semantics_audit.json",
    "provisional_release_binding_audit.json",
    "provisional_demo_remote_freeze_receipt.json",
    "patch_test_summary.json",
    "pre_existing_test_exception_audit.json",
    "provisional_demo_pre_arm_private_read_audit.json",
)

_REQUIRED_LEDGERS = (
    "engineering_smoke_order_ledger.jsonl",
    "engineering_smoke_fill_ledger.jsonl",
    "engineering_smoke_position_ledger.jsonl",
)

_IDENTITY_FIELDS = (
    "releaseId",
    "releaseHash",
    "riskOverlayHash",
    "executionIntersectionHash",
)

_FORBIDDEN_KEYS = {
    "apikey",
    "apisecret",
    "secretkey",
    "passphrase",
    "credential",
    "credentials",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _load_required(root: Path, name: str) -> dict[str, Any]:
    path = root / name
    _require(path.is_file(), f"Missing required smoke artifact: {name}")
    payload = load_json(path)
    _require(bool(payload), f"Smoke artifact is empty or invalid: {name}")
    return payload


def _read_jsonl(root: Path, name: str) -> list[dict[str, Any]]:
    path = root / name
    _require(path.is_file(), f"Missing required smoke ledger: {name}")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        _require(isinstance(value, dict), f"Invalid row in {name}:{line_number}")
        rows.append(value)
    _require(rows, f"Smoke ledger has no records: {name}")
    return rows


def _assert_no_sensitive_keys(value: Any, *, location: str = "root") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).replace("_", "").lower()
            _require(normalized not in _FORBIDDEN_KEYS, f"Sensitive key in {location}: {key}")
            _assert_no_sensitive_keys(child, location=f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_sensitive_keys(child, location=f"{location}[{index}]")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_text_atomic(path: Path, value: str) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(value, encoding="utf-8", newline="\n")
    temporary.replace(path)


def _validate_identity(
    release: Mapping[str, Any],
    contract: Mapping[str, Any],
    final_check: Mapping[str, Any],
) -> None:
    for field in _IDENTITY_FIELDS:
        expected = release.get(field)
        _require(bool(expected), f"Release identity is missing {field}")
        _require(contract.get(field) == expected, f"Contract {field} does not match Release")
        _require(final_check.get(field) == expected, f"Final self-check {field} does not match Release")
    _require(
        final_check.get("contractHash") == contract.get("contractHash"),
        "Final self-check contractHash does not match smoke contract",
    )


def _validate_smoke(
    payloads: Mapping[str, Mapping[str, Any]],
    ledgers: Mapping[str, Sequence[Mapping[str, Any]]],
) -> None:
    release = payloads["provisional_release.json"]
    contract = payloads["engineering_smoke_contract.json"]
    final_check = payloads["engineering_smoke_final_self_check.json"]
    _validate_identity(release, contract, final_check)
    _require(release.get("approved") is False, "Release must remain unapproved")
    _require(release.get("demoArm") is False, "Release must remain unarmed")
    _require(release.get("formalPass") is False, "V46 must remain a development-selected result")
    _require(release.get("livePromotionEligible") is False, "V46 must not be Live eligible")

    contract_audit = payloads["engineering_smoke_contract_hash_audit.json"]
    _require(contract_audit.get("status") == "passed", "Smoke contract hash audit failed")
    _require(contract_audit.get("exactBindingsVerified") is True, "Exact smoke bindings were not verified")
    _require(contract_audit.get("contractHash") == contract.get("contractHash"), "Contract hash audit mismatch")

    overlay = payloads["engineering_smoke_approval_overlay.json"]
    _require(overlay.get("status") == "approved_engineering_smoke_only", "Engineering-only approval is absent")
    _require(overlay.get("requestType") == "engineering_smoke_only", "Approval scope is not engineering-only")
    _require(overlay.get("strategyReleaseApprovalAccepted") is False, "Smoke approval cannot approve a strategy")

    preflight = payloads["engineering_smoke_private_preflight.json"]
    _require(preflight.get("status") == "passed", "Private Demo preflight failed")
    _require(preflight.get("environment") == "okx_demo", "Smoke was not run in OKX Demo")
    _require(preflight.get("demoHeaderRequired") is True, "Demo request header was not enforced")
    _require(preflight.get("credentialsRetained") is False, "Credentials were retained")
    _require(preflight.get("rawResponsesRetained") is False, "Raw private responses were retained")

    cancel = payloads["engineering_smoke_cancel_audit.json"]
    _require(cancel.get("status") == "passed", "Post-only cancel path failed")
    _require(cancel.get("finalOrderState") in {"canceled", "filled"}, "Path A has no terminal state")

    fill_close = payloads["engineering_smoke_fill_close_audit.json"]
    _require(fill_close.get("status") == "passed", "Fill-close path failed")
    _require(str(fill_close.get("finalPositionSize")) == "0", "Smoke did not end flat")
    _require(fill_close.get("reduceOnlyClose") is True, "Smoke close was not reduce-only")
    _require(int(fill_close.get("orderAttemptCount") or 0) in {2, 3}, "Unexpected smoke order count")

    for name in (
        "engineering_smoke_restart_recovery_audit.json",
        "engineering_smoke_kill_switch_audit.json",
    ):
        _require(payloads[name].get("status") == "passed", f"Smoke check failed: {name}")

    reconciliation = payloads["engineering_smoke_rest_reconciliation_audit.json"]
    _require(reconciliation.get("status") == "passed", "Final REST reconciliation failed")
    for field in ("pendingOrderCount", "nonzeroPositionCount", "unknownOrderCount", "orphanPositionCount"):
        _require(int(reconciliation.get(field) or 0) == 0, f"REST reconciliation has {field}")

    websocket = payloads["engineering_smoke_private_websocket_audit.json"]
    _require(websocket.get("status") == "passed", "Private WebSocket audit failed")
    _require(websocket.get("authenticated") is True, "Private WebSocket did not authenticate")
    _require(websocket.get("subscribed") is True, "Private WebSocket did not subscribe")
    _require(websocket.get("credentialsRetained") is False, "Private WebSocket retained credentials")

    isolation = payloads["engineering_smoke_strategy_evidence_isolation_audit.json"]
    _require(isolation.get("status") == "passed", "Strategy evidence isolation failed")
    _require(isolation.get("strategyEvidenceChanged") is False, "Smoke changed strategy evidence")
    for field in ("strategyOrderCountDelta", "strategyClosedTradeCountDelta", "forwardEvidenceDelta", "formalEvidenceDelta"):
        _require(int(isolation.get(field) or 0) == 0, f"Smoke changed {field}")

    _require(final_check.get("status") == "passed", "Final smoke self-check failed")
    _require(final_check.get("engineeringSmokeReady") is True, "Engineering smoke is not ready")
    for field in (
        "duplicateOrderCount",
        "orphanOrderCount",
        "orphanPositionCount",
        "unknownStateCount",
        "finalPositionCount",
        "strategyOrderCount",
        "strategyClosedTradeCount",
        "forwardEvidenceDelta",
        "formalEvidenceDelta",
    ):
        _require(int(final_check.get(field) or 0) == 0, f"Final smoke self-check has {field}")
    _require(final_check.get("nextRoute") == "blocked_waiting_exact_release_approval", "Smoke route is unsafe")
    for field in ("demoArm", "live", "withdraw"):
        _require(final_check.get(field) is False, f"Smoke unexpectedly enabled {field}")

    orders = list(ledgers["engineering_smoke_order_ledger.jsonl"])
    fills = list(ledgers["engineering_smoke_fill_ledger.jsonl"])
    positions = list(ledgers["engineering_smoke_position_ledger.jsonl"])
    _require(len(orders) in {2, 3}, "Engineering order ledger must contain two or three attempts")
    _require(len(fills) >= 2, "Engineering fill ledger must include open and close fills")
    _require(str(positions[-1].get("quantity")) == "0", "Final engineering position ledger row is not flat")
    for name, rows in ledgers.items():
        for row in rows:
            _require(row.get("engineeringOnly") is True, f"Non-engineering row in {name}")
            _require(row.get("strategyQualification") is False, f"Strategy-qualified row in {name}")
            _assert_no_sensitive_keys(row, location=name)


def _manifest(root: Path, generated_at: str) -> dict[str, Any]:
    names = sorted(
        path.name
        for path in root.iterdir()
        if path.is_file()
        and path.name != "engineering_smoke_artifact_manifest.json"
        and (
            path.name.startswith("engineering_smoke_")
            or path.name.startswith("updated_provisional_demo_pre_arm_readiness")
            or path.name.startswith("provisional_demo_exact_release_approval_request")
        )
    )
    artifacts = [
        {
            "path": name,
            "sha256": _sha256(root / name),
            "bytes": (root / name).stat().st_size,
        }
        for name in names
    ]
    core = {
        "schemaVersion": "v46_engineering_smoke_artifact_manifest_v1",
        "generatedAt": generated_at,
        "artifactCount": len(artifacts),
        "artifacts": artifacts,
        "demoArm": False,
        "live": False,
        "withdraw": False,
        "route": "blocked_waiting_exact_release_approval",
    }
    return {**core, "manifestHash": stable_hash(core, prefix="v46_engineering_smoke_manifest")}


def finalize_engineering_smoke(*, evidence_root: Path, generated_at: str) -> dict[str, Any]:
    root = evidence_root.resolve()
    payloads = {name: _load_required(root, name) for name in _REQUIRED_JSON}
    ledgers = {name: _read_jsonl(root, name) for name in _REQUIRED_LEDGERS}
    for name, payload in payloads.items():
        _assert_no_sensitive_keys(payload, location=name)
    _validate_smoke(payloads, ledgers)

    contract = payloads["engineering_smoke_contract.json"]
    compatibility = build_engineering_smoke_compatibility_audit(
        smoke_contract={"status": "passed", **contract},
        cancel_audit=payloads["engineering_smoke_cancel_audit.json"],
        fill_close_audit=payloads["engineering_smoke_fill_close_audit.json"],
        restart_audit=payloads["engineering_smoke_restart_recovery_audit.json"],
        reconciliation_audit=payloads["engineering_smoke_rest_reconciliation_audit.json"],
        private_websocket_audit=payloads["engineering_smoke_private_websocket_audit.json"],
        kill_switch_audit=payloads["engineering_smoke_kill_switch_audit.json"],
        final_self_check=payloads["engineering_smoke_final_self_check.json"],
        evidence_isolation_audit=payloads["engineering_smoke_strategy_evidence_isolation_audit.json"],
        generated_at=generated_at,
    )
    _require(compatibility.get("engineeringSmokeReady") is True, "Completed smoke is not compatible")
    write_json_atomic(root / "engineering_smoke_completed_compatibility_audit.json", compatibility)

    readiness = build_pre_arm_readiness(
        release=payloads["provisional_release.json"],
        cooldown_audit=payloads["v46_portfolio_cooldown_semantics_audit.json"],
        binding_audit=payloads["provisional_release_binding_audit.json"],
        remote_freeze_receipt=payloads["provisional_demo_remote_freeze_receipt.json"],
        targeted_test_summary=payloads["patch_test_summary.json"],
        test_exception_audit=payloads["pre_existing_test_exception_audit.json"],
        private_read_audit=payloads["provisional_demo_pre_arm_private_read_audit.json"],
        engineering_smoke_audit=compatibility,
        generated_at=generated_at,
    )
    _require(readiness.get("approvalReady") is True, "Pre-ARM readiness is incomplete")
    _require(readiness.get("route") == "blocked_waiting_exact_release_approval", "Readiness did not stop at exact approval")
    write_json_atomic(root / "updated_provisional_demo_pre_arm_readiness.json", readiness)
    _write_text_atomic(root / "updated_provisional_demo_pre_arm_readiness.md", render_pre_arm_readiness_markdown(readiness))

    request = build_exact_release_approval_request(
        release=payloads["provisional_release.json"],
        readiness=readiness,
        smoke_audit=compatibility,
        smoke_contract=contract,
        generated_at=generated_at,
    )
    write_json_atomic(root / "provisional_demo_exact_release_approval_request.json", request)
    _write_text_atomic(root / "provisional_demo_exact_release_approval_request.md", render_exact_release_approval_request_markdown(request))
    manifest = _manifest(root, generated_at)
    write_json_atomic(root / "engineering_smoke_artifact_manifest.json", manifest)
    return {
        "status": "completed",
        "releaseId": request["releaseId"],
        "releaseHash": request["releaseHash"],
        "riskOverlayHash": request["riskOverlayHash"],
        "executionIntersectionHash": request["executionIntersectionHash"],
        "engineeringSmokeEvidenceHash": request["engineeringSmokeEvidenceHash"],
        "engineeringSmokeContractHash": request["engineeringSmokeContractHash"],
        "approvalRequestHash": request["requestHash"],
        "route": "blocked_waiting_exact_release_approval",
        "approved": False,
        "demoArm": False,
        "live": False,
        "withdraw": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--generated-at", required=True)
    args = parser.parse_args(argv)
    result = finalize_engineering_smoke(
        evidence_root=args.evidence_root,
        generated_at=args.generated_at,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
