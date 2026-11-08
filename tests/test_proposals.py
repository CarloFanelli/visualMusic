import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
from PIL import Image

from dataset_tools import annotations, export, instrument, manifest, paths, propose, proposals

SAX = instrument.load()
NAMES = SAX.point_names


def prediction(positions=None, confidences=(0.9,)):
    """positions holds one list of four (x, y) per detection; None means no detection."""
    if positions is None:
        return SimpleNamespace(boxes=SimpleNamespace(conf=torch.tensor([])), keypoints=None)
    return SimpleNamespace(boxes=SimpleNamespace(conf=torch.tensor(list(confidences))), keypoints=SimpleNamespace(xyn=torch.tensor(positions)))


FOUND = [[(0.1, 0.2), (0.3, 0.4), (0.5, 0.6), (0.7, 0.8)]]


class FakeModel:
    points = len(NAMES)
    results = {}

    def __init__(self, source):
        self.source = source
        self.model = SimpleNamespace(kpt_shape=[FakeModel.points, 3])

    def predict(self, source, **arguments):
        if not Path(source).exists():
            raise FileNotFoundError(source)
        outcome = FakeModel.results.get(Path(source).name, FOUND)
        if outcome == "unreadable":
            return []
        return [outcome if isinstance(outcome, SimpleNamespace) else prediction(outcome)]


@pytest.fixture(autouse=True)
def reset_fake():
    FakeModel.points = len(NAMES)
    FakeModel.results = {}


@pytest.fixture
def layout(tmp_path):
    details = SimpleNamespace(
        manifest=tmp_path / "manifest.jsonl",
        annotations=tmp_path / "annotations",
        images=tmp_path / "images",
        proposals=tmp_path / "proposals",
        model=tmp_path / "latest.pt",
    )
    details.images.mkdir()
    details.model.write_bytes(b"model")
    return details


def add_image(layout, image_id, annotation=None):
    file = f"{image_id}.jpg"
    manifest.append({"image_id": image_id, "file": file}, layout.manifest)
    Image.new("RGB", (40, 30), "white").save(layout.images / file)
    if annotation:
        annotations.save(image_id, annotation, layout.annotations)


def run(layout, model_factory=FakeModel):
    return propose.run(SAX, layout.manifest, layout.annotations, layout.images, layout.proposals, layout.model, model_factory, "cpu")


def stored(layout, image_id):
    return proposals.load(image_id, SAX, layout.proposals)


def annotated_body():
    return {"status": "annotated", "points": [{"name": name, "x": 0.5, "y": 0.5, "visible": True} for name in NAMES]}


def test_image_with_a_saxophone_gets_all_its_points_as_visible(layout):
    add_image(layout, "a")
    report = run(layout)
    assert report.with_proposal == 1
    points = stored(layout, "a")
    assert [point["name"] for point in points] == list(NAMES)
    assert all(point["visible"] for point in points)
    assert points[3]["x"] == pytest.approx(0.7)
    assert points[3]["y"] == pytest.approx(0.8)


def test_several_detections_propose_the_most_confident(layout):
    other = [(0.9, 0.9)] * 4
    add_image(layout, "a")
    FakeModel.results["a.jpg"] = prediction([other, FOUND[0]], (0.3, 0.8))
    run(layout)
    assert stored(layout, "a")[0]["x"] == pytest.approx(0.1)


def test_no_detection_stores_nothing_and_is_counted(layout):
    add_image(layout, "a")
    FakeModel.results["a.jpg"] = None
    report = run(layout)
    assert report.without_proposal == 1
    assert stored(layout, "a") is None


def test_annotated_and_rejected_images_get_nothing_and_stay_unchanged(layout):
    add_image(layout, "done", annotated_body())
    add_image(layout, "bad", {"status": "rejected"})
    before = (layout.annotations / "done.json").read_text()
    report = run(layout)
    assert report.with_proposal == 0
    assert not layout.proposals.exists()
    assert (layout.annotations / "done.json").read_text() == before
    assert annotations.load("bad", layout.annotations) == {"status": "rejected"}


def test_skipped_images_get_a_proposal(layout):
    add_image(layout, "later", {"status": "skipped"})
    assert run(layout).with_proposal == 1
    assert stored(layout, "later") is not None


def test_counts_cover_all_the_outcomes(layout):
    add_image(layout, "yes")
    add_image(layout, "no")
    add_image(layout, "corrupt")
    add_image(layout, "gone")
    (layout.images / "gone.jpg").unlink()
    FakeModel.results.update({"no.jpg": None, "corrupt.jpg": "unreadable"})
    report = run(layout)
    assert (report.with_proposal, report.without_proposal, report.unreadable) == (1, 1, 2)
    assert "Images that could not be read: 2" in report.lines()


def test_points_outside_the_image_move_to_the_nearest_edge(layout):
    add_image(layout, "a")
    FakeModel.results["a.jpg"] = [[(-0.02, 1.02), (0.3, 0.4), (1.5, -1.0), (0.7, 0.8)]]
    run(layout)
    points = stored(layout, "a")
    assert (points[0]["x"], points[0]["y"]) == (0.0, 1.0)
    assert (points[2]["x"], points[2]["y"]) == (1.0, 0.0)


def test_running_again_replaces_the_proposal_and_removes_an_unsupported_one(layout):
    add_image(layout, "a")
    add_image(layout, "b")
    run(layout)
    FakeModel.results = {"a.jpg": [[(0.2, 0.2)] * 4], "b.jpg": None}
    run(layout)
    assert stored(layout, "a")[0]["x"] == pytest.approx(0.2)
    assert stored(layout, "b") is None


def test_interruption_keeps_the_proposals_already_computed(layout):
    add_image(layout, "a")
    add_image(layout, "b")

    class InterruptedModel(FakeModel):
        def predict(self, source, **arguments):
            if source.endswith("b.jpg"):
                raise KeyboardInterrupt
            return super().predict(source, **arguments)

    with pytest.raises(KeyboardInterrupt):
        run(layout, InterruptedModel)
    assert stored(layout, "a") is not None


def test_missing_model_stops_and_names_the_training_command(layout):
    layout.model.unlink()
    with pytest.raises(propose.ProposalError, match="dataset_tools.train"):
        run(layout)


def test_model_with_other_points_stops_and_leaves_proposals_untouched(layout):
    add_image(layout, "a")
    run(layout)
    before = (layout.proposals / "a.json").read_text()
    FakeModel.points = len(NAMES) + 1
    FakeModel.results["a.jpg"] = None
    with pytest.raises(propose.ProposalError, match="dataset_tools.train"):
        run(layout)
    assert (layout.proposals / "a.json").read_text() == before


@pytest.mark.parametrize("image_id, file", [("a", "../outside.jpg"), ("../outside", "a.jpg")])
def test_manifest_names_that_leave_their_folder_are_not_used(layout, image_id, file):
    manifest.append({"image_id": image_id, "file": file}, layout.manifest)
    Image.new("RGB", (40, 30), "white").save(layout.images.parent / "outside.jpg")
    Image.new("RGB", (40, 30), "white").save(layout.images / "a.jpg")
    assert run(layout).unreadable == 1
    assert not (layout.proposals.parent / "outside.json").exists()
    assert not layout.proposals.exists()


def test_torn_last_manifest_line_is_left_in_place(layout):
    add_image(layout, "a")
    with open(layout.manifest, "a", encoding="utf-8") as file:
        file.write('{"image_id": "being-written')
    content = layout.manifest.read_text()
    assert run(layout).with_proposal == 1
    assert layout.manifest.read_text() == content


def test_proposal_with_other_point_names_or_broken_content_is_unusable(tmp_path):
    (tmp_path / "other.json").write_text(json.dumps({"points": [{"name": "x", "x": 0.1, "y": 0.1, "visible": True}]}))
    (tmp_path / "broken.json").write_text("{")
    (tmp_path / "list.json").write_text("[]")
    for image_id in ("other", "broken", "list", "absent"):
        assert proposals.load(image_id, SAX, tmp_path) is None


def test_export_ignores_proposals_that_were_never_confirmed(layout, tmp_path):
    add_image(layout, "a")
    run(layout)
    with pytest.raises(export.ExportError):
        export.export(SAX, layout.manifest, layout.annotations, layout.images, tmp_path / "export")


def test_proposal_files_stay_out_of_git():
    assert subprocess.run(["git", "check-ignore", "-q", "data/proposals/photo.json"], cwd=paths.ROOT).returncode == 0


def test_model_image_reader_turns_a_rotated_photo_upright(tmp_path):
    """Points must fit the upright image the page shows."""
    patches = pytest.importorskip("ultralytics.utils.patches")
    photo = tmp_path / "rotated.jpg"
    exif = Image.Exif()
    exif[274] = 6
    Image.new("RGB", (200, 100), "red").save(photo, exif=exif)
    assert patches.imread(str(photo)).shape[:2] == (200, 100)


def test_command_stops_with_a_message(monkeypatch, capsys):
    def stop(_):
        raise propose.ProposalError("No trained model found")

    monkeypatch.setattr(propose, "run", stop)
    assert propose.main() == 1
    assert "No trained model found" in capsys.readouterr().out
