"""Register existing manual factors without rewriting values or promoting them."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from alphapilot.evolution.factor_dsl.ast import ast_to_dict
from alphapilot.evolution.factor_dsl.canonicalizer import (
    canonical_expression,
    canonical_field_name,
    canonicalize,
    expression_id,
)
from alphapilot.evolution.factor_dsl.parser import FactorSyntaxError, parse_expression
from alphapilot.evolution.factor_dsl.validator import validate_factor_expression
from alphapilot.evolution.registry.hashing import sha256_file, stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import FactorDefinitionRecord


def _reject_constant(value: str) -> None:
    raise ValueError(f"non_finite_json_number:{value}")


def _load_report(path: Path) -> dict[str, Any]:
    payload = json.loads(
        path.read_text(encoding="utf-8-sig"),
        parse_constant=_reject_constant,
    )
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return payload


def _issue_payload(code: str, message: str, path: str = "root") -> dict[str, str]:
    return {"code": code, "message": message, "path": path}


def _summarize_existing_evaluation(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    summary_keys = (
        "factorId",
        "expectedDirection",
        "factorDirectionAdjusted",
        "coveragePct",
        "missingRate",
        "sampleCount",
        "nonNullCount",
        "primaryHorizon",
        "warnings",
        "candidateStatus",
    )
    metric_keys = (
        "meanIC",
        "medianIC",
        "positiveICRatio",
        "meanRankIC",
        "medianRankIC",
        "positiveRankICRatio",
        "topBottomSpread",
        "monotonicityScore",
        "profitFactor",
        "expectancy",
        "winRate",
        "validSampleCount",
    )
    stability_keys = (
        "stableAcrossMonths",
        "stableAcrossPairs",
        "stableAcrossRegimes",
        "positiveMonthRatio",
        "positivePairRatio",
        "positiveRegimeRatio",
        "concentrationWarnings",
    )
    summary = {key: value.get(key) for key in summary_keys if key in value}
    metrics = value.get("primaryHorizonMetrics")
    if isinstance(metrics, dict):
        summary["primaryHorizonMetrics"] = {
            key: metrics.get(key) for key in metric_keys if key in metrics
        }
    stability = value.get("stability")
    if isinstance(stability, dict):
        summary["stability"] = {
            key: stability.get(key) for key in stability_keys if key in stability
        }
    return summary


def adapt_legacy_factor_library(
    *,
    manual_report_path: Path | str,
    evaluation_report_path: Path | str,
    repository: RegistryRepository,
) -> dict[str, Any]:
    manual_path = Path(manual_report_path)
    evaluation_path = Path(evaluation_report_path)
    manual_report = _load_report(manual_path)
    evaluation_report = _load_report(evaluation_path)
    definitions = manual_report.get("factorDefinitions") or []
    if not isinstance(definitions, list):
        raise ValueError("factorDefinitions must be an array")
    evaluation_rows = {
        str(item.get("factorId")): item
        for item in (evaluation_report.get("factorReports") or [])
        if isinstance(item, dict) and item.get("factorId")
    }
    existing_candidate_ids = {
        str(item.get("factorId") if isinstance(item, dict) else item)
        for item in (evaluation_report.get("candidateFactors") or [])
    }
    version = str(manual_report.get("version") or "legacy")
    factor_results: list[dict[str, Any]] = []
    supported_count = 0
    new_definition_count = 0

    for raw_definition in definitions:
        if not isinstance(raw_definition, dict):
            raise ValueError("Each factor definition must be a JSON object")
        factor_id = str(raw_definition.get("factorId") or "").strip()
        source_formula = str(raw_definition.get("formula") or "").strip()
        if not factor_id or not source_formula:
            raise ValueError("Each factor definition requires factorId and formula")
        required_fields = [
            canonical_field_name(str(name))
            for name in (raw_definition.get("requiredFields") or [])
        ]
        field_types = {name: "number" for name in required_fields}
        issues: list[dict[str, str]] = []
        canonical = None
        canonical_text = None
        factor_expression_id = None
        try:
            parsed = parse_expression(source_formula)
            canonical = canonicalize(parsed)
            validation = validate_factor_expression(canonical, field_types=field_types)
            issues = [
                _issue_payload(item.code, item.message, item.path) for item in validation.issues
            ]
            if validation.valid:
                canonical_text = canonical_expression(canonical)
                factor_expression_id = expression_id(canonical)
        except (FactorSyntaxError, TypeError, ValueError) as exc:
            issues = [_issue_payload("dsl_parse_or_canonicalization_failed", str(exc))]

        dsl_supported = not issues and canonical is not None
        if dsl_supported:
            supported_count += 1
        source_formula_hash = stable_hash(source_formula, prefix="source_formula")
        definition_payload = {
            "schemaVersion": "legacy_factor_definition_adapter_v1",
            "factorId": factor_id,
            "sourceVersion": version,
            "sourceDefinition": raw_definition,
            "sourceFormula": source_formula,
            "sourceFormulaHash": source_formula_hash,
            "canonicalExpression": canonical_text,
            "expressionId": factor_expression_id,
            "canonicalAst": ast_to_dict(canonical) if dsl_supported and canonical is not None else None,
            "dslSupported": dsl_supported,
            "validationIssues": issues,
            "valueMutationPerformed": False,
        }
        definition_identity = {
            "factorId": factor_id,
            "sourceVersion": version,
            "sourceFormula": source_formula,
            "requiredFields": required_fields,
        }
        definition_id = stable_hash(definition_identity, prefix="factor_definition")
        existed = repository.get_factor_definition(definition_id) is not None
        repository.create_factor_definition(
            FactorDefinitionRecord(
                factorDefinitionId=definition_id,
                name=str(raw_definition.get("name") or factor_id),
                version=version,
                expression=source_formula,
                definition=definition_payload,
                contentHash=stable_hash(definition_payload),
            )
        )
        if not existed:
            new_definition_count += 1
        existing_evaluation = _summarize_existing_evaluation(evaluation_rows.get(factor_id))
        factor_results.append(
            {
                "factorId": factor_id,
                "factorDefinitionId": definition_id,
                "sourceFormula": source_formula,
                "sourceFormulaHash": source_formula_hash,
                "requiredFields": required_fields,
                "dslSupported": dsl_supported,
                "canonicalExpression": canonical_text,
                "expressionId": factor_expression_id,
                "validationIssues": issues,
                "existingLegacyCandidate": factor_id in existing_candidate_ids,
                "existingEvaluation": existing_evaluation,
                "formalResearchReady": False,
                "newKernelStatus": (
                    "blocked_missing_formal_statistical_evidence"
                    if dsl_supported
                    else "blocked_unsupported_or_invalid_dsl"
                ),
                "valueMutationPerformed": False,
            }
        )

    return {
        "factorCount": len(factor_results),
        "dslSupportedCount": supported_count,
        "dslBlockedCount": len(factor_results) - supported_count,
        "legacyCandidateFactorCount": len(existing_candidate_ids),
        "formalResearchReadyCount": 0,
        "newFactorDefinitionCount": new_definition_count,
        "totalRegisteredFactorDefinitionCount": repository.count("FactorDefinitions"),
        "manualReportPath": manual_path.as_posix(),
        "manualReportSha256": sha256_file(manual_path),
        "evaluationReportPath": evaluation_path.as_posix(),
        "evaluationReportSha256": sha256_file(evaluation_path),
        "valueMutationPerformed": False,
        "factorValuesLoaded": False,
        "factors": factor_results,
        "createsStrategyCandidate": False,
        "createsDemoRelease": False,
    }
