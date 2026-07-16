from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from alphapilot.minimal_research_campaign.campaign_runner import (
    calculate_development_end,
    verify_implementation_freeze,
)


def test_development_boundary_uses_only_frozen_first_55_percent() -> None:
    observed = calculate_development_end(
        "2020-01-01T00:00:00+00:00",
        "2030-01-01T00:00:00+00:00",
        fraction=0.55,
    )
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    end = datetime(2030, 1, 1, tzinfo=timezone.utc)
    expected = start + (end - start) * 0.55

    assert observed == expected
    assert observed < end


def test_implementation_freeze_rejects_changed_source(tmp_path: Path) -> None:
    source = tmp_path / "runner.py"
    source.write_text("frozen", encoding="utf-8")
    preregistration = {
        "implementationSourceHashes": {"runner.py": "wrong-hash"}
    }

    with pytest.raises(RuntimeError, match="changed after preregistration"):
        verify_implementation_freeze(
            preregistration,
            source_root=tmp_path,
        )
