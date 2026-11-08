from types import SimpleNamespace

import pytest

from dataset_tools import train, trial


class FakeModel:
    instances = []
    failures_left = 0
    always_fails = False
    interrupted = False

    def __init__(self, source):
        self.source = source
        self.train_arguments = None
        FakeModel.instances.append(self)

    def train(self, **arguments):
        self.train_arguments = arguments
        if FakeModel.interrupted:
            raise KeyboardInterrupt
        if FakeModel.always_fails or (arguments["device"] == "mps" and FakeModel.failures_left):
            FakeModel.failures_left -= 1
            raise RuntimeError("backend failure")
        best = arguments["project"] / arguments["name"] / "weights" / "best.pt"
        best.parent.mkdir(parents=True, exist_ok=True)
        best.write_bytes(b"new model")
        self.trainer = SimpleNamespace(best=best)


@pytest.fixture(autouse=True)
def reset_fake():
    FakeModel.instances = []
    FakeModel.failures_left = 0
    FakeModel.always_fails = False
    FakeModel.interrupted = False


@pytest.fixture
def layout(tmp_path):
    data_yaml = tmp_path / "export" / "data.yaml"
    data_yaml.parent.mkdir()
    data_yaml.write_text("path: x\n")
    return SimpleNamespace(data_yaml=data_yaml, runs=tmp_path / "runs", model=tmp_path / "runs" / "latest.pt")


def run(layout, device="cpu"):
    return train.run(layout.data_yaml, layout.runs, layout.model, FakeModel, device)


def test_training_runs_for_all_passes_from_the_base_model(layout):
    run(layout)
    model = FakeModel.instances[0]
    assert model.source == trial.WEIGHTS
    assert model.train_arguments["epochs"] == 100
    assert model.train_arguments["data"] == str(layout.data_yaml)


def test_success_publishes_the_best_result(layout):
    assert run(layout) == layout.model
    assert layout.model.read_bytes() == b"new model"


def test_a_new_training_replaces_the_published_model(layout):
    layout.model.parent.mkdir()
    layout.model.write_bytes(b"old model")
    run(layout)
    assert layout.model.read_bytes() == b"new model"


def test_failed_training_leaves_the_previous_model(layout):
    layout.model.parent.mkdir()
    layout.model.write_bytes(b"old model")
    FakeModel.always_fails = True
    with pytest.raises(RuntimeError):
        run(layout)
    assert layout.model.read_bytes() == b"old model"


def test_interrupted_training_leaves_the_previous_model(layout):
    layout.model.parent.mkdir()
    layout.model.write_bytes(b"old model")
    FakeModel.interrupted = True
    with pytest.raises(KeyboardInterrupt):
        run(layout)
    assert layout.model.read_bytes() == b"old model"


def test_missing_dataset_stops_and_names_the_export_command(layout):
    layout.data_yaml.unlink()
    with pytest.raises(trial.TrainingError, match="dataset_tools.export"):
        run(layout)
    assert FakeModel.instances == []


def test_gpu_failure_falls_back_to_cpu_with_a_visible_notice(layout, capsys):
    FakeModel.failures_left = 1
    run(layout, "mps")
    assert [model.train_arguments["device"] for model in FakeModel.instances] == ["mps", "cpu"]
    assert "CPU" in capsys.readouterr().out
    assert layout.model.read_bytes() == b"new model"


def test_command_reports_the_saved_model(layout, monkeypatch, capsys):
    monkeypatch.setattr(train, "run", lambda: layout.model)
    assert train.main() == 0
    assert str(layout.model) in capsys.readouterr().out


@pytest.mark.parametrize("error", [trial.TrainingError("no dataset"), RuntimeError("broken"), KeyboardInterrupt()])
def test_command_explains_a_stop_and_fails(error, monkeypatch, capsys):
    def stop():
        raise error

    monkeypatch.setattr(train, "run", stop)
    assert train.main() == 1
    assert "previous model" in capsys.readouterr().out
