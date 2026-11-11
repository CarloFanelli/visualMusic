"""Trains the model fully and publishes the result as the model used for proposals."""
import csv
import datetime
import hashlib
import json
import shutil
import subprocess
import sys

from ultralytics import YOLO

from dataset_tools import annotations, paths, trial

EPOCHS = 100
RUN_NAME = "full"
# The code that builds the dataset and trains: a change here changes the model.
TRAINING_CODE = ["dataset_tools", "instruments", "requirements.txt"]
POSE_MAP50 = "metrics/mAP50(P)"
POSE_MAP50_95 = "metrics/mAP50-95(P)"


def code_version():
    """Returns the current commit and whether the training code has uncommitted changes, or (None, None) outside git."""
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=paths.ROOT, capture_output=True, text=True, check=True).stdout.strip()
        status = subprocess.run(["git", "status", "--porcelain", "--", *TRAINING_CODE], cwd=paths.ROOT, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None, None
    return commit, bool(status.strip())


def best_metrics(results_csv):
    """The validation scores of the epoch with the best point accuracy, or None when training left no results."""
    if not results_csv.exists():
        return None
    with open(results_csv, encoding="utf-8") as file:
        rows = [{key.strip(): value for key, value in row.items()} for row in csv.DictReader(file)]
    rows = [row for row in rows if row.get(POSE_MAP50_95)]
    if not rows:
        return None
    best = max(rows, key=lambda row: float(row[POSE_MAP50_95]))
    return {"epoch": int(best["epoch"]), "pose_map50": float(best[POSE_MAP50]), "pose_map50_95": float(best[POSE_MAP50_95])}


def training_info(best, data_yaml, runs_dir):
    export_dir = data_yaml.parent
    commit, changed = code_version()
    return {
        "model_sha256": hashlib.sha256(best.read_bytes()).hexdigest(),
        "trained_on": datetime.date.today().isoformat(),
        "base_model": trial.WEIGHTS,
        "epochs": EPOCHS,
        "image_size": trial.IMAGE_SIZE,
        "images": {split: sorted(path.name for path in (export_dir / "images" / split).glob("*")) for split in ("train", "val")},
        "code_commit": commit,
        "code_changed": changed,
        "metrics": best_metrics(runs_dir / RUN_NAME / "results.csv"),
    }


def run(data_yaml=paths.EXPORT / "data.yaml", runs_dir=paths.RUNS, model_path=paths.LATEST_MODEL, model_factory=YOLO, device=None, info_path=paths.LATEST_INFO):
    trial.require_dataset(data_yaml)
    best, _ = trial.train(data_yaml, runs_dir, model_factory, device or trial.default_device(), EPOCHS, RUN_NAME)
    info = training_info(best, data_yaml, runs_dir)
    with open(best, "rb") as source, annotations.atomic_writer(model_path) as destination:
        shutil.copyfileobj(source, destination)
    with annotations.atomic_writer(info_path) as destination:
        destination.write((json.dumps(info, indent=2) + "\n").encode("utf-8"))
    return model_path


def main():
    try:
        model_path = run()
    except (trial.TrainingError, RuntimeError, OSError, KeyboardInterrupt) as error:
        print(f"Training stopped: {error!r}. The previous model stays in use.")
        return 1
    print(f"Model saved to {model_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
