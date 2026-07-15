"""Generate Phase 4 immutable strategy-validation release contracts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from alphapilot.evolution.promotion.demo_risk_profile import build_demo_risk_profile
from alphapilot.evolution.promotion.strategy_validation_release import (
    build_strategy_validation_releases,
    write_strategy_validation_releases,
)
from alphapilot.evolution.registry.hashing import canonical_json


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def generate(*, campaign_dir: Path, preregistration_path: Path, created_at: str | None = None) -> dict:
    campaign_dir = Path(campaign_dir).resolve()
    preregistration = _read(Path(preregistration_path).resolve())
    summary = _read(campaign_dir / "campaign_summary.json")
    manifest = _read(campaign_dir / "artifact_manifest.json")
    evidences = [_read(path) for path in sorted((campaign_dir / "formal_pass_evidence").glob("*.json"))]
    risk_profile = build_demo_risk_profile()
    generated_at = created_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    releases = build_strategy_validation_releases(
        evidences=evidences,
        preregistration=preregistration,
        campaign_summary=summary,
        artifact_manifest=manifest,
        risk_profile=risk_profile,
        created_at=generated_at,
    )
    release_dir = campaign_dir / "candidate_releases"
    paths = write_strategy_validation_releases(releases, release_dir)
    (release_dir / "demo_risk_profile.json").write_text(canonical_json(risk_profile), encoding="utf-8")
    result = {
        "schemaVersion": "strategy_validation_release_generation_v1",
        "campaignId": summary["campaignId"],
        "formalPassCount": int(summary.get("formalPassCount") or 0),
        "releaseCount": len(releases),
        "releaseHashes": [row["releaseHash"] for row in releases],
        "releasePaths": [path.as_posix() for path in paths],
        "riskConfigHash": risk_profile["riskConfigHash"],
        "ordersCreated": 0,
        "approvalRecordsCreated": 0,
        "status": "completed",
    }
    (release_dir / "generation_summary.json").write_text(canonical_json(result), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--preregistration", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(generate(campaign_dir=args.campaign_dir, preregistration_path=args.preregistration), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
