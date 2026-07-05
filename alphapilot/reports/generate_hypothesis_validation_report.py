"""Generate the V13.4.26 hypothesis validation report.

This is a thin wrapper around ``alphapilot.research_factory.validate_hypotheses``.
It creates research reports only and does not run a Freqtrade backtest.
"""

from __future__ import annotations

from alphapilot.research_factory.validate_hypotheses import build_parser, run_validation


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    report = run_validation(args)
    print(f"Hypothesis validation status: {report.get('status')}")
    print(f"Report: {args.output_report}")


if __name__ == "__main__":
    main()
