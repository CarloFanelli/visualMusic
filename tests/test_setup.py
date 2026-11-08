import os
import subprocess

from dataset_tools.paths import ROOT


def test_setup_refuses_a_python_older_than_the_tools_need(tmp_path):
    fake_python = tmp_path / "python3"
    fake_python.write_text("#!/bin/sh\nexit 1\n")
    fake_python.chmod(0o755)
    result = subprocess.run(
        [str(ROOT / "scripts" / "setup.sh")],
        env={**os.environ, "PATH": f"{tmp_path}:/usr/bin:/bin"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "Python 3.11" in result.stderr
