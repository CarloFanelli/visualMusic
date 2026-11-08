import hashlib
import io

import pytest
from PIL import Image

from dataset_tools import manifest, restore
from dataset_tools.http_client import RequestFailed


def jpeg_bytes(color="red"):
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), color).save(buffer, "JPEG")
    return buffer.getvalue()


class FakeHttp:
    def __init__(self, files=None):
        self.files = files or {}
        self.downloads = []

    def download(self, url, destination):
        self.downloads.append(url)
        content = self.files.get(url, RequestFailed("gone"))
        if isinstance(content, Exception):
            raise content
        destination.write_bytes(content)
        return hashlib.sha256(content).hexdigest()


@pytest.fixture
def dirs(tmp_path):
    images = tmp_path / "images"
    images.mkdir()
    return images, tmp_path / "manifest.jsonl"


def add_online(manifest_path, content, image_id="online-a"):
    record = {
        "image_id": image_id,
        "download_url": f"https://file.example/{image_id}",
        "sha256": hashlib.sha256(content).hexdigest(),
        "file": f"{image_id}.jpg",
    }
    manifest.append(record, manifest_path)
    return record


def test_fresh_clone_gets_available_images_back(dirs):
    images, manifest_path = dirs
    content = jpeg_bytes()
    record = add_online(manifest_path, content)

    report = restore.restore(FakeHttp({record["download_url"]: content}), images, manifest_path)

    assert report.restored == 1
    assert (images / record["file"]).read_bytes() == content


def test_valid_files_are_not_downloaded_again(dirs):
    images, manifest_path = dirs
    content = jpeg_bytes()
    record = add_online(manifest_path, content)
    (images / record["file"]).write_bytes(content)
    http = FakeHttp()

    report = restore.restore(http, images, manifest_path)

    assert report.present == 1
    assert http.downloads == []


def test_image_removed_by_its_source_is_reported_missing(dirs):
    images, manifest_path = dirs
    record = add_online(manifest_path, jpeg_bytes())

    report = restore.restore(FakeHttp(), images, manifest_path)

    assert report.missing == [record["image_id"]]
    assert list(images.iterdir()) == []


def test_downloaded_file_that_differs_from_its_fingerprint_is_not_kept(dirs):
    images, manifest_path = dirs
    record = add_online(manifest_path, jpeg_bytes("red"))

    report = restore.restore(FakeHttp({record["download_url"]: jpeg_bytes("blue")}), images, manifest_path)

    assert report.missing == [record["image_id"]]
    assert list(images.iterdir()) == []


def test_damaged_local_file_is_replaced_from_the_source(dirs):
    images, manifest_path = dirs
    content = jpeg_bytes()
    record = add_online(manifest_path, content)
    (images / record["file"]).write_bytes(b"damaged")

    report = restore.restore(FakeHttp({record["download_url"]: content}), images, manifest_path)

    assert report.restored == 1
    assert (images / record["file"]).read_bytes() == content


def test_missing_user_frame_is_reported_as_restorable_only_from_the_video(dirs):
    images, manifest_path = dirs
    manifest.append({"image_id": "video-a", "download_url": None, "sha256": "x", "file": "video-a.jpg"}, manifest_path)
    http = FakeHttp()

    report = restore.restore(http, images, manifest_path)

    assert report.user_owned_missing == ["video-a"]
    assert http.downloads == []
    assert any("your video" in line for line in report.lines())


def test_manifest_path_outside_the_images_folder_touches_nothing(dirs, tmp_path):
    images, manifest_path = dirs
    outside = tmp_path / "keep.txt"
    outside.write_text("precious")
    record = add_online(manifest_path, jpeg_bytes())
    lines = manifest_path.read_text().replace(record["file"], "../keep.txt")
    manifest_path.write_text(lines)
    report = restore.restore(FakeHttp(), images, manifest_path)
    assert outside.read_text() == "precious"
    assert report.missing == [record["image_id"]]


def test_restore_never_edits_the_manifest(dirs):
    images, manifest_path = dirs
    content = jpeg_bytes()
    add_online(manifest_path, content)
    with open(manifest_path, "ab") as file:
        file.write(b'{"image_id": "torn')
    before = manifest_path.read_bytes()
    restore.restore(FakeHttp({"https://file.example/online-a": content}), images, manifest_path)
    assert manifest_path.read_bytes() == before
