"""Single-source Formal gate evaluation and artifact projections."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping, Sequence


IMPLEMENTATION_ADMISSION_GATES = frozenset(
    {
        "translation_parity",
        "capital_policy_parity",
        "ranking_evidence_complete",
        "point_in_time_context_complete",
        "fold_assignment_complete",
    }
)


def _count(audit: Mapping[str, Any], primary: str, fallback: str | None = None) -> int:
    value = audit.get(primary)
    if value is None and fallback is not None:
        value = audit.get(fallback)
    return int(value or 0)


def build_fold_assignment_gate(audit: Mapping[str, Any]) -> dict[str, Any]:
    """Build the fold gate from forbidden outcomes, not legal exclusions."""

    violations = {
        "unclassifiedEventCount": _count(
            audit, "unclassifiedEventCount", "unclassifiedCount"
        ),
        "multiAssignedEventCount": _count(
            audit, "multiAssignedEventCount", "multiAssignedCount"
        ),
        "unknownDispositionCount": _count(audit, "unknownDispositionCount"),
        "crossBoundaryLeakageCount": _count(audit, "crossBoundaryLeakageCount"),
    }
    violation_count = sum(violations.values())
    return {
        "gateId": "fold_assignment_complete",
        "actual": violation_count,
        "threshold": 0,
        "status": "passed" if violation_count == 0 else "failed",
        "passed": violation_count == 0,
        "gateRole": "admission",
        "gateClass": "admission",
        "routeClass": "implementation",
        "violations": violations,
        "legalExcludedEventCount": _count(
            audit, "explicitlyExcludedEventCount", "excludedEventCount"
        ),
        "reasonCode": (
            None
            if violation_count == 0
            else "forbidden_fold_assignment_outcomes_present"
        ),
        "evidenceRefs": [],
    }


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value)))


@dataclass(frozen=True)
class FormalGateEvaluation:
    """Authoritative Formal routing decision and its artifact projections."""

    gate_rows: tuple[Mapping[str, Any], ...]
    route: str
    blockers: tuple[str, ...]
    implementation_blockers: tuple[str, ...]
    failed_admission_gate_ids: tuple[str, ...]
    failed_diagnostic_gate_ids: tuple[str, ...]
    not_evaluable_admission_gate_ids: tuple[str, ...]

    @property
    def gate_matrix(self) -> dict[str, Any]:
        rows = [dict(row) for row in self.gate_rows]
        return {
            "schemaVersion": "s01_v18_formal_gate_matrix_v1",
            "gates": rows,
            "passedCount": sum(row.get("passed") is True for row in rows),
            "failedCount": sum(row.get("passed") is False for row in rows),
            "notEvaluableCount": sum(row.get("passed") is None for row in rows),
            "failedAdmissionGateIds": list(self.failed_admission_gate_ids),
            "failedDiagnosticGateIds": list(self.failed_diagnostic_gate_ids),
            "notEvaluableAdmissionGateIds": list(
                self.not_evaluable_admission_gate_ids
            ),
            "route": self.route,
            "routeBlockers": list(self.blockers),
        }

    def with_route(self, route: str, blockers: Sequence[str]) -> "FormalGateEvaluation":
        return replace(self, route=str(route), blockers=_unique(list(blockers)))

    def route_payload(self, campaign_id: str) -> dict[str, Any]:
        return {
            "schemaVersion": "s01_v18_formal_route_v1",
            "campaignId": campaign_id,
            "route": self.route,
            "blockers": list(self.blockers),
            "formalRunCount": 1,
            "formalInputReadCount": 1,
            "resultDrivenParameterChangeCount": 0,
            "lockedOosAccessCount": 0,
            "releaseCount": 0,
            "demoArm": False,
            "orderCount": 0,
            "formalPass": False,
            "formalEvidenceCount": 0,
        }

    def failure_attribution(
        self,
        campaign_id: str,
        *,
        economic_failure_route: str = "archive_s01_current_version",
        implementation_failure_route: str = (
            "implementation_invalid_requires_new_campaign"
        ),
    ) -> dict[str, Any]:
        return {
            "schemaVersion": "s01_v18_formal_failure_attribution_v1",
            "campaignId": campaign_id,
            "route": self.route,
            "primaryBlocker": self.blockers[0] if self.blockers else None,
            "blockers": list(self.blockers),
            "strategyPerformanceFailure": self.route == economic_failure_route,
            "implementationOrEvidenceFailure": self.route
            == implementation_failure_route,
            "resultDrivenRepairAllowed": False,
        }

    def summary_fields(self) -> dict[str, Any]:
        return {"route": self.route, "blockers": list(self.blockers)}


def evaluate_formal_gates(
    *,
    gate_rows: Sequence[Mapping[str, Any]],
    implementation_blockers: Sequence[str],
    stopping_rules: Mapping[str, Any],
    comparable_candidate_panel_status: str | None,
    funding_unavailable_is_route_cap: bool = False,
) -> FormalGateEvaluation:
    """Evaluate every artifact-facing gate once and derive the route from it."""

    normalized_rows: list[dict[str, Any]] = []
    failed_admission: list[str] = []
    failed_diagnostic: list[str] = []
    not_evaluable_admission: list[str] = []
    failed_implementation: list[str] = []

    for source in gate_rows:
        row = dict(source)
        gate_id = str(row.get("gateId") or "")
        source_gate_class = str(row.get("gateClass") or "")
        gate_class = (
            source_gate_class
            if source_gate_class in {"admission", "diagnostic"}
            else str(row.get("gateRole") or "admission")
        )
        route_class = str(
            row.get("routeClass")
            or (
                source_gate_class
                if source_gate_class in {"implementation", "economic"}
                else "implementation"
                if gate_id in IMPLEMENTATION_ADMISSION_GATES
                else "economic"
            )
        )
        row["gateRole"] = gate_class
        row["gateClass"] = gate_class
        row["routeClass"] = route_class
        row["status"] = (
            "unavailable" if row.get("passed") is None else row.get("status")
        )
        row["reasonCode"] = row.get("reasonCode") or row.get("reason")
        row["evidenceRefs"] = list(row.get("evidenceRefs") or [])
        normalized_rows.append(row)
        if gate_class == "diagnostic":
            if row.get("passed") is False:
                failed_diagnostic.append(gate_id)
            continue
        if row.get("passed") is None:
            not_evaluable_admission.append(gate_id)
            if (
                funding_unavailable_is_route_cap
                and gate_id == "conservative_funding_average_net_r"
            ):
                continue
            failed_admission.append(gate_id)
        elif row.get("passed") is False:
            failed_admission.append(gate_id)
        if route_class == "implementation" and row.get("passed") is not True:
            failed_implementation.append(gate_id)

    explicit_implementation = _unique(list(implementation_blockers))
    if explicit_implementation or failed_implementation:
        route = str(
            stopping_rules.get("implementationInvalid")
            or "implementation_invalid_requires_new_campaign"
        )
        blockers = _unique(
            [
                *explicit_implementation,
                *failed_implementation,
                *failed_admission,
            ]
        )
    elif failed_admission:
        route = str(
            stopping_rules.get("economicGateFailure")
            or "archive_s01_current_version"
        )
        blockers = _unique(failed_admission)
    elif comparable_candidate_panel_status == "unavailable_predeclared":
        route = str(
            stopping_rules.get("statisticsUnavailable")
            or "walk_forward_research_pass_statistics_unavailable"
        )
        blockers = ("comparable_candidate_panel_unavailable_predeclared",)
    else:
        route = "walk_forward_research_pass_no_clean_holdout"
        blockers = ("clean_locked_oos_unavailable",)

    return FormalGateEvaluation(
        gate_rows=tuple(normalized_rows),
        route=route,
        blockers=blockers,
        implementation_blockers=explicit_implementation,
        failed_admission_gate_ids=_unique(failed_admission),
        failed_diagnostic_gate_ids=_unique(failed_diagnostic),
        not_evaluable_admission_gate_ids=_unique(not_evaluable_admission),
    )
