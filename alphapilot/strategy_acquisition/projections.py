"""Read-only export projections for acquisition evidence packages."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .store import StrategyArtifactStore


def export_artifact_projections(
    store: StrategyArtifactStore, output_dir: Path
) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    artifacts = store.list()
    inventory = output / "source_inventory.json"
    inventory.write_text(
        json.dumps([item.to_dict() for item in artifacts], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    matrix = output / "source_equivalence_matrix.csv"
    with matrix.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "artifactId",
                "familyId",
                "sourceEquivalenceClass",
                "authorityRef",
                "status",
            ),
        )
        writer.writeheader()
        for item in artifacts:
            writer.writerow(
                {
                    "artifactId": item.artifactId,
                    "familyId": item.familyId,
                    "sourceEquivalenceClass": item.sourceEquivalenceClass,
                    "authorityRef": item.authorityRef,
                    "status": item.status,
                }
            )
    history = output / "artifact_lifecycle_history.jsonl"
    with history.open("w", encoding="utf-8", newline="\n") as handle:
        for artifact in artifacts:
            for event in store.lifecycle_history(artifact.artifactId):
                handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return {
        "sourceInventory": inventory,
        "sourceEquivalenceMatrix": matrix,
        "artifactLifecycleHistory": history,
    }
