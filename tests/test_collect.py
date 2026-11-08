import hashlib
import io

import pytest
from PIL import Image

from dataset_tools import collect as collect_module
from dataset_tools import images, manifest
from dataset_tools.http_client import RequestFailed
from dataset_tools.sources import Candidate


def jpeg_bytes(color):
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), color).save(buffer, "JPEG")
    return buffer.getvalue()


class FakeHttp:
    def __init__(self, files):
        self.files = files
        self.downloads = []

    def download(self, url, destination):
        self.downloads.append(url)
        content = self.files[url]
        if isinstance(content, Exception):
            raise content
        destination.write_bytes(content)
        return hashlib.sha256(content).hexdigest()


def candidate(key, license_raw="CC BY 4.0", author="Ann", **overrides):
    values = dict(
        image_id=f"test-{key}",
        source="Test",
        source_url=f"https://page.example/{key}",
        download_url=f"https://file.example/{key}",
        author=author,
        license_raw=license_raw,
        license_url="https://creativecommons.org/licenses/by/4.0",
    )
    values.update(overrides)
    return Candidate(**values)


def source(*items):
    def candidates(http, notes, cache_directory):
        yield from items

    return ("Test", candidates)


@pytest.fixture
def run(tmp_path):
    manifest_path = tmp_path / "manifest.jsonl"
    images_dir = tmp_path / "images"

    def _run(http, *sources, **options):
        return collect_module.collect(
            http, sources=sources, images_dir=images_dir, manifest_path=manifest_path, cache_dir=tmp_path / "cache", today="2026-11-08", **options
        )

    _run.manifest_path = manifest_path
    _run.images_dir = images_dir
    return _run


def test_kept_image_has_a_complete_record_and_its_file(run):
    http = FakeHttp({"https://file.example/a": jpeg_bytes("red")})
    reports = run(http, source(candidate("a")))

    record = manifest.load(run.manifest_path)[0]
    assert reports[0].kept == 1
    assert record == {
        "image_id": "test-a",
        "source": "Test",
        "source_url": "https://page.example/a",
        "download_url": "https://file.example/a",
        "author": "Ann",
        "license": "cc-by",
        "license_raw": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0",
        "collected_on": "2026-11-08",
        "sha256": hashlib.sha256(http.files["https://file.example/a"]).hexdigest(),
        "file": "test-a.jpg",
    }
    assert (run.images_dir / "test-a.jpg").exists()


def test_rejections_are_counted_by_reason_and_nothing_is_downloaded(run):
    http = FakeHttp({})
    reports = run(
        http,
        source(
            candidate("sa", license_raw="CC BY-SA 4.0"),
            candidate("nc", license_raw="CC BY-NC 4.0"),
            candidate("nd", license_raw="CC BY-ND 4.0"),
            candidate("gpl", license_raw="GPL"),
            candidate("gfdl", license_raw="GFDL"),
            candidate("none", license_raw=None),
            candidate("odd", license_raw="Attribution"),
            candidate("anon", author=None),
            candidate("audio", unsupported_reason="unsupported-format"),
        ),
    )
    assert dict(reports[0].rejected) == {
        "share-alike": 1,
        "non-commercial": 1,
        "no-derivatives": 1,
        "gpl": 1,
        "gfdl": 1,
        "missing-license": 1,
        "unrecognised": 1,
        "no-author": 1,
        "unsupported-format": 1,
    }
    assert http.downloads == []
    assert manifest.load(run.manifest_path) == []


def test_public_domain_image_without_author_is_kept(run):
    http = FakeHttp({"https://file.example/a": jpeg_bytes("red")})
    run(http, source(candidate("a", license_raw="Public domain", author=None)))
    assert manifest.load(run.manifest_path)[0]["author"] == "unknown"


def test_failed_download_creates_no_record_and_no_file(run):
    http = FakeHttp({"https://file.example/a": RequestFailed("gone")})
    reports = run(http, source(candidate("a")))
    assert reports[0].rejected["download-failed"] == 1
    assert manifest.load(run.manifest_path) == []
    assert list(run.images_dir.iterdir()) == []


def test_file_that_is_not_an_image_is_rejected(run):
    http = FakeHttp({"https://file.example/a": b"<html>not an image</html>"})
    reports = run(http, source(candidate("a")))
    assert reports[0].rejected["unsupported-format"] == 1
    assert list(run.images_dir.iterdir()) == []


def test_same_image_from_two_sources_is_kept_once(run):
    same = jpeg_bytes("red")
    http = FakeHttp({"https://file.example/a": same, "https://file.example/b": same})
    reports = run(http, source(candidate("a")), source(candidate("b")))
    assert reports[0].kept == 1
    assert reports[1].rejected["duplicate"] == 1
    assert [p.name for p in run.images_dir.iterdir()] == ["test-a.jpg"]


def test_second_run_leaves_earlier_records_byte_identical_and_adds_only_new_images(run):
    http = FakeHttp({"https://file.example/a": jpeg_bytes("red"), "https://file.example/b": jpeg_bytes("blue")})
    run(http, source(candidate("a")))
    first_run = run.manifest_path.read_bytes()

    reports = run(http, source(candidate("a"), candidate("b")))

    assert run.manifest_path.read_bytes().startswith(first_run)
    assert reports[0].already_known == 1
    assert reports[0].kept == 1
    assert http.downloads.count("https://file.example/a") == 1


def test_run_continues_after_an_interruption_without_duplicates(run):
    http = FakeHttp({"https://file.example/a": jpeg_bytes("red"), "https://file.example/b": jpeg_bytes("blue")})
    run(http, source(candidate("a")))
    with open(run.manifest_path, "ab") as file:
        file.write(b'{"image_id": "test-b", "torn')

    run(http, source(candidate("a"), candidate("b")))

    assert [record["image_id"] for record in manifest.load(run.manifest_path)] == ["test-a", "test-b"]


def test_unreachable_source_is_named_and_others_continue(run):
    def broken(http, notes, cache_directory):
        raise RequestFailed("service down")
        yield

    http = FakeHttp({"https://file.example/a": jpeg_bytes("red")})
    reports = run(http, ("Broken", broken), source(candidate("a")))

    assert reports[0].failure == "service down"
    assert any("FAILED" in line for line in reports[0].lines())
    assert reports[1].kept == 1


def test_source_without_results_reports_zero_and_continues(run):
    http = FakeHttp({"https://file.example/a": jpeg_bytes("red")})
    reports = run(http, source(), source(candidate("a")))
    assert reports[0].kept == 0
    assert reports[0].failure is None
    assert reports[1].kept == 1


def test_limit_stops_after_the_requested_number_of_new_images(run):
    http = FakeHttp({"https://file.example/a": jpeg_bytes("red"), "https://file.example/b": jpeg_bytes("blue")})
    reports = run(http, source(candidate("a"), candidate("b")), limit=1)
    assert reports[0].kept == 1
    assert len(manifest.load(run.manifest_path)) == 1


def test_image_without_a_source_page_is_rejected():
    family, reason = collect_module.rejection_reason(candidate("a", source_url=""))
    assert family is None
    assert reason == "no-source-url"


def test_cc_by_image_without_a_license_url_is_rejected():
    family, reason = collect_module.rejection_reason(candidate("a", license_url=None))
    assert family is None
    assert reason == "no-license-url"


def test_public_domain_image_may_have_no_license_url():
    assert collect_module.rejection_reason(candidate("a", license_raw="Public domain", license_url=None)) == ("public-domain", None)


def test_multi_picture_jpeg_is_kept_as_a_jpeg(tmp_path):
    path = tmp_path / "multi.part"
    Image.new("RGB", (8, 8), "red").save(path, "MPO", save_all=True, append_images=[Image.new("RGB", (8, 8), "blue")])
    assert images.extension_of(path) == "jpg"
