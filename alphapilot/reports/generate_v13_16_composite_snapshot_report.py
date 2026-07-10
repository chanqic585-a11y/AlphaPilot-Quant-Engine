"""Generate the V13.16 canonical base plus public increment snapshot report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from alphapilot.data_foundation.composite_snapshot import build_composite_data_snapshot
from alphapilot.reports.generate_v13_16_public_increment_report import parse_timeframes


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _summary(report: dict[str, object]) -> str:
    snapshot = report.get("dataSnapshot") if isinstance(report.get("dataSnapshot"), dict) else {}
    verification = (
        report.get("dataSnapshotVerification")
        if isinstance(report.get("dataSnapshotVerification"), dict)
        else {}
    )
    lines = [
        "# AlphaPilot V13.16 Composite Data Snapshot",
        "",
        f"- Status: `{report.get('status')}`",
        f"- Valid groups: `{report.get('validGroupCount', 0)}/{report.get('requestedGroupCount', 0)}`",
        f"- Canonical files: `{report.get('canonicalFileCount', 0)}`",
        f"- DataSnapshot: `{snapshot.get('dataSnapshotId') or 'not_created'}`",
        f"- Point-in-time cutoff: `{snapshot.get('pointInTimeCutoff') or 'not_available'}`",
        f"- Snapshot verified: `{str(bool(verification.get('valid'))).lower()}`",
        f"- Snapshot registered: `{str(bool(report.get('dataSnapshotRegistered'))).lower()}`",
        f"- Formal promotion eligible: `{str(bool(report.get('formalPromotionEligible'))).lower()}`",
        "",
        "The immutable snapshot joins the read-only local base with verified public OKX increments. "
        "Unknown provenance on the local base remains a hard formal-promotion blocker.",
    ]
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build V13.16 composite canonical data evidence.")
    parser.add_argument("--market-root", default="data/market")
    parser.add_argument("--registry-path", default="data/evolution_registry.sqlite")
    parser.add_argument("--instruments", default="BTC-USDT-SWAP,ETH-USDT-SWAP,SOL-USDT-SWAP")
    parser.add_argument("--timeframes", type=parse_timeframes, default=parse_timeframes("15m,1h,4h,1d"))
    parser.add_argument("--market-type", default="swap", choices=("swap", "spot"))
    parser.add_argument("--no-register", action="store_true")
    parser.add_argument("--output-json", default="reports/v13_16_composite_data_snapshot_report.json")
    parser.add_argument("--output-markdown", default="reports/v13_16_composite_data_snapshot_summary.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_composite_data_snapshot(
        market_root=args.market_root,
        registry_path=args.registry_path,
        instruments=_csv(args.instruments),
        timeframes=args.timeframes,
        market_type=args.market_type,
        register_snapshot=not args.no_register,
    )
    output_json = Path(args.output_json)
    output_markdown = Path(args.output_markdown)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_markdown.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    output_markdown.write_text(_summary(report), encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "reportId",
        "version",
        "status",
        "requestedGroupCount",
        "validGroupCount",
        "canonicalFileCount",
        "dataSnapshotRegistered",
        "formalPromotionEligible",
    )}, ensure_ascii=False, indent=2))
    print(f"Wrote {output_json}")
    print(f"Wrote {output_markdown}")


if __name__ == "__main__":
    main()
