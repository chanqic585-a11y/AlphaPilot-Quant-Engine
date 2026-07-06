"""Generate V13.5.22 Alpha191 factor extraction report.

This module reads a user-provided local Alpha191 learning PDF text extraction
and converts it into a copyright-safe research catalog. It stores categories,
operator tags, required fields, implementation notes, and source metadata only.
It does not copy full formulas or long source explanations.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphapilot.reports.generate_v13_5_derivatives_ml_strategy_report import write_json, write_text


VERSION = "V13.5.22"
REPORT_ID = "v13_5_22_alpha191_factor_extraction_report"
DEFAULT_SOURCE_TEXT = Path("tmp/pdfs/alpha191_extracted_text.txt")
DEFAULT_OUTPUT_REPORT = Path("reports/v13_5_22_alpha191_factor_extraction_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_5_22_alpha191_factor_extraction_summary.md")
DEFAULT_OUTPUT_CATALOG = Path("reports/v13_5_22_alpha191_factor_candidate_catalog.json")

HEADER_RE = re.compile(r"^Alpha(\d{3})\s*-\s*(.+)$", re.M)

OPERATOR_PATTERNS = {
    "rank": ["RANK("],
    "ts_rank": ["TSRANK("],
    "corr": ["CORR("],
    "delta": ["DELTA("],
    "delay": ["DELAY("],
    "sum": ["SUM("],
    "mean": ["MEAN("],
    "std": ["STD("],
    "sma": ["SMA("],
    "wma": ["WMA("],
    "decay_linear": ["DECAYLINEAR("],
    "count": ["COUNT("],
    "sum_if": ["SUMIF("],
    "regression_beta": ["REGBETA("],
    "regression_residual": ["REGRESI", "RESIDUAL"],
    "min": ["MIN("],
    "max": ["MAX("],
    "log": ["LOG("],
    "sign": ["SIGN("],
    "conditional": ["?", ":"],
}

FIELD_PATTERNS = {
    "open": ["OPEN"],
    "high": ["HIGH"],
    "low": ["LOW"],
    "close": ["CLOSE"],
    "vwap": ["VWAP"],
    "volume": ["VOLUME"],
    "amount": ["AMOUNT"],
    "return": ["RET"],
    "benchmark": ["BENCH", "INDEX", "MKT", "市场"],
}

KNOWN_REVIEW_FACTORS = {
    "Alpha022": "SMEAN function semantics are unclear in the source note and need manual platform review.",
    "Alpha023": "Source note flags extraction or spelling issues that require manual review.",
    "Alpha052": "Source note flags extraction or spelling issues that require manual review.",
    "Alpha131": "Source note flags extraction or spelling issues that require manual review.",
    "Alpha159": "Source note flags extraction or spelling issues that require manual review.",
    "Alpha188": "Source note flags extraction or spelling issues that require manual review.",
}

CATEGORY_ADAPTATION = {
    "量价相关/协同": {
        "cluster": "volume_price_correlation",
        "summary": "Use as crypto price-volume interaction factors: rolling correlation, volume pressure, liquidity confirmation, and cross-sectional rank overlays.",
    },
    "动量反转/均值回复": {
        "cluster": "momentum_reversal",
        "summary": "Use as exhaustion, rebound, and mean-reversion context. Keep 2R evaluation and avoid treating a single indicator as an entry command.",
    },
    "成交量/资金活跃": {
        "cluster": "liquidity_activity",
        "summary": "Use as liquidity, activity, and volume-ratio filters for avoiding thin or noisy candidates.",
    },
    "波动振幅/日内结构": {
        "cluster": "volatility_range_structure",
        "summary": "Use as wick, range, volatility compression, breakout, and failed-breakout context for crypto OHLCV panels.",
    },
    "市场联动/回归": {
        "cluster": "btc_beta_residual",
        "summary": "Adapt market-linkage factors to BTC/ETH beta, residual return, and regime filters rather than equity index linkage.",
    },
    "排序位置/相对强弱": {
        "cluster": "relative_strength_rank",
        "summary": "Use as cross-sectional relative-strength and time-series rank features across the active crypto universe.",
    },
    "综合价格形态": {
        "cluster": "price_pattern_composite",
        "summary": "Use as composite candle and price-structure context. Treat as explainability features before strategy gates.",
    },
    "条件统计/规则触发": {
        "cluster": "event_condition_trigger",
        "summary": "Use as event gates or state triggers, then validate with walk-forward and stress tests.",
    },
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _read_source_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(
            f"Source text not found: {path}. Extract the user-provided PDF to this UTF-8 text path first."
        )
    return path.read_text(encoding="utf-8")


def _factor_blocks(text: str) -> list[tuple[str, str, str]]:
    headers = list(HEADER_RE.finditer(text))
    blocks: list[tuple[str, str, str]] = []
    for idx, match in enumerate(headers):
        start = match.end()
        end = headers[idx + 1].start() if idx + 1 < len(headers) else len(text)
        factor_id = f"Alpha{match.group(1)}"
        category = match.group(2).strip()
        blocks.append((factor_id, category, text[start:end]))
    return blocks


def _formula_excerpt(block: str) -> str:
    lines: list[str] = []
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("--- PAGE"):
            continue
        if line.startswith("关键拆解") or line.startswith("一句话") or line.startswith("从里到外"):
            break
        lines.append(line)
    return " ".join(lines)


def _operator_tags(formula_text: str) -> list[str]:
    upper = formula_text.upper()
    tags = []
    for tag, patterns in OPERATOR_PATTERNS.items():
        if all(pattern in upper for pattern in patterns) if tag == "conditional" else any(pattern in upper for pattern in patterns):
            tags.append(tag)
    return sorted(tags)


def _required_fields(formula_text: str) -> list[str]:
    upper = formula_text.upper()
    fields = []
    for field, patterns in FIELD_PATTERNS.items():
        if any(pattern in upper for pattern in patterns):
            fields.append(field)
    return sorted(fields)


def _window_numbers(formula_text: str) -> list[int]:
    numbers = []
    for token in re.findall(r"(?<![\d.])\d+(?![\d.])", formula_text):
        value = int(token)
        if 2 <= value <= 252:
            numbers.append(value)
    return sorted(set(numbers))


def _formula_summary(category: str, operators: list[str], fields: list[str]) -> str:
    adaptation = CATEGORY_ADAPTATION.get(category, {})
    cluster = adaptation.get("cluster", "uncategorized")
    field_text = ", ".join(fields) if fields else "field review needed"
    operator_text = ", ".join(operators) if operators else "basic arithmetic or comparison"
    return f"{cluster} factor using {operator_text} over {field_text}; full formula intentionally not stored."


def _priority(category: str, operators: list[str], fields: list[str], review_notes: list[str]) -> str:
    if review_notes:
        return "low"
    if "benchmark" in fields:
        return "medium"
    if "regression_beta" in operators or "regression_residual" in operators:
        return "medium"
    if category in {"动量反转/均值回复", "成交量/资金活跃", "波动振幅/日内结构"}:
        return "high"
    if category == "量价相关/协同" and {"close", "volume"}.issubset(set(fields)):
        return "high"
    if "rank" in operators or "ts_rank" in operators or "corr" in operators:
        return "medium"
    return "medium"


def _crypto_notes(category: str, fields: list[str], operators: list[str], review_notes: list[str]) -> list[str]:
    adaptation = CATEGORY_ADAPTATION.get(category, {})
    notes = [adaptation.get("summary", "Review before adapting this factor to crypto OHLCV data.")]
    if "vwap" in fields:
        notes.append("Crypto OHLCV files may not include true tick VWAP; use exchange VWAP when available or a documented OHLCV proxy.")
    if "amount" in fields:
        notes.append("Amount can be approximated from close * volume only when quote-volume is unavailable; mark the proxy explicitly.")
    if "benchmark" in fields:
        notes.append("Equity-market benchmark semantics should be mapped to BTC, ETH, or a documented crypto market index proxy.")
    if "rank" in operators or "ts_rank" in operators:
        notes.append("Ranking features require stable universe membership and missing-data handling before backtesting.")
    if "corr" in operators:
        notes.append("Rolling correlation factors should be stress-tested across bull, bear, sideways, and crash regimes.")
    notes.extend(review_notes)
    return notes


def _candidate_clusters(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        clusters[record["cryptoAdaptationCluster"]].append(record)

    rows: list[dict[str, Any]] = []
    for cluster, items in sorted(clusters.items()):
        priority_counts = Counter(item["implementationPriority"] for item in items)
        high_examples = [
            {
                "factorId": item["factorId"],
                "category": item["category"],
                "operatorTags": item["operatorTags"],
                "requiredFields": item["requiredFields"],
                "copyrightSafeFormulaSummary": item["copyrightSafeFormulaSummary"],
            }
            for item in items
            if item["implementationPriority"] == "high"
        ][:10]
        rows.append(
            {
                "clusterId": cluster,
                "factorCount": len(items),
                "priorityCounts": dict(sorted(priority_counts.items())),
                "highPriorityExamples": high_examples,
                "nextResearchUse": _cluster_next_use(cluster),
            }
        )
    return rows


def _cluster_next_use(cluster: str) -> str:
    mapping = {
        "volume_price_correlation": "Add as volume-price confirmation overlays for existing high-reward event filters.",
        "momentum_reversal": "Use as candidate exhaustion and rebound features for fixed 2R historical replay.",
        "liquidity_activity": "Use as liquidity gates and thin-market filters before signal selection.",
        "volatility_range_structure": "Use as failed-breakout, wick, range compression, and volatility context.",
        "btc_beta_residual": "Use for BTC/ETH beta and residual filters, not equity-index assumptions.",
        "relative_strength_rank": "Use for universe-wide rank features after dynamic universe quality checks.",
        "price_pattern_composite": "Use as explainability features in the factor panel before strategy gating.",
        "event_condition_trigger": "Use as explicit event gates with walk-forward validation.",
    }
    return mapping.get(cluster, "Manual review required before implementation.")


def _aggregate(records: list[dict[str, Any]]) -> dict[str, Any]:
    category_counts = Counter(record["category"] for record in records)
    priority_counts = Counter(record["implementationPriority"] for record in records)
    operator_counts = Counter(tag for record in records for tag in record["operatorTags"])
    field_counts = Counter(field for record in records for field in record["requiredFields"])
    review_count = sum(1 for record in records if record["manualReviewNotes"])
    return {
        "factorCount": len(records),
        "categoryCounts": dict(category_counts),
        "implementationPriorityCounts": dict(priority_counts),
        "operatorCounts": dict(operator_counts.most_common()),
        "requiredFieldCounts": dict(field_counts.most_common()),
        "manualReviewFactorCount": review_count,
        "formulaTextStored": False,
        "longSourceTextStored": False,
    }


def _build_records(text: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for factor_id, category, block in _factor_blocks(text):
        formula_text = _formula_excerpt(block)
        operators = _operator_tags(formula_text)
        fields = _required_fields(formula_text)
        windows = _window_numbers(formula_text)
        review_notes = []
        if factor_id in KNOWN_REVIEW_FACTORS:
            review_notes.append(KNOWN_REVIEW_FACTORS[factor_id])
        adaptation = CATEGORY_ADAPTATION.get(category, {})
        records.append(
            {
                "factorId": factor_id,
                "category": category,
                "cryptoAdaptationCluster": adaptation.get("cluster", "uncategorized"),
                "operatorTags": operators,
                "requiredFields": fields,
                "windowCandidates": windows[:12],
                "implementationPriority": _priority(category, operators, fields, review_notes),
                "copyrightSafeFormulaSummary": _formula_summary(category, operators, fields),
                "cryptoAdaptationNotes": _crypto_notes(category, fields, operators, review_notes),
                "manualReviewNotes": review_notes,
                "formulaCopied": False,
                "longExplanationCopied": False,
            }
        )
    return records


def _summary_markdown(report: dict[str, Any]) -> str:
    aggregate = report["aggregate"]
    lines = [
        "# AlphaPilot V13.5.22 Alpha191 Factor Extraction",
        "",
        "This report extracts Alpha191 factor metadata from a user-provided local PDF.",
        "It stores categories, operator tags, required fields, implementation notes, and citation metadata only.",
        "It does not copy full formulas or long source explanations.",
        "",
        "## Source Metadata",
        "",
        f"- title: {report['sourceMetadata']['title']}",
        f"- sourceType: {report['sourceMetadata']['sourceType']}",
        f"- citation: {report['sourceMetadata']['citation']}",
        f"- copyrightPolicy: {report['sourceMetadata']['copyrightPolicy']}",
        "",
        "## Extraction Summary",
        "",
        f"- factorCount: {aggregate['factorCount']}",
        f"- formulaTextStored: {aggregate['formulaTextStored']}",
        f"- longSourceTextStored: {aggregate['longSourceTextStored']}",
        f"- manualReviewFactorCount: {aggregate['manualReviewFactorCount']}",
        "",
        "## Category Counts",
        "",
    ]
    for category, count in aggregate["categoryCounts"].items():
        lines.append(f"- {category}: {count}")
    lines.extend(["", "## Implementation Priority Counts", ""])
    for priority, count in aggregate["implementationPriorityCounts"].items():
        lines.append(f"- {priority}: {count}")
    lines.extend(["", "## Top Operator Tags", ""])
    for operator, count in list(aggregate["operatorCounts"].items())[:15]:
        lines.append(f"- {operator}: {count}")
    lines.extend(["", "## Candidate Clusters", ""])
    for cluster in report["candidateClusters"]:
        lines.append(
            f"- {cluster['clusterId']}: factors={cluster['factorCount']}, "
            f"priority={cluster['priorityCounts']}, next={cluster['nextResearchUse']}"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- alpha191MetadataExtracted: {report['decision']['alpha191MetadataExtracted']}",
            f"- readyForFactorImplementationSpec: {report['decision']['readyForFactorImplementationSpec']}",
            f"- exchangeDryRunApproved: {report['decision']['exchangeDryRunApproved']}",
            f"- liveTradingApproved: {report['decision']['liveTradingApproved']}",
            f"- nextAction: {report['decision']['nextAction']}",
            "",
            "## Safety Boundary",
            "",
            "- Research metadata only.",
            "- No full formula copying.",
            "- No Trade API.",
            "- No Withdraw API.",
            "- No API key storage.",
            "- No real account reads.",
            "- No real position reads.",
            "- No order creation.",
            "- No automatic trading.",
        ]
    )
    return "\n".join(lines) + "\n"


def generate_report(source_text: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    text = _read_source_text(source_text)
    records = _build_records(text)
    if len(records) != 191:
        raise ValueError(f"Expected 191 Alpha factors, found {len(records)}")

    aggregate = _aggregate(records)
    clusters = _candidate_clusters(records)
    catalog = {
        "version": VERSION,
        "catalogId": "v13_5_22_alpha191_factor_candidate_catalog",
        "generatedAt": utc_now(),
        "sourceTextPathUsedForExtraction": str(source_text),
        "formulaTextStored": False,
        "longSourceTextStored": False,
        "factorRecords": records,
        "candidateClusters": clusters,
    }
    report = {
        "version": VERSION,
        "reportId": REPORT_ID,
        "generatedAt": utc_now(),
        "status": "completed",
        "sourceMetadata": {
            "sourceType": "user_provided_local_pdf_text_extraction",
            "title": "Alpha 191 因子公式小白学习手册",
            "sourceNotes": [
                "The PDF describes Alpha191 formula learning notes and cites the original Guotai Junan short-cycle price-volume factor table as the underlying formula source.",
                "The PDF also notes that BigQuant formula pages were used to cross-check extraction issues.",
                "AlphaPilot stores only metadata, short summaries, categories, and implementation notes from this user-provided document.",
            ],
            "license": "user_provided_local_reference_unknown_license",
            "citation": "User-provided local PDF: Alpha191因子公式小白学习手册.pdf, reviewed on 2026-07-06.",
            "copyrightPolicy": "Only URL/path metadata, source summary, citation, categories, operator tags, and short implementation notes are stored; full formulas and long explanations are not copied.",
        },
        "aggregate": aggregate,
        "candidateClusters": clusters,
        "manualReviewFactors": [
            {
                "factorId": record["factorId"],
                "notes": record["manualReviewNotes"],
            }
            for record in records
            if record["manualReviewNotes"]
        ],
        "decision": {
            "alpha191MetadataExtracted": True,
            "readyForFactorImplementationSpec": True,
            "strategyChanged": False,
            "paperTradingChanged": False,
            "exchangeDryRunApproved": False,
            "liveTradingApproved": False,
            "nextAction": "Design a small crypto-safe Alpha191-inspired factor implementation subset, then evaluate it against existing V13.5 local paper candidate gates.",
        },
        "safetyBoundary": {
            "researchOnly": True,
            "fullFormulasCopied": False,
            "longSourceTextCopied": False,
            "tradeApi": False,
            "withdrawApi": False,
            "apiKeyStorage": False,
            "realAccountReads": False,
            "realPositionReads": False,
            "orderCreation": False,
            "automaticTrading": False,
        },
    }
    return report, catalog


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate V13.5.22 Alpha191 factor extraction report.")
    parser.add_argument("--source-text", type=Path, default=DEFAULT_SOURCE_TEXT)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-catalog", type=Path, default=DEFAULT_OUTPUT_CATALOG)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    report, catalog = generate_report(args.source_text)
    write_json(args.output_report, report)
    write_json(args.output_catalog, catalog)
    write_text(args.output_summary, _summary_markdown(report))
    print(f"wrote {args.output_report}")
    print(f"wrote {args.output_catalog}")
    print(f"wrote {args.output_summary}")


if __name__ == "__main__":
    main()
