"""Immutable identity records for external research references."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash


@dataclass(frozen=True)
class ExternalReference:
    reference_id: str
    source_type: str
    repository_or_file: str
    commit_or_hash: str
    license_status: str
    retrieved_at: str
    read_only: bool
    source_path: str

    @classmethod
    def create(
        cls,
        *,
        source_type: str,
        repository_or_file: str,
        commit_or_hash: str,
        license_status: str,
        source_path: str,
        retrieved_at: str,
    ) -> "ExternalReference":
        identity = {
            "sourceType": source_type,
            "repositoryOrFile": repository_or_file,
            "commitOrHash": commit_or_hash,
        }
        return cls(
            reference_id=stable_hash(identity, prefix="external_reference"),
            source_type=source_type,
            repository_or_file=repository_or_file,
            commit_or_hash=commit_or_hash,
            license_status=license_status,
            retrieved_at=retrieved_at,
            read_only=True,
            source_path=source_path,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "referenceId": self.reference_id,
            "sourceType": self.source_type,
            "repositoryOrFile": self.repository_or_file,
            "commitOrHash": self.commit_or_hash,
            "licenseStatus": self.license_status,
            "retrievedAt": self.retrieved_at,
            "readOnly": self.read_only,
            "sourcePath": self.source_path,
        }
