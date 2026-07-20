"""Run one bounded V36 campaign through the V35 research service."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from alphapilot.automatic_candidate_research import AutomaticCandidateResearchExecutor
from alphapilot.research_service import (
    ResearchService,
    ResearchServicePolicy,
    ResearchServiceStateStore,
)
from alphapilot.standard_replication import ReplicationSourceRegistry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--job-json", required=True, type=Path)
    parser.add_argument("--registry-path", type=Path)
    parser.add_argument("--now", required=True)
    parser.add_argument("--owner", default="v36-candidate-research-cli")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    campaign_input = json.loads(args.job_json.read_text(encoding="utf-8"))
    if not isinstance(campaign_input, dict):
        raise ValueError("campaign_input_must_be_object")
    campaign_id = str(campaign_input.get("campaignId") or "").strip()
    family_ids = tuple(str(value) for value in campaign_input.get("familyIds") or [])
    candidate_ids = tuple(
        str(value) for value in campaign_input.get("candidateIds") or []
    )
    registry_path = args.registry_path or (
        args.repo_root
        / "research/source_registry/strategy_research_source_registry.json"
    )
    registry = ReplicationSourceRegistry.load(registry_path)
    policy = ResearchServicePolicy.default()
    state_root = Path(args.state_root)
    state_store = ResearchServiceStateStore(
        state_root / "research_service_state.json",
        policy=policy,
    )
    executor = AutomaticCandidateResearchExecutor(
        registry=registry,
        output_root=args.output_root,
        campaign_inputs={campaign_id: campaign_input},
        max_formal_runs=policy.max_formal_runs_per_campaign,
    )
    service = ResearchService(
        policy=policy,
        state_store=state_store,
        executor=executor,
        lease_path=state_root / "research_service.lock",
        receipt_path=state_root / "research_cycle_receipts.jsonl",
        owner=args.owner,
    )
    state = state_store.load_or_initialize(now=args.now)
    existing = next(
        (job for job in state["jobs"] if job.get("campaignId") == campaign_id),
        None,
    )
    if existing is None:
        service.enqueue(
            campaign_id=campaign_id,
            family_ids=family_ids,
            candidate_ids=candidate_ids,
            queued_at=str(campaign_input.get("createdAt") or args.now),
        )
        receipt = service.run_cycle(now=args.now)
    elif existing.get("status") == "queued":
        receipt = service.run_cycle(now=args.now)
    else:
        receipt = dict(existing.get("result") or {})
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
