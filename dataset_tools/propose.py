"""Computes a proposal with the latest trained model for every image still to be marked."""
import sys
from dataclasses import dataclass
from pathlib import Path

from ultralytics import YOLO

from dataset_tools import annotations, manifest, paths, proposals, trial
from dataset_tools import instrument as instrument_module

COVERED_STATUSES = {annotations.PENDING, annotations.SKIPPED}


class ProposalError(Exception):
    pass


@dataclass
class Report:
    with_proposal: int = 0
    without_proposal: int = 0
    unreadable: int = 0

    def lines(self):
        return [
            f"Images with a proposal: {self.with_proposal}",
            f"Images without a proposal: {self.without_proposal}",
            f"Images that could not be read: {self.unreadable}",
        ]


def points_of(result, instrument):
    """Coordinates can fall just outside the image, where an annotation would be refused."""
    best = int(result.boxes.conf.argmax())
    return [
        {"name": name, "x": min(max(x, 0.0), 1.0), "y": min(max(y, 0.0), 1.0), "visible": True}
        for name, (x, y) in zip(instrument.point_names, result.keypoints.xyn[best].tolist())
    ]


def _predict(model, record, images_dir, device):
    """Returns the prediction, or None if the image cannot be read."""
    # The manifest is versioned and can come from a contributor, so its names are not trusted as paths.
    if Path(record["image_id"]).name != record["image_id"] or Path(record["file"]).name != record["file"]:
        return None
    try:
        results = model.predict(str(images_dir / record["file"]), device=device, verbose=False)
    except FileNotFoundError:
        return None
    return results[0] if results else None


def load_model(instrument, model_path, model_factory):
    if not model_path.exists():
        raise ProposalError("No trained model found. Run: .venv/bin/python -m dataset_tools.train")
    model = model_factory(str(model_path))
    if model.model.kpt_shape[0] != len(instrument.point_names):
        raise ProposalError(
            f"The model has {model.model.kpt_shape[0]} points and the instrument {len(instrument.point_names)}. "
            "Train again with: .venv/bin/python -m dataset_tools.train"
        )
    return model


def run(
    instrument,
    manifest_path=paths.MANIFEST,
    annotations_dir=paths.ANNOTATIONS,
    images_dir=paths.IMAGES,
    proposals_dir=paths.PROPOSALS,
    model_path=paths.LATEST_MODEL,
    model_factory=YOLO,
    device=None,
):
    model = load_model(instrument, model_path, model_factory)
    device = device or trial.default_device()
    report = Report()
    for record in manifest.load(manifest_path, repair=False):
        image_id = record["image_id"]
        status = annotations.status_of(annotations.load(image_id, annotations_dir), instrument)
        if status not in COVERED_STATUSES:
            continue
        result = _predict(model, record, images_dir, device)
        if result is None:
            report.unreadable += 1
        elif trial.has_detection(result):
            proposals.save(image_id, points_of(result, instrument), proposals_dir)
            report.with_proposal += 1
        else:
            proposals.remove(image_id, proposals_dir)
            report.without_proposal += 1
    return report


def main():
    try:
        report = run(instrument_module.load())
    except (ProposalError, instrument_module.InvalidInstrument, manifest.CorruptManifest, RuntimeError, OSError) as error:
        print(f"Proposals stopped: {error}")
        return 1
    except KeyboardInterrupt:
        print("Proposals stopped. Those already computed stay usable: run the command again to complete the rest.")
        return 1
    print("\n".join(report.lines()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
