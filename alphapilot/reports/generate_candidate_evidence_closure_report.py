"""Generate preregistered candidate evidence-closure research artifacts."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.validation.preregistration import (
    build_preregistration,
    verify_preregistration,
)
from alphapilot.validation.registry_loader import load_candidate_preregistration_records

from .candidate_evidence_closure_schema import PREREGISTRATION_OUTPUTS


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_head(root: Path) -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def environment_fingerprint(root: Path, source_root: Path) -> dict[str, Any]:
    packages: dict[str, str | None] = {}
    for name in ("numpy", "pandas", "pyarrow", "scipy"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    registry = source_root / "data" / "evolution_registry.sqlite"
    attribution = source_root / "reports" / "full_archived_strategy_failure_attribution.json"
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "executable": str(Path(sys.executable).resolve()),
        "packages": packages,
        "gitHead": _git_head(root),
        "sourceGitHead": _git_head(source_root),
        "registrySha256": _sha256_file(registry) if registry.is_file() else None,
        "failureAttributionSha256": (
            _sha256_file(attribution) if attribution.is_file() else None
        ),
    }


def _markdown(preregistration: dict[str, Any], deduplication: dict[str, Any]) -> str:
    lines = [
        "# 候选证据闭环锁定验证预注册",
        "",
        f"- 预注册哈希：`{preregistration['preRegistrationHash']}`",
        f"- 候选版本：{deduplication['candidate_version_count']}",
        f"- 去重后家族：{deduplication['canonical_representative_count']}",
        "- 主验收风险模型：模型一（单笔账户风险 0.25%）",
        "- 模型二、模型三：仅敏感性观察，不能挽救主模型失败",
        "- 研究边界：不恢复归档版本，不授予执行资格，不创建订单",
        "",
        "## 候选队列",
        "",
    ]
    for candidate in preregistration["candidates"]:
        lines.append(
            f"- {candidate['tier']}：{candidate['displayLabelZh']} "
            f"(`{candidate['strategyVersionId']}`)"
        )
    lines.extend(
        [
            "",
            "## 锁定规则",
            "",
            "- 信号定义、方向、周期、阈值、成本模型、风险模型和门槛在查看结果前冻结。",
            "- 1D 需要至少 365 天且有效交易数不少于 50；30–49 笔仅探索。",
            "- 缺少无污染锁定样本或 point-in-time 宇宙证据时只能诊断，不能通过。",
            "- Bootstrap 和 Monte Carlo 正式运行均为 5,000 次，使用登记种子。",
            "- NoTrade 与简单方向基线只用于比较，不能授予通过。",
            "",
        ]
    )
    return "\n".join(lines)


def generate_preregistration(root: Path, source_root: Path) -> dict[str, Any]:
    locked_path = root / PREREGISTRATION_OUTPUTS["preregistrationJson"]
    if locked_path.is_file():
        locked = json.loads(locked_path.read_text(encoding="utf-8"))
        if not isinstance(locked, dict):
            raise ValueError("locked preregistration must be a JSON object")
        return verify_preregistration(locked)

    attribution_path = (
        source_root / "reports" / "full_archived_strategy_failure_attribution.json"
    )
    registry_path = source_root / "data" / "evolution_registry.sqlite"
    attributions = json.loads(attribution_path.read_text(encoding="utf-8"))
    if not isinstance(attributions, list):
        raise ValueError("failure attribution report must be a JSON array")
    candidates, deduplication, diagnostics = load_candidate_preregistration_records(
        failure_attributions=attributions,
        registry_path=registry_path,
    )
    preregistration = build_preregistration(
        candidates=candidates,
        environment_fingerprint=environment_fingerprint(root, source_root),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    queue = {
        "schemaVersion": "candidate_validation_queue_v1",
        "candidateVersionCount": deduplication.candidate_version_count,
        "candidateFamilyCount": deduplication.candidate_family_count,
        "canonicalRepresentativeCount": deduplication.canonical_representative_count,
        "candidates": candidates,
        "diagnostics": diagnostics,
    }
    deduplication_payload = asdict(deduplication)
    for key, relative in PREREGISTRATION_OUTPUTS.items():
        path = root / relative
        if key == "queue":
            write_json_atomic(path, queue)
        elif key == "deduplication":
            write_json_atomic(path, deduplication_payload)
        elif key == "preregistrationJson":
            write_json_atomic(path, preregistration)
        elif key == "preregistrationMarkdown":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                _markdown(preregistration, deduplication_payload), encoding="utf-8"
            )
    return preregistration


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("preregister",), default="preregister")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--source-root", type=Path, default=None)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = args.root.resolve()
    source_root = (args.source_root or root).resolve()
    preregistration = generate_preregistration(root, source_root)
    print(
        json.dumps(
            {
                "status": "preregistered",
                "candidateCount": len(preregistration["candidates"]),
                "preRegistrationHash": preregistration["preRegistrationHash"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
