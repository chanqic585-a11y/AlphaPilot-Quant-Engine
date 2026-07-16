from __future__ import annotations

import pytest

from alphapilot.exit_policy import (
    ExitPolicy,
    ExitPolicyMode,
    canonical_exit_policy,
    exit_policy_hash,
    validate_exit_policy,
)


def test_fixed_r_below_two_is_valid_and_canonical() -> None:
    policy = ExitPolicy(
        mode=ExitPolicyMode.FIXED_R,
        maximumHoldBars=24,
        parameters={"targetR": 1.25},
    )

    canonical = canonical_exit_policy(policy)

    assert canonical == {
        "version": "advisory_r_exit_policy_v1",
        "mode": "fixed_r",
        "maximumHoldBars": 24,
        "initialStopMayWiden": False,
        "parameters": {"targetR": 1.25},
    }
    assert exit_policy_hash(policy) == exit_policy_hash(policy)


def test_structure_or_time_does_not_require_fixed_target() -> None:
    policy = ExitPolicy(
        mode=ExitPolicyMode.STRUCTURE_OR_TIME,
        maximumHoldBars=36,
        parameters={
            "structureRule": {
                "kind": "residual_neutral_zone",
                "absoluteZscoreMaximum": 0.35,
            }
        },
    )

    validate_exit_policy(policy)

    assert "targetR" not in canonical_exit_policy(policy)["parameters"]


def test_partial_then_trailing_requires_bounded_fraction_and_distance() -> None:
    valid = ExitPolicy(
        mode=ExitPolicyMode.PARTIAL_THEN_TRAILING,
        maximumHoldBars=48,
        parameters={
            "partialAtR": 0.8,
            "partialFraction": 0.4,
            "trailingAtrMultiple": 1.6,
        },
    )

    validate_exit_policy(valid)

    with pytest.raises(ValueError, match="partialFraction"):
        validate_exit_policy(
            ExitPolicy(
                mode=ExitPolicyMode.PARTIAL_THEN_TRAILING,
                maximumHoldBars=48,
                parameters={
                    "partialAtR": 0.8,
                    "partialFraction": 1.0,
                    "trailingAtrMultiple": 1.6,
                },
            )
        )

    with pytest.raises(ValueError, match="trailingAtrMultiple"):
        validate_exit_policy(
            ExitPolicy(
                mode=ExitPolicyMode.PARTIAL_THEN_TRAILING,
                maximumHoldBars=48,
                parameters={
                    "partialAtR": 0.8,
                    "partialFraction": 0.4,
                    "trailingAtrMultiple": 0.0,
                },
            )
        )


def test_hybrid_accepts_one_partial_and_one_bounded_remainder_rule() -> None:
    policy = ExitPolicy(
        mode=ExitPolicyMode.HYBRID,
        maximumHoldBars=60,
        parameters={
            "partialAtR": 1.0,
            "partialFraction": 0.5,
            "remainderMode": "structure",
            "structureRule": {
                "kind": "correlation_recovery",
                "minimumCorrelation": 0.72,
            },
        },
    )

    validate_exit_policy(policy)

    assert canonical_exit_policy(policy)["mode"] == "hybrid"


@pytest.mark.parametrize(
    ("parameters", "message"),
    [
        ({"targetR": 0.0}, "targetR"),
        ({"targetR": 1.0, "unexpected": True}, "unknown"),
    ],
)
def test_fixed_r_rejects_invalid_or_unknown_parameters(
    parameters: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        validate_exit_policy(
            ExitPolicy(
                mode=ExitPolicyMode.FIXED_R,
                maximumHoldBars=12,
                parameters=parameters,
            )
        )


def test_structure_rule_must_be_declarative_and_whitelisted() -> None:
    with pytest.raises(ValueError, match="unsupported structure rule"):
        validate_exit_policy(
            ExitPolicy(
                mode=ExitPolicyMode.STRUCTURE_OR_TIME,
                maximumHoldBars=12,
                parameters={
                    "structureRule": {
                        "kind": "python_callback",
                        "callback": "module.function",
                    }
                },
            )
        )


def test_maximum_hold_is_positive_and_initial_stop_cannot_widen() -> None:
    with pytest.raises(ValueError, match="maximumHoldBars"):
        validate_exit_policy(
            ExitPolicy(
                mode=ExitPolicyMode.FIXED_R,
                maximumHoldBars=0,
                parameters={"targetR": 1.0},
            )
        )

    with pytest.raises(ValueError, match="initial stop"):
        validate_exit_policy(
            ExitPolicy(
                mode=ExitPolicyMode.FIXED_R,
                maximumHoldBars=12,
                parameters={"targetR": 1.0},
                initialStopMayWiden=True,
            )
        )


def test_hash_changes_when_exit_policy_parameters_change() -> None:
    first = ExitPolicy(
        mode=ExitPolicyMode.FIXED_R,
        maximumHoldBars=24,
        parameters={"targetR": 1.25},
    )
    second = ExitPolicy(
        mode=ExitPolicyMode.FIXED_R,
        maximumHoldBars=24,
        parameters={"targetR": 1.5},
    )

    assert exit_policy_hash(first) != exit_policy_hash(second)
