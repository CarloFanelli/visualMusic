import pytest

from dataset_tools import manifest


def test_appends_and_loads_records(tmp_path):
    path = tmp_path / "manifest.jsonl"
    manifest.append({"image_id": "a", "author": "Zoë"}, path)
    manifest.append({"image_id": "b"}, path)
    assert [record["image_id"] for record in manifest.load(path)] == ["a", "b"]
    assert manifest.load(path)[0]["author"] == "Zoë"


def test_missing_manifest_is_empty(tmp_path):
    assert manifest.load(tmp_path / "missing.jsonl") == []


def test_torn_last_line_is_repaired_and_earlier_bytes_stay_unchanged(tmp_path):
    path = tmp_path / "manifest.jsonl"
    manifest.append({"image_id": "a"}, path)
    intact = path.read_bytes()
    with open(path, "ab") as file:
        file.write(b'{"image_id": "b", "sou')

    assert [record["image_id"] for record in manifest.load(path)] == ["a"]
    assert path.read_bytes() == intact


def test_damage_before_the_last_line_is_reported(tmp_path):
    path = tmp_path / "manifest.jsonl"
    path.write_text('not json\n{"image_id": "b"}\n')
    with pytest.raises(manifest.CorruptManifest):
        manifest.load(path)
