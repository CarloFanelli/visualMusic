import json

import pytest

from dataset_tools import annotations
from dataset_tools import instrument as instrument_module
from dataset_tools.instrument import Instrument, InvalidInstrument

SAX = instrument_module.load()


def complete_annotation(instrument=SAX):
    return {
        "status": annotations.ANNOTATED,
        "points": [{"name": name, "x": 0.5, "y": 0.5, "visible": True} for name in instrument.point_names],
    }


def test_project_definition_lists_the_four_points_in_click_order():
    assert SAX.point_names == ("bell_centre", "bell_edge_left", "bell_edge_right", "mouthpiece")


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        '{"class_name": "sax"}',
        '{"class_name": "sax", "points": []}',
        '{"class_name": "sax", "points": [{"name": "a"}]}',
        '{"class_name": "sax", "points": [{"name": "a", "label": "A"}, {"name": "a", "label": "B"}]}',
        '{"class_name": "sax", "points": [{"name": "a", "label": "A"}], "mirror_pairs": [["a", "b"]]}',
    ],
)
def test_invalid_definition_is_refused(tmp_path, content):
    path = tmp_path / "instrument.json"
    path.write_text(content)
    with pytest.raises(InvalidInstrument):
        instrument_module.load(path)


def test_missing_definition_is_refused_and_named(tmp_path):
    path = tmp_path / "missing.json"
    with pytest.raises(InvalidInstrument, match="missing.json"):
        instrument_module.load(path)


def test_saved_annotation_is_loaded_back(tmp_path):
    annotations.save("a", complete_annotation(), tmp_path)
    assert annotations.load("a", tmp_path) == complete_annotation()


def test_failed_write_leaves_the_previous_annotation_intact(tmp_path, monkeypatch):
    annotations.save("a", complete_annotation(), tmp_path)
    before = (tmp_path / "a.json").read_bytes()

    def fail(*args):
        raise OSError("disk full")

    monkeypatch.setattr(annotations.os, "replace", fail)
    with pytest.raises(OSError):
        annotations.save("a", {"status": "other"}, tmp_path)

    assert (tmp_path / "a.json").read_bytes() == before
    assert [path.name for path in tmp_path.iterdir()] == ["a.json"]


@pytest.mark.parametrize("field, value", [("x", 1.2), ("x", -0.1), ("y", "0.5"), ("y", None), ("x", True), ("visible", "yes")])
def test_points_outside_the_image_are_refused(field, value):
    annotation = complete_annotation()
    annotation["points"][0][field] = value
    with pytest.raises(annotations.InvalidAnnotation):
        annotations.validate(annotation, SAX)


def test_points_on_the_image_border_are_accepted():
    annotation = complete_annotation()
    annotation["points"][0].update(x=0, y=1)
    annotations.validate(annotation, SAX)


def test_annotation_with_missing_or_reordered_points_is_refused():
    short = complete_annotation()
    short["points"].pop()
    swapped = complete_annotation()
    swapped["points"].reverse()
    for annotation in (short, swapped):
        with pytest.raises(annotations.InvalidAnnotation):
            annotations.validate(annotation, SAX)


def test_status_is_pending_without_annotation_or_after_definition_change_but_file_is_kept(tmp_path):
    annotations.save("a", complete_annotation(), tmp_path)
    changed = Instrument("saxophone", SAX.point_names + ("new_point",), SAX.point_labels + ("nuovo",), ())

    assert annotations.status_of(None, SAX) == annotations.PENDING
    assert annotations.status_of(annotations.load("a", tmp_path), SAX) == annotations.ANNOTATED
    assert annotations.status_of(annotations.load("a", tmp_path), changed) == annotations.PENDING
    assert json.loads((tmp_path / "a.json").read_text()) == complete_annotation()


def test_damaged_annotation_file_counts_as_missing(tmp_path):
    (tmp_path / "a.json").write_text("{broken")
    assert annotations.load("a", tmp_path) is None


def hidden_point(name):
    return {"name": name, "visible": False}


def test_a_hidden_point_is_stored_without_a_position():
    annotation = complete_annotation()
    annotation["points"][0] = hidden_point("bell_centre")
    annotations.validate(annotation, SAX)
    assert annotations.status_of(annotation, SAX) == annotations.ANNOTATED


def test_a_hidden_point_with_a_position_is_refused():
    annotation = complete_annotation()
    annotation["points"][0] = {**hidden_point("bell_centre"), "x": 0.5, "y": 0.5}
    with pytest.raises(annotations.InvalidAnnotation):
        annotations.validate(annotation, SAX)


def test_an_annotation_with_every_point_hidden_is_refused():
    annotation = {"status": annotations.ANNOTATED, "points": [hidden_point(name) for name in SAX.point_names]}
    with pytest.raises(annotations.InvalidAnnotation):
        annotations.validate(annotation, SAX)


@pytest.mark.parametrize("status", [annotations.SKIPPED, annotations.REJECTED, annotations.PENDING])
def test_statuses_without_points_are_valid_and_reported(status):
    annotation = {"status": status}
    annotations.validate(annotation, SAX)
    assert annotations.status_of(annotation, SAX) == status


def test_a_status_without_points_cannot_carry_points():
    with pytest.raises(annotations.InvalidAnnotation):
        annotations.validate({"status": annotations.REJECTED, "points": complete_annotation()["points"]}, SAX)


def test_rejected_status_stays_valid_after_a_definition_change():
    changed = Instrument("saxophone", SAX.point_names + ("new_point",), SAX.point_labels + ("nuovo",), ())
    assert annotations.status_of({"status": annotations.REJECTED}, changed) == annotations.REJECTED


@pytest.mark.parametrize(
    "stored",
    [
        {"status": []},
        {"status": {}},
        {"status": "annotated", "points": complete_annotation()["points"] + [5]},
        {"status": "annotated", "points": [5] + complete_annotation()["points"]},
    ],
)
def test_malformed_annotation_is_invalid_and_counts_as_pending(stored):
    with pytest.raises(annotations.InvalidAnnotation):
        annotations.validate(stored, SAX)
    assert annotations.status_of(stored, SAX) == annotations.PENDING


@pytest.mark.parametrize(
    "pairs",
    ['[["a", "a"]]', '[["a", "b"], ["b", "c"]]'],
)
def test_mirror_pairs_must_be_two_points_used_once(tmp_path, pairs):
    path = tmp_path / "instrument.json"
    points = ", ".join(f'{{"name": "{name}", "label": "{name}"}}' for name in "abc")
    path.write_text(f'{{"class_name": "sax", "points": [{points}], "mirror_pairs": {pairs}}}')
    with pytest.raises(InvalidInstrument, match="mirror pair"):
        instrument_module.load(path)
