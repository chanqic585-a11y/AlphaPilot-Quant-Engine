from pathlib import Path

from alphapilot.storage_governance.reference_graph import build_reference_graph


def test_reference_graph_marks_formal_evidence_targets_immutable(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    referenced = data_root / "referenced.parquet"
    unreferenced = data_root / "unreferenced.parquet"
    referenced.write_bytes(b"referenced")
    unreferenced.write_bytes(b"unreferenced")
    evidence = tmp_path / "formal_pass_evidence.json"
    evidence.write_text(
        '{"path": "' + str(referenced).replace("\\", "\\\\") + '"}',
        encoding="utf-8",
    )

    graph = build_reference_graph(data_root, reference_documents=[evidence])
    rows = {Path(row["path"]).name: row for row in graph["files"]}

    assert rows["referenced.parquet"]["referenceCount"] == 1
    assert rows["referenced.parquet"]["immutableEvidence"] is True
    assert rows["referenced.parquet"]["safeToRemove"] is False
    assert rows["unreferenced.parquet"]["referenceCount"] == 0


def test_sidecar_references_its_adjacent_target(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    target = data_root / "asset.csv"
    target.write_text("a,b\n1,2\n", encoding="utf-8")
    (data_root / "asset.csv.sha256").write_text("unused  asset.csv\n", encoding="ascii")

    graph = build_reference_graph(data_root)
    row = next(item for item in graph["files"] if item["path"] == str(target.resolve()))

    assert row["referenceCount"] == 1
    assert row["safeToRemove"] is False
