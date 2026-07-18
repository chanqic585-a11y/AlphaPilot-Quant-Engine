"""Fail-closed implementation contracts for frozen Advisory-R candidates."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash


class ImplementationConformanceError(RuntimeError):
    """Raised when frozen semantics would otherwise be silently replaced."""


_COMMON_POLICY_KEYS = {
    "exitPolicy.initialStopMayWiden",
    "exitPolicy.maximumHoldBars",
    "exitPolicy.mode",
    "exitPolicy.version",
}


def _paths(*values: str) -> set[str]:
    return set(values) | _COMMON_POLICY_KEYS


CONSUMED_KEYS_BY_VARIANT: dict[str, set[str]] = {
    "S01": _paths(
        "featureDefinition.marketRegime",
        "featureDefinition.recoveryBars",
        "featureDefinition.residualWindow",
        "featureDefinition.residualZMaximum",
        "entryDefinition.kind",
        "entryDefinition.minimumRecoveryZ",
        "initialStopDefinition.kind",
        "initialStopDefinition.mayWiden",
        "initialStopDefinition.multiple",
        "exitPolicy.parameters.partialAtR",
        "exitPolicy.parameters.partialFraction",
        "exitPolicy.parameters.remainderMode",
        "exitPolicy.parameters.structureRule.absoluteZscoreMaximum",
        "exitPolicy.parameters.structureRule.kind",
    ),
    "S02": _paths(
        "featureDefinition.betaWindow",
        "featureDefinition.btcImpulseZ",
        "featureDefinition.lagWindow",
        "entryDefinition.kind",
        "entryDefinition.maximumFollowerMoveFraction",
        "initialStopDefinition.kind",
        "initialStopDefinition.mayWiden",
        "initialStopDefinition.multiple",
        "exitPolicy.parameters.partialAtR",
        "exitPolicy.parameters.partialFraction",
        "exitPolicy.parameters.trailingAtrMultiple",
    ),
    "S03": _paths(
        "featureDefinition.btcImpulseZ",
        "featureDefinition.lagWindow",
        "featureDefinition.overreactionRatio",
        "entryDefinition.confirmationBars",
        "entryDefinition.kind",
        "initialStopDefinition.kind",
        "initialStopDefinition.mayWiden",
        "initialStopDefinition.multiple",
        "exitPolicy.parameters.structureRule.confirmationBars",
        "exitPolicy.parameters.structureRule.kind",
    ),
    "S04": _paths(
        "featureDefinition.entryResidualZ",
        "featureDefinition.minimumCorrelation",
        "featureDefinition.pairWindow",
        "entryDefinition.kind",
        "entryDefinition.requireTurn",
        "initialStopDefinition.kind",
        "initialStopDefinition.mayWiden",
        "initialStopDefinition.maximumAdverseZ",
        "exitPolicy.parameters.structureRule.absoluteZscoreMaximum",
        "exitPolicy.parameters.structureRule.kind",
    ),
    "S05": _paths(
        "featureDefinition.baselineMinimum",
        "featureDefinition.breakMaximum",
        "featureDefinition.correlationWindow",
        "entryDefinition.kind",
        "entryDefinition.residualTurnBars",
        "initialStopDefinition.kind",
        "initialStopDefinition.mayWiden",
        "initialStopDefinition.multiple",
        "exitPolicy.parameters.partialAtR",
        "exitPolicy.parameters.partialFraction",
        "exitPolicy.parameters.remainderMode",
        "exitPolicy.parameters.structureRule.kind",
        "exitPolicy.parameters.structureRule.minimumCorrelation",
    ),
    "S06": _paths(
        "featureDefinition.breakMaximum",
        "featureDefinition.correlationWindow",
        "featureDefinition.relativeStrengthBars",
        "entryDefinition.kind",
        "entryDefinition.minimumRelativeMoveZ",
        "initialStopDefinition.kind",
        "initialStopDefinition.mayWiden",
        "initialStopDefinition.multiple",
        "exitPolicy.parameters.partialAtR",
        "exitPolicy.parameters.partialFraction",
        "exitPolicy.parameters.trailingAtrMultiple",
    ),
    "S07": _paths(
        "featureDefinition.atrPercentileWindow",
        "featureDefinition.closeLocationThreshold",
        "featureDefinition.shockPercentile",
        "entryDefinition.confirmationBars",
        "entryDefinition.kind",
        "initialStopDefinition.kind",
        "initialStopDefinition.mayWiden",
        "initialStopDefinition.multiple",
        "exitPolicy.parameters.partialAtR",
        "exitPolicy.parameters.partialFraction",
        "exitPolicy.parameters.trailingAtrMultiple",
    ),
    "S08": _paths(
        "featureDefinition.minimumVolumeRatio",
        "featureDefinition.trendWindow",
        "featureDefinition.utcEntryHours",
        "entryDefinition.directionFromPriorBars",
        "entryDefinition.kind",
        "initialStopDefinition.kind",
        "initialStopDefinition.mayWiden",
        "initialStopDefinition.multiple",
        "exitPolicy.parameters.targetR",
    ),
    "S09": _paths(
        "featureDefinition.betaWindow",
        "featureDefinition.btcTrendWindow",
        "featureDefinition.rebalanceBars",
        "entryDefinition.kind",
        "entryDefinition.longQuantile",
        "entryDefinition.shortQuantile",
        "initialStopDefinition.kind",
        "initialStopDefinition.mayWiden",
        "initialStopDefinition.riskBudgetR",
        "exitPolicy.parameters.structureRule.kind",
        "exitPolicy.parameters.structureRule.maximumRankPercentile",
    ),
    "S10": _paths(
        "featureDefinition.minimumVotes",
        "featureDefinition.signals",
        "entryDefinition.confirmationBars",
        "entryDefinition.kind",
        "initialStopDefinition.kind",
        "initialStopDefinition.mayWiden",
        "initialStopDefinition.multiple",
        "exitPolicy.parameters.structureRule.fastWindow",
        "exitPolicy.parameters.structureRule.kind",
        "exitPolicy.parameters.structureRule.slowWindow",
    ),
}


def _leaf_paths(value: Any, prefix: str) -> set[str]:
    if isinstance(value, Mapping):
        result: set[str] = set()
        for key, item in value.items():
            result.update(_leaf_paths(item, f"{prefix}.{key}"))
        return result
    return {prefix}


def frozen_execution_keys(candidate: Mapping[str, Any]) -> set[str]:
    result: set[str] = set()
    for root in (
        "featureDefinition",
        "entryDefinition",
        "initialStopDefinition",
        "exitPolicy",
    ):
        result.update(_leaf_paths(candidate[root], root))
    return result


def _value_at_path(candidate: Mapping[str, Any], path: str) -> Any:
    value: Any = candidate
    for part in path.split("."):
        if not isinstance(value, Mapping) or part not in value:
            raise ImplementationConformanceError(f"unknown frozen path: {path}")
        value = value[part]
    return value


def build_conformance_record(
    candidate: Mapping[str, Any],
    *,
    consumed_keys: set[str],
    unsupported_keys: set[str] | None = None,
    hardcoded_values: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    unsupported = sorted(unsupported_keys or set())
    if unsupported:
        raise ImplementationConformanceError(
            f"unsupported frozen rule: {', '.join(unsupported)}"
        )
    for path, implemented_value in (hardcoded_values or {}).items():
        frozen_value = _value_at_path(candidate, path)
        if implemented_value != frozen_value:
            raise ImplementationConformanceError(
                f"hard-coded value mismatch at {path}: "
                f"implemented={implemented_value!r}, frozen={frozen_value!r}"
            )

    expected = frozen_execution_keys(candidate)
    unknown_consumed = sorted(consumed_keys - expected)
    if unknown_consumed:
        raise ImplementationConformanceError(
            f"implementation declared unknown frozen keys: {unknown_consumed}"
        )
    unused = sorted(expected - consumed_keys)
    feature = sorted(key for key in consumed_keys if key.startswith("featureDefinition."))
    entry = sorted(key for key in consumed_keys if key.startswith("entryDefinition."))
    stop = sorted(key for key in consumed_keys if key.startswith("initialStopDefinition."))
    exit_rule = sorted(key for key in consumed_keys if key.startswith("exitPolicy."))
    payload = {
        "candidateId": candidate["candidateId"],
        "strategyDefinitionHash": candidate["strategyDefinitionHash"],
        "implementedFeatureKeys": feature,
        "implementedEntryKeys": entry,
        "implementedStopKeys": stop,
        "implementedExitRuleKeys": exit_rule,
        "unusedFrozenKeys": unused,
        "unsupportedFrozenKeys": [],
        "implementationConformancePassed": not unused,
    }
    return {
        **payload,
        "implementationConformanceHash": stable_hash(
            payload, prefix="advisory_r_implementation_conformance"
        ),
    }


def build_candidate_conformance(candidate: Mapping[str, Any]) -> dict[str, Any]:
    variant = str(candidate["variantId"])
    try:
        consumed = CONSUMED_KEYS_BY_VARIANT[variant]
    except KeyError as exc:
        raise ImplementationConformanceError(
            f"unsupported candidate variant: {variant}"
        ) from exc
    return build_conformance_record(candidate, consumed_keys=set(consumed))

