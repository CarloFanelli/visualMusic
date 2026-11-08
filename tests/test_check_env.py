import builtins

from dataset_tools import check_env


def test_reports_version_and_available_gpu():
    lines = check_env.describe("1.2.3", True)
    assert "YOLO (ultralytics) version: 1.2.3" in lines
    assert "Apple GPU acceleration: available" in lines


def test_warns_without_failing_when_gpu_is_unavailable():
    lines = check_env.describe("1.2.3", False)
    assert any(line.startswith("WARNING") for line in lines)


def test_points_to_setup_when_environment_is_missing(monkeypatch, capsys):
    real_import = builtins.__import__

    def fail_for_training_packages(name, *args, **kwargs):
        if name in {"torch", "ultralytics"}:
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_for_training_packages)
    assert check_env.main() == 1
    assert check_env.SETUP_HINT in capsys.readouterr().out
