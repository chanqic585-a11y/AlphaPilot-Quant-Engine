"""Deterministic numeric comparison labels for independently computed fixtures."""

from __future__ import annotations

import numpy as np


def classify_numeric_match(
    actual: np.ndarray,
    expected: np.ndarray,
    *,
    tolerance: float = 1e-10,
    known_semantic_deviation: bool = False,
) -> str:
    if actual.shape != expected.shape:
        return "unexpected_mismatch"
    if np.array_equal(actual, expected, equal_nan=True):
        return "exact_match"
    if np.allclose(actual, expected, atol=tolerance, rtol=tolerance, equal_nan=True):
        return "tolerance_match"
    if known_semantic_deviation:
        return "known_semantic_deviation"
    return "unexpected_mismatch"
