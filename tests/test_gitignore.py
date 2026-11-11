import subprocess

import pytest

from dataset_tools.paths import ROOT


def is_ignored(path):
    result = subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT)
    return result.returncode == 0


@pytest.mark.parametrize(
    "path",
    [
        "data/images/photo.jpg",
        "data/images/photo.webp",
        "data/videos/clip.mov",
        "data/previews/photo.jpg",
        "data/export/images/train/photo.jpg",
        "data/proposals/photo.json",
        "data/annotations/.photo.abc123.part",
        "data/annotations/photo.json",
        "data/manifest.jsonl",
        "screenshot.jpg",
        "docs/photo.PNG",
        "tests/clip.Mp4",
    ],
)
def test_personal_data_stays_out_of_git(path):
    assert is_ignored(path)
