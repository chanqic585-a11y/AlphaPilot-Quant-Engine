"""Independent versioned policy-object metadata for the V18 formal core."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from .capacity_model import CAPACITY_POLICY_V1
from .correlation_cluster_policy import CLUSTER_POLICY_V1
from .portfolio_beta_policy import BETA_POLICY_V1
from .signal_ranking_policy import RANKING_POLICY_V1


@dataclass(frozen=True)
class VersionedPolicyObject:
    policy_id: str
    version: str
    schema_version: str
    definition_hash: str
    definition: Mapping[str, Any]


def _object(policy_id: str, version: str, definition: Mapping[str, Any]) -> VersionedPolicyObject:
    frozen_definition = MappingProxyType(deepcopy(dict(definition)))
    return VersionedPolicyObject(
        policy_id=policy_id,
        version=version,
        schema_version=str(frozen_definition["schemaVersion"]),
        definition_hash=str(frozen_definition["definitionHash"]),
        definition=frozen_definition,
    )


def build_v18_policy_objects() -> dict[str, VersionedPolicyObject]:
    """Expose unchanged policies as separately versioned immutable objects."""

    return {
        "capacity": _object("capacity", "1", CAPACITY_POLICY_V1),
        "cluster": _object("cluster", "1", CLUSTER_POLICY_V1),
        "beta": _object("beta", "1", BETA_POLICY_V1),
        "ranking": _object("ranking", "1", RANKING_POLICY_V1),
    }
