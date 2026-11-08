"""Builds the YOLO keypoint dataset from finished annotations."""
import hashlib
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

from dataset_tools import annotations, frames, manifest, paths
from dataset_tools import instrument as instrument_module

VALIDATION_PERCENT = 20
BOX_PADDING = 0.10
MIN_BOX_SIDE = 0.05
TARGET_IMAGES = 300
TARGET_USER_FRAMES = 50
VISIBLE = 2


class ExportError(Exception):
    pass


@dataclass
class Report:
    train: int = 0
    validation: int = 0
    user_frames: int = 0
    missing_files: list = field(default_factory=list)
    outdated: list = field(default_factory=list)

    def lines(self):
        total = self.train + self.validation
        lines = [
            f"Annotated images: {total} of {TARGET_IMAGES} ({self.train} training, {self.validation} validation)",
            f"Frames from your videos: {self.user_frames} of {TARGET_USER_FRAMES}",
        ]
        if total < TARGET_IMAGES:
            lines.append(f"WARNING: {TARGET_IMAGES - total} more annotated images are needed.")
        if self.user_frames < TARGET_USER_FRAMES:
            lines.append(f"WARNING: {TARGET_USER_FRAMES - self.user_frames} more annotated frames from your videos are needed.")
        lines.extend(f"Left out, image file is missing: {image_id}" for image_id in self.missing_files)
        lines.extend(f"Left out, points no longer match the instrument definition: {image_id}" for image_id in self.outdated)
        return lines


def object_box(visible_points):
    """Returns the normalized (center x, center y, width, height) around the points."""
    center_x, width = _axis_box([x for x, _ in visible_points])
    center_y, height = _axis_box([y for _, y in visible_points])
    return center_x, center_y, width, height


def _axis_box(values):
    low, high = min(values), max(values)
    size = max((high - low) * (1 + 2 * BOX_PADDING), MIN_BOX_SIDE)
    center = (low + high) / 2
    if center - size / 2 < 0:
        center = size / 2
    if center + size / 2 > 1:
        center = 1 - size / 2
    start = max(center - size / 2, 0)
    end = min(center + size / 2, 1)
    return (start + end) / 2, end - start


def label_line(annotation):
    points = annotation["points"]
    box = object_box([(point["x"], point["y"]) for point in points if point["visible"]])
    values = [0, *box]
    for point in points:
        values.extend([point["x"], point["y"], VISIBLE] if point["visible"] else [0, 0, 0])
    return " ".join(f"{value:.6f}" if isinstance(value, float) else str(value) for value in values)


def _split_of(record):
    """Stable, and shared by all frames of a video so near-identical images never span both splits."""
    group = record.get("video_id") or record["image_id"]
    bucket = int(hashlib.sha256(group.encode("utf-8")).hexdigest(), 16) % 100
    return "val" if bucket < VALIDATION_PERCENT else "train"


def _flip_indexes(instrument):
    names = list(instrument.point_names)
    indexes = list(range(len(names)))
    for first, second in instrument.mirror_pairs:
        a, b = names.index(first), names.index(second)
        indexes[a], indexes[b] = b, a
    return indexes


def _data_yaml(instrument, export_dir):
    names = ", ".join(instrument.point_names)
    return (
        f'path: "{export_dir}"\n'
        "train: images/train\n"
        "val: images/val\n"
        f"kpt_shape: [{len(instrument.point_names)}, 3]\n"
        f"flip_idx: {_flip_indexes(instrument)}\n"
        "names:\n"
        f"  0: {instrument.class_name}\n"
        "kpt_names:\n"
        f"  0: [{names}]\n"
    )


def _select(instrument, manifest_path, annotations_dir, images_dir, report):
    examples = []
    for record in manifest.load(manifest_path, repair=False):
        annotation = annotations.load(record["image_id"], annotations_dir)
        if annotation is None or annotation.get("status") != annotations.ANNOTATED:
            continue
        if annotations.status_of(annotation, instrument) != annotations.ANNOTATED:
            report.outdated.append(record["image_id"])
        elif Path(record["file"]).name != record["file"] or not (images_dir / record["file"]).exists():
            report.missing_files.append(record["image_id"])
        else:
            split = _split_of(record)
            examples.append((record, annotation, split))
            if split == "train":
                report.train += 1
            else:
                report.validation += 1
            if record.get("license") == frames.USER_OWNED:
                report.user_frames += 1
    return examples


def _stopped(reason, report):
    return ExportError("\n".join([reason, *report.lines()]))


def export(instrument, manifest_path=paths.MANIFEST, annotations_dir=paths.ANNOTATIONS, images_dir=paths.IMAGES, export_dir=paths.EXPORT):
    report = Report()
    examples = _select(instrument, manifest_path, annotations_dir, images_dir, report)
    if not examples:
        raise _stopped("No annotated images to export.", report)
    splits = {split for _, _, split in examples}
    if splits != {"train", "val"}:
        raise _stopped(f"Only the {splits.pop()} split has images. Annotate more images, ideally from more videos.", report)

    if export_dir.exists():
        shutil.rmtree(export_dir)
    for split in ("train", "val"):
        (export_dir / "images" / split).mkdir(parents=True)
        (export_dir / "labels" / split).mkdir(parents=True)
    for record, annotation, split in examples:
        source = images_dir / record["file"]
        shutil.copyfile(source, export_dir / "images" / split / record["file"])
        (export_dir / "labels" / split / f"{source.stem}.txt").write_text(label_line(annotation) + "\n", encoding="utf-8")
    (export_dir / "data.yaml").write_text(_data_yaml(instrument, export_dir), encoding="utf-8")
    return report


def main():
    try:
        report = export(instrument_module.load())
    except (ExportError, instrument_module.InvalidInstrument) as error:
        print(f"Export stopped: {error}")
        return 1
    print("\n".join(report.lines()))
    print(f"Dataset written to {paths.EXPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
