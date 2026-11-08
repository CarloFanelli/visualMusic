import pytest
from PIL import Image
from ultralytics.data.utils import check_det_dataset, verify_image_label

from dataset_tools import annotations, export, manifest
from dataset_tools import instrument as instrument_module

SAX = instrument_module.load()


def points(x=0.5, y=0.5):
    return [{"name": name, "x": x, "y": y, "visible": True} for name in SAX.point_names]


@pytest.fixture
def workspace(tmp_path):
    class Workspace:
        manifest_path = tmp_path / "manifest.jsonl"
        annotations_dir = tmp_path / "annotations"
        images_dir = tmp_path / "images"
        export_dir = tmp_path / "export"

        def add(self, image_id, annotation=None, video_id=None, make_file=True):
            record = {"image_id": image_id, "file": f"{image_id}.jpg", "license": "cc-by"}
            if video_id:
                record.update(video_id=video_id, license="user-owned")
            manifest.append(record, self.manifest_path)
            if make_file:
                self.images_dir.mkdir(exist_ok=True)
                Image.new("RGB", (40, 30), "red").save(self.images_dir / record["file"])
            if annotation is not None:
                annotations.save(image_id, annotation, self.annotations_dir)

        def run(self):
            return export.export(SAX, self.manifest_path, self.annotations_dir, self.images_dir, self.export_dir)

    return Workspace()


def add_both_splits(workspace, count=40):
    for number in range(count):
        workspace.add(f"image-{number}", {"status": "annotated", "points": points()})


def exported_names(workspace):
    return {path.stem for path in workspace.export_dir.glob("images/*/*")}


def test_only_annotated_images_are_exported_in_both_splits(workspace):
    add_both_splits(workspace)
    workspace.add("skipped", {"status": "skipped"})
    workspace.add("rejected", {"status": "rejected"})
    workspace.add("pending")

    report = workspace.run()

    names = exported_names(workspace)
    assert not names & {"skipped", "rejected", "pending"}
    assert len(names) == 40
    assert report.train > 0 and report.validation > 0
    assert report.train + report.validation == 40


def test_export_is_accepted_by_yolo_checks(workspace):
    add_both_splits(workspace)
    workspace.run()

    data = check_det_dataset(str(workspace.export_dir / "data.yaml"))
    assert data["kpt_shape"] == [4, 3]
    assert data["flip_idx"] == [0, 2, 1, 3]

    image = next(workspace.export_dir.glob("images/train/*"))
    label = workspace.export_dir / "labels" / "train" / f"{image.stem}.txt"
    result = verify_image_label((str(image), str(label), "", True, 1, 4, 3, False))
    assert result[-1] == ""
    assert result[0] == str(image)


def test_label_has_box_and_visible_points():
    annotation = {
        "status": "annotated",
        "points": [
            {"name": "bell_centre", "x": 0.4, "y": 0.5, "visible": True},
            {"name": "bell_edge_left", "x": 0.3, "y": 0.5, "visible": True},
            {"name": "bell_edge_right", "x": 0.5, "y": 0.5, "visible": True},
            {"name": "neck", "visible": False},
        ],
    }
    values = [float(value) for value in export.label_line(annotation).split()]
    assert values[0] == 0
    assert values[5:] == pytest.approx([0.4, 0.5, 2, 0.3, 0.5, 2, 0.5, 0.5, 2, 0, 0, 0])


def test_box_wraps_visible_points_with_padding():
    center_x, center_y, width, height = export.object_box([(0.2, 0.4), (0.6, 0.8)])
    assert (center_x, center_y) == pytest.approx((0.4, 0.6))
    assert (width, height) == pytest.approx((0.48, 0.48))


def test_single_visible_point_gets_a_minimum_box():
    _, _, width, height = export.object_box([(0.5, 0.5)])
    assert (width, height) == pytest.approx((0.05, 0.05))


def test_box_on_the_image_corner_stays_inside_the_image():
    center_x, center_y, width, height = export.object_box([(0.0, 0.0), (1.0, 1.0)])
    assert (center_x, center_y, width, height) == pytest.approx((0.5, 0.5, 1.0, 1.0))
    center_x, center_y, width, height = export.object_box([(1.0, 1.0)])
    assert center_x + width / 2 <= 1 and center_y + height / 2 <= 1
    assert center_x - width / 2 >= 0 and center_y - height / 2 >= 0


def test_frames_from_one_video_stay_in_the_same_split(workspace):
    add_both_splits(workspace)
    for number in range(10):
        workspace.add(f"video-a-{number}", {"status": "annotated", "points": points()}, video_id="a")
    workspace.run()
    splits = {path.parent.name for path in workspace.export_dir.glob("images/*/video-a-*")}
    assert len(splits) == 1


def test_split_does_not_change_between_exports(workspace):
    add_both_splits(workspace)
    workspace.run()
    first = {path.relative_to(workspace.export_dir) for path in workspace.export_dir.glob("images/*/*")}
    workspace.add("new", {"status": "annotated", "points": points()})
    workspace.run()
    second = {path.relative_to(workspace.export_dir) for path in workspace.export_dir.glob("images/*/*")}
    assert first <= second


def test_no_annotated_images_stops_with_an_error(workspace):
    workspace.add("pending")
    with pytest.raises(export.ExportError, match="annotated"):
        workspace.run()


def test_one_empty_split_stops_with_an_error_and_keeps_the_previous_export(workspace):
    add_both_splits(workspace)
    workspace.run()
    before = exported_names(workspace)

    for path in workspace.annotations_dir.iterdir():
        path.unlink()
    workspace.add("only", {"status": "annotated", "points": points()})
    with pytest.raises(export.ExportError, match="split"):
        workspace.run()
    assert exported_names(workspace) == before


def test_missing_image_file_is_excluded_and_reported(workspace):
    add_both_splits(workspace)
    workspace.add("gone", {"status": "annotated", "points": points()}, make_file=False)
    report = workspace.run()
    assert report.missing_files == ["gone"]
    assert "gone" not in exported_names(workspace)
    assert any("gone" in line for line in report.lines())


def test_annotation_that_no_longer_matches_the_definition_is_excluded_and_reported(workspace):
    add_both_splits(workspace)
    old = [{"name": "old_point", "x": 0.5, "y": 0.5, "visible": True}]
    workspace.add("outdated", {"status": "annotated", "points": old})
    report = workspace.run()
    assert report.outdated == ["outdated"]
    assert "outdated" not in exported_names(workspace)
    assert any("outdated" in line for line in report.lines())


def test_summary_warns_below_both_targets_with_counts(workspace):
    add_both_splits(workspace)
    for number in range(3):
        workspace.add(f"video-a-{number}", {"status": "annotated", "points": points()}, video_id="a")
    text = "\n".join(workspace.run().lines())
    assert "43 of 300" in text
    assert "3 of 50" in text
    assert "WARNING" in text


def test_enough_images_but_too_few_user_frames_warns_only_about_frames():
    report = export.Report(train=250, validation=50, user_frames=10)
    warnings = [line for line in report.lines() if line.startswith("WARNING")]
    assert len(warnings) == 1
    assert "video" in warnings[0]


def test_no_warning_when_targets_are_met():
    report = export.Report(train=280, validation=70, user_frames=50)
    assert not [line for line in report.lines() if line.startswith("WARNING")]


def test_error_with_no_usable_images_reports_the_missing_files(workspace):
    workspace.add("gone", {"status": "annotated", "points": points()}, make_file=False)
    with pytest.raises(export.ExportError, match="Left out, image file is missing: gone"):
        workspace.run()


def test_error_with_one_empty_split_reports_counts_and_missing_files(workspace):
    workspace.add("only", {"status": "annotated", "points": points()})
    workspace.add("gone", {"status": "annotated", "points": points()}, make_file=False)
    with pytest.raises(export.ExportError) as error:
        workspace.run()
    assert "Annotated images: 1 of 300" in str(error.value)
    assert "Left out, image file is missing: gone" in str(error.value)


def test_manifest_path_outside_the_images_folder_is_reported_and_never_written(workspace, tmp_path):
    add_both_splits(workspace)
    Image.new("RGB", (40, 30), "blue").save(tmp_path / "outside.jpg")
    manifest.append({"image_id": "bad", "file": "../outside.jpg", "license": "cc-by"}, workspace.manifest_path)
    annotations.save("bad", {"status": "annotated", "points": points()}, workspace.annotations_dir)
    report = workspace.run()
    assert report.missing_files == ["bad"]
    assert not (workspace.export_dir / "images" / "outside.jpg").exists()
