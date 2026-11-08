"""Trains the model fully and publishes the result as the model used for proposals."""
import shutil
import sys

from ultralytics import YOLO

from dataset_tools import annotations, paths, trial

EPOCHS = 100
RUN_NAME = "full"


def run(data_yaml=paths.EXPORT / "data.yaml", runs_dir=paths.RUNS, model_path=paths.LATEST_MODEL, model_factory=YOLO, device=None):
    trial.require_dataset(data_yaml)
    best, _ = trial.train(data_yaml, runs_dir, model_factory, device or trial.default_device(), EPOCHS, RUN_NAME)
    with open(best, "rb") as source, annotations.atomic_writer(model_path) as destination:
        shutil.copyfileobj(source, destination)
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
