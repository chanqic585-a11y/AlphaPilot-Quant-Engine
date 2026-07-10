"""Generate the V13.16 data-foundation catalog and smoke snapshot report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from alphapilot.data_foundation.pipeline import run_data_foundation


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _summary(report: dict[str, object]) -> str:
    catalog = report.get("catalogSummary") if isinstance(report.get("catalogSummary"), dict) else {}
    snapshot = report.get("dataSnapshot") if isinstance(report.get("dataSnapshot"), dict) else {}
    lines = [
        "# AlphaPilot V13.16 Data Foundation",
        "",
        f"- Status: `{report.get('status')}`",
        f"- Raw files cataloged: `{catalog.get('totalFileCount', 0)}`",
        f"- Selected source files: `{catalog.get('selectedFileCount', 0)}`",
        f"- Canonical smoke assets: `{report.get('canonicalCreatedOrExistingCount', 0)}`",
        f"- Canonical failures: `{report.get('canonicalFailedCount', 0)}`",
        f"- DataSnapshot: `{snapshot.get('dataSnapshotId') or 'not_created'}`",
        f"- Snapshot registered: `{str(bool(report.get('dataSnapshotRegistered'))).lower()}`",
        f"- Formal promotion eligible: `{str(bool(report.get('formalPromotionEligible'))).lower()}`",
        "",
        "Unknown source provenance remains a hard promotion blocker. This report does not create a strategy, Demo release, Live candidate, or order.",
    ]
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build AlphaPilot V13.16 market-data foundation evidence.")
    parser.add_argument("--raw-root", default=r"D:\Codex-Workspace\回测数据")
    parser.add_argument("--market-root", default="data/market")
    parser.add_argument("--registry-path", default="data/evolution_registry.sqlite")
    parser.add_argument("--symbols", default="BTC,ETH,SOL")
    parser.add_argument("--timeframes", default="15m,1h,4h,1d")
    parser.add_argument("--market-type", default="swap", choices=("swap", "spot"))
    parser.add_argument("--exchange", default="unknown")
    parser.add_argument("--hash-mode", default="none", choices=("none", "selected", "all"))
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--no-register", action="store_true")
    parser.add_argument("--output-json", default="reports/v13_16_data_foundation_report.json")
    parser.add_argument("--output-markdown", default="reports/v13_16_data_foundation_summary.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = run_data_foundation(
        raw_root=args.raw_root,
        market_root=args.market_root,
        registry_path=args.registry_path,
        symbols=_csv(args.symbols),
        timeframes=_csv(args.timeframes),
        market_type=args.market_type,
        exchange=args.exchange,
        hash_mode=args.hash_mode,
        overwrite=args.overwrite,
        register_snapshot=not args.no_register,
    )
    output_json = Path(args.output_json)
    output_markdown = Path(args.output_markdown)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_markdown.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    output_markdown.write_text(_summary(report), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("reportId", "version", "status", "smokeAssetCount", "canonicalCreatedOrExistingCount", "canonicalFailedCount", "dataSnapshotRegistered", "formalPromotionEligible")}, ensure_ascii=False, indent=2))
    print(f"Wrote {output_json}")
    print(f"Wrote {output_markdown}")


if __name__ == "__main__":
    main()
