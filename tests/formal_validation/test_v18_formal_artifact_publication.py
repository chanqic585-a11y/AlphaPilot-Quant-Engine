from __future__ import annotations

from pathlib import Path

from alphapilot.formal_validation import v18_formal_reporting as reporting
from alphapilot.formal_validation.candidate_adapters import get_candidate_adapter


def test_formal_artifact_staging_avoids_long_campaign_and_candidate_segments(
    tmp_path: Path, monkeypatch
) -> None:
    destination = (
        tmp_path
        / ("campaign-" + "c" * 80)
        / ("candidate-" + "d" * 48)
    )
    observed_paths: list[Path] = []
    original_writer = reporting.write_json_atomic

    def recording_writer(path: Path, value: object, **kwargs: object) -> None:
        observed_paths.append(Path(path))
        original_writer(path, value, **kwargs)

    monkeypatch.setattr(reporting, "write_json_atomic", recording_writer)

    reporting._publish_artifacts(
        destination,
        json_payloads={"fold_results.json": []},
        markdown_payloads={},
        parquet_payloads={},
        csv_payloads={},
        campaign_id="v36-long-path-contract",
        candidate_id="v35_tsmom_crypto_adaptation",
        candidate_adapter=get_candidate_adapter("v35_tsmom_crypto_adaptation"),
        route="formal_walk_forward_completed",
    )

    assert observed_paths
    staging = observed_paths[0].parent
    assert staging.parent == destination.parents[1]
    assert len(str(staging)) < len(str(destination.parent))
    assert (destination / "artifact_manifest.json").is_file()
