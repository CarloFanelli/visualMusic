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
        "screenshot.jpg",
        "docs/photo.PNG",
        "tests/clip.Mp4",
    ],
)
def test_image_and_video_files_stay_out_of_git(path):
    assert is_ignored(path)


@pytest.mark.parametrize("path", ["data/manifest.jsonl", "data/annotations/photo.json"])
def test_manifest_and_annotations_can_be_committed(path):
    assert not is_ignored(path)
