"""SQLite-backed projection and append-only history for acquired artifacts."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import replace
from typing import Any

from alphapilot.evolution.registry.hashing import canonical_json, stable_hash

from .lifecycle import validate_transition
from .lineage import artifact_content_hash, lifecycle_event_hash
from .models import StrategyArtifact, utc_now


class StrategyArtifactStore:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def register(self, artifact: StrategyArtifact) -> StrategyArtifact:
        if not artifact.authorityRef.strip():
            raise ValueError("authorityRef is required for projection-only artifacts")
        content_hash = artifact_content_hash(artifact)
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO StrategyArtifacts(
                  artifactId, artifactType, name, familyId,
                  sourceEquivalenceClass, status, authorityRef, artifactJson,
                  contentHash, createdAt, updatedAt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact.artifactId,
                    artifact.artifactType,
                    artifact.name,
                    artifact.familyId,
                    artifact.sourceEquivalenceClass,
                    artifact.status,
                    artifact.authorityRef,
                    canonical_json(artifact.to_dict()),
                    content_hash,
                    artifact.createdAt,
                    artifact.updatedAt,
                ),
            )
            self._append_event(
                artifact.artifactId,
                previous_status=None,
                next_status=artifact.status,
                reason_code="artifact_registered",
                evidence={"authorityRef": artifact.authorityRef, "contentHash": content_hash},
            )
        return artifact

    def get(self, artifact_id: str) -> StrategyArtifact | None:
        row = self.connection.execute(
            "SELECT artifactJson FROM StrategyArtifacts WHERE artifactId = ?",
            (artifact_id,),
        ).fetchone()
        return StrategyArtifact.from_dict(json.loads(row[0])) if row else None

    def list(self, *, status: str | None = None) -> list[StrategyArtifact]:
        if status is None:
            rows = self.connection.execute(
                "SELECT artifactJson FROM StrategyArtifacts ORDER BY createdAt, artifactId"
            ).fetchall()
        else:
            rows = self.connection.execute(
                "SELECT artifactJson FROM StrategyArtifacts WHERE status = ? ORDER BY createdAt, artifactId",
                (status,),
            ).fetchall()
        return [StrategyArtifact.from_dict(json.loads(row[0])) for row in rows]

    def transition(
        self,
        artifact_id: str,
        next_status: str,
        *,
        reason_code: str,
        evidence: dict[str, Any],
    ) -> StrategyArtifact:
        current = self.get(artifact_id)
        if current is None:
            raise KeyError(artifact_id)
        validate_transition(current.status, next_status)
        updated = replace(current, status=next_status, updatedAt=utc_now())
        content_hash = artifact_content_hash(updated)
        with self.connection:
            self.connection.execute(
                """
                UPDATE StrategyArtifacts
                SET status = ?, artifactJson = ?, contentHash = ?, updatedAt = ?
                WHERE artifactId = ?
                """,
                (
                    next_status,
                    canonical_json(updated.to_dict()),
                    content_hash,
                    updated.updatedAt,
                    artifact_id,
                ),
            )
            self._append_event(
                artifact_id,
                previous_status=current.status,
                next_status=next_status,
                reason_code=reason_code,
                evidence=evidence,
            )
        return updated

    def lifecycle_history(self, artifact_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT eventId, artifactId, previousStatus, nextStatus, reasonCode,
                   evidenceJson, previousEventHash, eventHash, createdAt
            FROM ArtifactLifecycleEvents
            WHERE artifactId = ?
            ORDER BY createdAt, eventId
            """,
            (artifact_id,),
        ).fetchall()
        return [
            {
                "eventId": row[0],
                "artifactId": row[1],
                "previousStatus": row[2],
                "nextStatus": row[3],
                "reasonCode": row[4],
                "evidence": json.loads(row[5]),
                "previousEventHash": row[6],
                "eventHash": row[7],
                "createdAt": row[8],
            }
            for row in rows
        ]

    def record_bench(
        self, artifact_id: str, bench_type: str, result: dict[str, Any]
    ) -> str:
        if self.get(artifact_id) is None:
            raise KeyError(artifact_id)
        created_at = utc_now()
        payload = {
            "artifactId": artifact_id,
            "benchType": bench_type,
            "result": result,
            "createdAt": created_at,
        }
        content_hash = stable_hash(payload, prefix="artifact_bench")
        bench_id = f"bench_{uuid.uuid4().hex}"
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO ArtifactBenchHistory(
                  benchId, artifactId, benchType, resultJson, contentHash, createdAt
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    bench_id,
                    artifact_id,
                    bench_type,
                    canonical_json(result),
                    content_hash,
                    created_at,
                ),
            )
        return bench_id

    def _append_event(
        self,
        artifact_id: str,
        *,
        previous_status: str | None,
        next_status: str,
        reason_code: str,
        evidence: dict[str, Any],
    ) -> None:
        previous_row = self.connection.execute(
            """
            SELECT eventHash FROM ArtifactLifecycleEvents
            WHERE artifactId = ? ORDER BY createdAt DESC, eventId DESC LIMIT 1
            """,
            (artifact_id,),
        ).fetchone()
        previous_hash = previous_row[0] if previous_row else None
        created_at = utc_now()
        payload: dict[str, object] = {
            "artifactId": artifact_id,
            "previousStatus": previous_status,
            "nextStatus": next_status,
            "reasonCode": reason_code,
            "evidence": evidence,
            "previousEventHash": previous_hash,
            "createdAt": created_at,
        }
        event_hash = lifecycle_event_hash(payload)
        event_id = f"artifact_event_{uuid.uuid4().hex}"
        self.connection.execute(
            """
            INSERT INTO ArtifactLifecycleEvents(
              eventId, artifactId, previousStatus, nextStatus, reasonCode,
              evidenceJson, previousEventHash, eventHash, createdAt
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                artifact_id,
                previous_status,
                next_status,
                reason_code,
                canonical_json(evidence),
                previous_hash,
                event_hash,
                created_at,
            ),
        )
