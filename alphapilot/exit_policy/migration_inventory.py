"""Compatibility entry point for the Advisory-R migration inventory."""

from alphapilot.reports.generate_exit_policy_migration_inventory import (
    main,
    scan_exit_policy_references,
    summarize_inventory,
    write_inventory,
)

__all__ = [
    "main",
    "scan_exit_policy_references",
    "summarize_inventory",
    "write_inventory",
]


if __name__ == "__main__":
    raise SystemExit(main())
