from types import SimpleNamespace

import numpy as np
import pytest
import torch
from PIL import Image

from dataset_tools import trial


def dataset(tmp_path, images=("a", "b")):
    root = tmp_path / "export"
    (root / "images" / "val").mkdir(parents=True)
    (root / "data.yaml").write_text("path: x\n")
    for name in images:
        Image.new("RGB", (40, 30), "white").save(root / "images" / "val" / f"{name}.jpg")
    return root / "data.yaml"


def detection():
    return SimpleNamespace(
        orig_img=np.full((30, 40, 3), 255, dtype=np.uint8),
        boxes=SimpleNamespace(conf=torch.tensor([0.2, 0.9])),
        keypoints=SimpleNamespace(xy=torch.tensor([[[1.0, 1.0]], [[20.0, 15.0]]])),
    )


def no_detection():
    return SimpleNamespace(
        orig_img=np.full((30, 40, 3), 255, dtype=np.uint8),
        boxes=SimpleNamespace(conf=torch.tensor([])),
        keypoints=None,
    )


class FakeModel:
    instances = []
    failures_left = 0

    def __init__(self, source):
        self.source = source
        self.train_arguments = None
        FakeModel.instances.append(self)

    def train(self, **arguments):
        self.train_arguments = arguments
        if arguments["device"] == "mps" and FakeModel.failures_left:
            FakeModel.failures_left -= 1
            raise RuntimeError("MPS backend failure")
        best = arguments["project"] / arguments["name"] / "weights" / "best.pt"
        best.parent.mkdir(parents=True, exist_ok=True)
        best.write_bytes(b"model")
        self.trainer = SimpleNamespace(best=best)

    def predict(self, source, **arguments):
        return [no_detection() if source.endswith("a.jpg") else detection()]


@pytest.fixture(autouse=True)
def reset_fake():
    FakeModel.instances = []
    FakeModel.failures_left = 0


def test_missing_dataset_stops_and_names_the_export_command(tmp_path):
    with pytest.raises(trial.TrainingError, match="dataset_tools.export"):
        trial.run(tmp_path / "none" / "data.yaml", tmp_path / "runs", FakeModel, "cpu")
    assert FakeModel.instances == []


def test_trial_saves_a_model_file_and_draws_validation_images(tmp_path):
    result = trial.run(dataset(tmp_path), tmp_path / "runs", FakeModel, "cpu")
    assert result.model_path.read_bytes() == b"model"
    assert sorted(path.name for path in result.predictions_dir.iterdir()) == ["a.jpg", "b.jpg"]


def test_training_is_short_and_written_to_the_runs_folder(tmp_path):
    trial.run(dataset(tmp_path), tmp_path / "runs", FakeModel, "cpu")
    arguments = FakeModel.instances[0].train_arguments
    assert arguments["epochs"] == trial.EPOCHS
    assert arguments["project"] == tmp_path / "runs"
    assert arguments["exist_ok"] is True


def test_gpu_failure_falls_back_to_cpu_with_a_visible_notice(tmp_path, capsys):
    FakeModel.failures_left = 1
    trial.run(dataset(tmp_path), tmp_path / "runs", FakeModel, "mps")
    assert [model.train_arguments["device"] for model in FakeModel.instances if model.train_arguments] == ["mps", "cpu"]
    assert "CPU" in capsys.readouterr().out


def test_image_without_detection_gets_a_label_and_no_error(tmp_path):
    result = trial.run(dataset(tmp_path), tmp_path / "runs", FakeModel, "cpu")
    assert result.no_detection == 1
    assert result.detected == 1


def test_predicted_points_are_drawn_on_the_most_confident_detection():
    drawn = trial.draw(detection())
    assert drawn[15, 20].tolist() != [255, 255, 255]
    assert drawn[1, 1].tolist() == [255, 255, 255]


def large_detection():
    return SimpleNamespace(
        orig_img=np.full((3000, 4000, 3), 255, dtype=np.uint8),
        boxes=SimpleNamespace(conf=torch.tensor([0.9])),
        keypoints=SimpleNamespace(xy=torch.tensor([[[2000.0, 1500.0]]])),
    )


def test_points_stay_visible_when_a_large_photo_is_viewed_small():
    drawn = trial.draw(large_detection())
    # At about 10% of a 4000-pixel photo's width, a mark needs a radius of tens of pixels.
    assert drawn[1500, 2030].tolist() != [255, 255, 255]


def test_no_detection_label_stays_readable_on_a_large_photo():
    large = SimpleNamespace(
        orig_img=np.full((3000, 4000, 3), 255, dtype=np.uint8),
        boxes=SimpleNamespace(conf=torch.tensor([])),
        keypoints=None,
    )
    changed_rows = np.where((trial.draw(large) != 255).any(axis=(1, 2)))[0]
    assert changed_rows.max() - changed_rows.min() > 60


def test_no_detection_label_changes_the_image():
    assert (trial.draw(no_detection()) != 255).any()


def test_regenerated_output_replaces_old_predictions(tmp_path):
    data_yaml = dataset(tmp_path)
    first = trial.run(data_yaml, tmp_path / "runs", FakeModel, "cpu")
    (first.predictions_dir / "stale.jpg").write_bytes(b"old")
    second = trial.run(data_yaml, tmp_path / "runs", FakeModel, "cpu")
    assert not (second.predictions_dir / "stale.jpg").exists()


class AlwaysFailingModel(FakeModel):
    def train(self, **arguments):
        raise RuntimeError("Dataset error")


def test_failed_training_leaves_no_old_predictions(tmp_path):
    data_yaml = dataset(tmp_path)
    first = trial.run(data_yaml, tmp_path / "runs", FakeModel, "cpu")
    with pytest.raises(RuntimeError):
        trial.run(data_yaml, tmp_path / "runs", AlwaysFailingModel, "cpu")
    assert not first.predictions_dir.exists()


def test_failed_training_stops_without_a_traceback(monkeypatch, capsys):
    def fail():
        raise RuntimeError("Dataset error")

    monkeypatch.setattr(trial, "run", fail)
    assert trial.main() == 1
    assert "Trial stopped: Dataset error" in capsys.readouterr().out


def test_notice_shows_the_error_without_blaming_the_gpu(tmp_path, capsys):
    FakeModel.failures_left = 1
    trial.run(dataset(tmp_path), tmp_path / "runs", FakeModel, "mps")
    output = capsys.readouterr().out
    assert "MPS backend failure" in output
    assert "failed" not in output
