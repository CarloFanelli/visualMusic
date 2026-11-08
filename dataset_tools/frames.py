"""Turns the user's own videos into candidate images, at most one frame per second."""
import datetime
import hashlib
import os
import sys

import cv2

from dataset_tools import manifest, paths

SOURCE = "user-video"
USER_OWNED = "user-owned"
MIN_GAP_MS = 1000
JPEG_QUALITY = 95


class UnreadableVideo(Exception):
    pass


def _video_id(path):
    """Based on content, so renaming a video creates no duplicate frames."""
    with open(path, "rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()[:16]


def _record(image_id, video_id, video_name, timestamp_ms, sha256, file_name, today):
    return {
        "image_id": image_id,
        "source": SOURCE,
        "source_url": None,
        "download_url": None,
        "author": "project owner",
        "license": USER_OWNED,
        "license_raw": None,
        "license_url": None,
        "collected_on": today,
        "sha256": sha256,
        "file": file_name,
        "video_id": video_id,
        "video_file": video_name,
        "timestamp_ms": timestamp_ms,
    }


def _save_frame(frame, images_dir, file_name):
    encoded, data = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    if not encoded:
        raise UnreadableVideo("a frame could not be encoded")
    content = data.tobytes()
    images_dir.mkdir(parents=True, exist_ok=True)
    temporary = images_dir / f".{file_name}.part"
    temporary.write_bytes(content)
    os.replace(temporary, images_dir / file_name)
    return hashlib.sha256(content).hexdigest()


def extract_video(path, known_ids, images_dir, manifest_path, today):
    """Returns the number of new frames."""
    video_id = _video_id(path)
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        capture.release()
        raise UnreadableVideo("it cannot be opened as a video")
    capture.set(cv2.CAP_PROP_ORIENTATION_AUTO, 1)

    added = 0
    frames_read = 0
    next_ms = 0
    try:
        while capture.grab():
            frames_read += 1
            timestamp_ms = round(capture.get(cv2.CAP_PROP_POS_MSEC))
            if timestamp_ms < next_ms:
                continue
            next_ms = timestamp_ms + MIN_GAP_MS
            image_id = f"video-{video_id}-{timestamp_ms:08d}"
            if image_id in known_ids:
                continue
            retrieved, frame = capture.retrieve()
            if not retrieved:
                continue
            file_name = f"{image_id}.jpg"
            sha256 = _save_frame(frame, images_dir, file_name)
            manifest.append(_record(image_id, video_id, path.name, timestamp_ms, sha256, file_name, today), manifest_path)
            known_ids.add(image_id)
            added += 1
    finally:
        capture.release()
    if frames_read == 0:
        raise UnreadableVideo("it contains no readable frames")
    return added


def extract(videos_dir=paths.VIDEOS, images_dir=paths.IMAGES, manifest_path=paths.MANIFEST, today=None):
    """Returns (new frames per video name, error per video name)."""
    today = today or datetime.date.today().isoformat()
    known_ids = {record["image_id"] for record in manifest.load(manifest_path)}
    added, errors = {}, {}
    videos = sorted(p for p in videos_dir.iterdir() if p.is_file() and not p.name.startswith(".")) if videos_dir.exists() else []
    for path in videos:
        try:
            added[path.name] = extract_video(path, known_ids, images_dir, manifest_path, today)
        except (UnreadableVideo, OSError) as error:
            errors[path.name] = str(error)
    return added, errors


def main():
    added, errors = extract()
    if not added and not errors:
        print(f"No videos found. Put your videos in {paths.VIDEOS}")
        return 0
    for name, count in added.items():
        print(f"{name}: {count} new frames")
    for name, error in errors.items():
        print(f"{name}: UNREADABLE, {error}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
