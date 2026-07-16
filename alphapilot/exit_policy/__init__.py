"""Public Advisory-R exit-policy API."""

from .canonical import canonical_exit_policy, exit_policy_from_dict, exit_policy_hash
from .engine import replay_exit_policy
from .exit_legs import ExitCosts, ExitExecutionResult, ExitLeg
from .legacy_adapter import legacy_fixed_r_policy, replay_legacy_candidate_exit
from .models import ExitPolicy, ExitPolicyMode
from .reporting import exit_execution_to_dict
from .validation import validate_exit_policy

__all__ = [
    "ExitPolicy",
    "ExitPolicyMode",
    "ExitCosts",
    "ExitExecutionResult",
    "ExitLeg",
    "canonical_exit_policy",
    "exit_execution_to_dict",
    "exit_policy_from_dict",
    "exit_policy_hash",
    "legacy_fixed_r_policy",
    "replay_exit_policy",
    "replay_legacy_candidate_exit",
    "validate_exit_policy",
]
