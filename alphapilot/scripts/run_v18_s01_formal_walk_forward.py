"""Compatibility entry point for the generic V18 formal runner."""

from __future__ import annotations

from .run_formal_walk_forward import (
    _blocked_route,
    _default_executor,
    formal_artifact_root,
    main,
    run,
)

__all__ = [
    "_blocked_route",
    "_default_executor",
    "formal_artifact_root",
    "main",
    "run",
]


if __name__ == "__main__":
    raise SystemExit(main())
