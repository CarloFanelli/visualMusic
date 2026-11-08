"""Runs a short training to prove the dataset and environment work end to end."""
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import torch
from ultralytics import YOLO

from dataset_tools import paths

WEIGHTS = "yolo26n-pose.pt"
EPOCHS = 10
IMAGE_SIZE = 640
RUN_NAME = "trial"
DRAWING_REFERENCE_SIDE = 640
POINT_COLOR = (48, 59, 255)
NO_DETECTION_COLOR = (0, 0, 200)


class TrialError(Exception):
    pass


@dataclass
class TrialResult:
    model_path: Path
    predictions_dir: Path
    device: str
    detected: int = 0
    no_detection: int = 0


def _train_once(data_yaml, runs_dir, model_factory, device):
    model = model_factory(WEIGHTS)
    model.train(data=str(data_yaml), epochs=EPOCHS, imgsz=IMAGE_SIZE, device=device, project=runs_dir, name=RUN_NAME, exist_ok=True)
    return Path(model.trainer.best)


def _train(data_yaml, runs_dir, model_factory, device):
    if device != "cpu":
        try:
            return _train_once(data_yaml, runs_dir, model_factory, device), device
        except (RuntimeError, NotImplementedError) as error:
            print(f"NOTICE: training stopped on the Apple GPU ({error}). Trying again on the CPU, which is slower.", flush=True)
    return _train_once(data_yaml, runs_dir, model_factory, "cpu"), "cpu"


def has_detection(result):
    return result.keypoints is not None and len(result.boxes.conf) > 0


def draw(result):
    """A training with few images may find nothing; that is a result to show, not an error."""
    image = result.orig_img.copy()
    # Sizes follow the photo, or marks would vanish when a large one is viewed at screen size.
    scale = max(max(image.shape[:2]) / DRAWING_REFERENCE_SIDE, 1)
    font_scale = 0.6 * scale
    thickness = round(2 * scale)
    if not has_detection(result):
        origin = (round(5 * scale), round(20 * scale))
        cv2.putText(image, "no detection", origin, cv2.FONT_HERSHEY_SIMPLEX, font_scale, NO_DETECTION_COLOR, thickness)
        return image
    best = int(result.boxes.conf.argmax())
    for number, (x, y) in enumerate(result.keypoints.xy[best].tolist(), start=1):
        center = (round(x), round(y))
        cv2.circle(image, center, round(6 * scale), POINT_COLOR, -1)
        label_origin = (center[0] + round(8 * scale), center[1] + round(5 * scale))
        cv2.putText(image, str(number), label_origin, cv2.FONT_HERSHEY_SIMPLEX, font_scale, POINT_COLOR, thickness)
    return image


def run(data_yaml=paths.EXPORT / "data.yaml", runs_dir=paths.RUNS, model_factory=YOLO, device=None):
    if not data_yaml.exists():
        raise TrialError("Exported dataset not found. Run: .venv/bin/python -m dataset_tools.export")
    device = device or ("mps" if torch.backends.mps.is_available() else "cpu")
    predictions_dir = runs_dir / RUN_NAME / "predictions"
    if predictions_dir.exists():
        shutil.rmtree(predictions_dir)
    model_path, used_device = _train(data_yaml, runs_dir, model_factory, device)

    predictions_dir.mkdir(parents=True)
    result = TrialResult(model_path, predictions_dir, used_device)
    model = model_factory(str(model_path))
    for image_path in sorted((data_yaml.parent / "images" / "val").iterdir()):
        prediction = model.predict(str(image_path), device=used_device, verbose=False)[0]
        if has_detection(prediction):
            result.detected += 1
        else:
            result.no_detection += 1
        cv2.imwrite(str(predictions_dir / image_path.name), draw(prediction))
    return result


def main():
    try:
        result = run()
    except (TrialError, RuntimeError) as error:
        print(f"Trial stopped: {error}")
        return 1
    print(f"Model saved to {result.model_path}")
    print(f"Validation images with predicted points: {result.predictions_dir}")
    print(f"Images with a detection: {result.detected}. Images with no detection: {result.no_detection}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
