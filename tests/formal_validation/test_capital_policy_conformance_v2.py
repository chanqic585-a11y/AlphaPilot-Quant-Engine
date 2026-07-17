from __future__ import annotations
from copy import deepcopy

from alphapilot.formal_validation.capital_policy_conformance import (
    audit_capital_policy_v2,
    verify_capital_policy_v2,
)
from alphapilot.formal_validation.executable_capital_policy import (
    build_capital_policy_v2,
)
from alphapilot.formal_validation.formal_reporting import (
    audit_executable_formal_contract,
)


def test_v2_policy_is_complete_for_the_existing_pre_run_audit() -> None:
    policy = build_capital_policy_v2()

    assert audit_executable_formal_contract({"capitalCompetitionPolicy": policy}) == []
    assert audit_capital_policy_v2(policy) == []
    assert verify_capital_policy_v2(policy) is True


def test_any_result_affecting_policy_mutation_breaks_conformance() -> None:
    policy = deepcopy(build_capital_policy_v2())
    policy["maximum_portfolio_beta"] = 1.6

    issues = audit_capital_policy_v2(policy)

    assert verify_capital_policy_v2(policy) is False
    assert {row["code"] for row in issues} == {"capital_policy_contract_mismatch"}
