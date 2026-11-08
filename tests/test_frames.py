import cv2
import numpy as np
import pytest

from dataset_tools import frames, manifest


def write_video(path, seconds=3.5, fps=10, size=(64, 48)):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    assert writer.isOpened()
    for index in range(int(seconds * fps)):
        writer.write(np.full((size[1], size[0], 3), index * 5 % 255, dtype=np.uint8))
    writer.release()


@pytest.fixture
def dirs(tmp_path):
    videos = tmp_path / "videos"
    videos.mkdir()
    return videos, tmp_path / "images", tmp_path / "manifest.jsonl"


def test_frames_become_user_owned_candidates_linked_to_their_video(dirs):
    videos, images, manifest_path = dirs
    write_video(videos / "take.mp4")

    added, errors = frames.extract(videos, images, manifest_path, today="2026-11-08")

    records = manifest.load(manifest_path)
    assert errors == {}
    assert added == {"take.mp4": len(records)} and len(records) >= 3
    for record in records:
        assert record["license"] == frames.USER_OWNED
        assert record["video_file"] == "take.mp4"
        assert record["video_id"] in record["image_id"]
        assert (images / record["file"]).exists()


def test_kept_frames_are_at_least_one_second_apart(dirs):
    videos, images, manifest_path = dirs
    write_video(videos / "take.mp4")
    frames.extract(videos, images, manifest_path)
    timestamps = [record["timestamp_ms"] for record in manifest.load(manifest_path)]
    assert all(later - earlier >= 1000 for earlier, later in zip(timestamps, timestamps[1:]))


def test_processing_twice_or_renaming_adds_no_duplicates(dirs):
    videos, images, manifest_path = dirs
    write_video(videos / "take.mp4")
    frames.extract(videos, images, manifest_path)
    first_run = manifest_path.read_bytes()

    assert frames.extract(videos, images, manifest_path)[0] == {"take.mp4": 0}
    (videos / "take.mp4").rename(videos / "renamed.mp4")
    assert frames.extract(videos, images, manifest_path)[0] == {"renamed.mp4": 0}
    assert manifest_path.read_bytes() == first_run


def test_unreadable_video_is_named_and_others_continue(dirs):
    videos, images, manifest_path = dirs
    (videos / "broken.mp4").write_bytes(b"not a video")
    write_video(videos / "take.mp4")

    added, errors = frames.extract(videos, images, manifest_path)

    assert "broken.mp4" in errors
    assert added["take.mp4"] >= 3


def test_portrait_video_keeps_its_portrait_shape(dirs):
    videos, images, manifest_path = dirs
    write_video(videos / "portrait.mp4", seconds=1, size=(48, 64))
    frames.extract(videos, images, manifest_path)
    record = manifest.load(manifest_path)[0]
    height, width = cv2.imread(str(images / record["file"])).shape[:2]
    assert height > width


def test_missing_videos_folder_adds_nothing(tmp_path):
    assert frames.extract(tmp_path / "none", tmp_path / "images", tmp_path / "manifest.jsonl") == ({}, {})
