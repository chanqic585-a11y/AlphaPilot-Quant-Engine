"""Certify the V18.2 pre-result formal evidence chain."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from alphapilot.formal_validation.formal_evidence_chain_fixture import (
    run_formal_evidence_chain_fixture,
    write_formal_evidence_chain_certification,
)
from alphapilot.formal_validation.freqtrade_runtime import PINNED_FREQTRADE_IMAGE
from alphapilot.formal_validation.freqtrade_runtime_loader import (
    FreqtradeRuntimeRequest,
    load_freqtrade_runtime,
)


RuntimeLoader = Callable[..., dict[str, Any]]


def certify(
    *,
    repo_root: Path,
    config_path: Path,
    data_root: Path,
    timerange: str,
    output_root: Path,
    runtime_loader: RuntimeLoader = load_freqtrade_runtime,
) -> dict[str, Any]:
    """Run the synthetic fixture only after the exact runtime attests."""

    repo_root = Path(repo_root).resolve(strict=True)
    request = FreqtradeRuntimeRequest(
        image_reference=PINNED_FREQTRADE_IMAGE,
        strategy_module="user_data.strategies.AlphaPilotS01BearRecovery4H",
        strategy_class="AlphaPilotS01BearRecovery4H",
        config_path=Path(config_path),
        data_root=Path(data_root),
        timerange=timerange,
    )
    runtime_report = runtime_loader(request, repo_root=repo_root)
    fixture_report = run_formal_evidence_chain_fixture(
        runtime_report=runtime_report
    )
    write_formal_evidence_chain_certification(
        output_root=Path(output_root),
        runtime_report=runtime_report,
        fixture_report=fixture_report,
    )
    certification_path = (
        Path(output_root).resolve()
        / "formal_evidence_chain_certification.json"
    )
    return json.loads(certification_path.read_text(encoding="utf-8"))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--config-path", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--timerange", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = certify(
        repo_root=args.repo_root,
        config_path=args.config_path,
        data_root=args.data_root,
        timerange=args.timerange,
        output_root=args.output_root,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "formalEvidenceChainCertificationHash": result[
                    "formalEvidenceChainCertificationHash"
                ],
                "formalResultCount": result["formalResultCount"],
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
