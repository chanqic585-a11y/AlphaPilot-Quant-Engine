"""Portable Factor Lab evidence exports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from .compare import rank_factor_bench
from .registry import FactorRegistry


def write_factor_lab_reports(
    output_dir: Path,
    *,
    registry: FactorRegistry,
    bench_rows: Iterable[dict[str, Any]],
    similarity_rows: Iterable[dict[str, Any]],
    dedup_decisions: Iterable[dict[str, Any]],
) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    registry_path = output / "factor_registry.json"
    bench_path = output / "factor_bench_matrix.csv"
    similarity_path = output / "artifact_similarity_matrix.parquet"
    dedup_path = output / "candidate_dedup_decision.json"
    registry_path.write_text(
        json.dumps(registry.to_rows(), indent=2, sort_keys=True), encoding="utf-8"
    )
    pd.DataFrame(rank_factor_bench(bench_rows)).to_csv(
        bench_path, index=False, encoding="utf-8"
    )
    pd.DataFrame(list(similarity_rows)).to_parquet(similarity_path, index=False)
    dedup_path.write_text(
        json.dumps(list(dedup_decisions), indent=2, sort_keys=True), encoding="utf-8"
    )
    return {
        "factorRegistry": registry_path,
        "factorBenchMatrix": bench_path,
        "artifactSimilarityMatrix": similarity_path,
        "candidateDedupDecision": dedup_path,
    }
