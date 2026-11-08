import threading
import time

import pytest
import requests
from PIL import Image

from dataset_tools import annotations, manifest
from dataset_tools import instrument as instrument_module
from dataset_tools.annotate import server as server_module

SAX = instrument_module.load()


def annotation_body():
    return {
        "status": "annotated",
        "points": [{"name": name, "x": 0.25, "y": 0.75, "visible": True} for name in SAX.point_names],
    }


@pytest.fixture
def app(tmp_path):
    storage = server_module.Storage(
        manifest_path=tmp_path / "manifest.jsonl",
        annotations_dir=tmp_path / "annotations",
        images_dir=tmp_path / "images",
        previews_dir=tmp_path / "previews",
    )
    storage.images_dir.mkdir()
    for image_id in ("first", "second"):
        Image.new("RGB", (40, 20), "red").save(storage.images_dir / f"{image_id}.jpg")
        manifest.append({"image_id": image_id, "file": f"{image_id}.jpg"}, storage.manifest_path)
    server = server_module.create_server(SAX, storage, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    server.base_url = f"http://127.0.0.1:{server.server_address[1]}"
    server.storage = storage
    yield server
    server.shutdown()
    server.server_close()


def test_only_this_computer_can_reach_the_server(app):
    assert app.server_address[0] == "127.0.0.1"


def test_page_is_served(app):
    response = requests.get(app.base_url + "/")
    assert response.status_code == 200
    assert "text/html" in response.headers["Content-Type"]


def test_state_lists_images_statuses_and_points_in_order(app):
    state = requests.get(app.base_url + "/api/state").json()
    assert [image["image_id"] for image in state["images"]] == ["first", "second"]
    assert {image["status"] for image in state["images"]} == {"pending"}
    assert [point["name"] for point in state["points"]] == list(SAX.point_names)
    assert state["points"][0]["label"] == "centro campana"


def test_saved_annotation_survives_a_restart_and_can_be_reopened(app):
    url = app.base_url + "/api/images/first/annotation"
    assert requests.put(url, json=annotation_body()).status_code == 200

    restarted = server_module.create_server(SAX, app.storage, port=0)
    thread = threading.Thread(target=restarted.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{restarted.server_address[1]}"
        state = requests.get(base + "/api/state").json()
        assert [image["status"] for image in state["images"]] == ["annotated", "pending"]
        assert requests.get(base + "/api/images/first/annotation").json()["annotation"] == annotation_body()
    finally:
        restarted.shutdown()
        restarted.server_close()


def test_changed_points_replace_the_old_ones(app):
    url = app.base_url + "/api/images/first/annotation"
    requests.put(url, json=annotation_body())
    changed = annotation_body()
    changed["points"][0]["x"] = 0.9
    requests.put(url, json=changed)
    assert requests.get(url).json()["annotation"]["points"][0]["x"] == 0.9


def test_last_save_wins_for_the_same_image(app):
    url = app.base_url + "/api/images/first/annotation"
    for x in (0.1, 0.2):
        body = annotation_body()
        body["points"][0]["x"] = x
        requests.put(url, json=body)
    assert annotations.load("first", app.storage.annotations_dir)["points"][0]["x"] == 0.2


def test_preview_is_upright_and_within_size_limit(tmp_path):
    source = tmp_path / "source.jpg"
    exif = Image.Exif()
    exif[274] = 6  # rotated 90 degrees: a 3000x1000 file is displayed as 1000x3000
    Image.new("RGB", (3000, 1000), "blue").save(source, exif=exif)
    destination = tmp_path / "previews" / "source.jpg"

    server_module.create_preview(source, destination)

    with Image.open(destination) as preview:
        assert preview.size[1] == server_module.PREVIEW_MAX_SIDE
        assert preview.size[0] < preview.size[1]


def test_preview_is_served_quickly_once_cached(app):
    url = app.base_url + "/images/first"
    assert requests.get(url).headers["Content-Type"] == "image/jpeg"
    start = time.perf_counter()
    assert requests.get(url).status_code == 200
    assert time.perf_counter() - start < 0.5


def test_unreadable_image_gives_an_error_and_others_stay_usable(app):
    (app.storage.images_dir / "first.jpg").write_bytes(b"not an image")
    assert requests.get(app.base_url + "/images/first").status_code == 404
    assert requests.get(app.base_url + "/images/second").status_code == 200


def test_missing_image_file_gives_an_error(app):
    (app.storage.images_dir / "first.jpg").unlink()
    assert requests.get(app.base_url + "/images/first").status_code == 404


def test_other_websites_cannot_save(app):
    response = requests.put(
        app.base_url + "/api/images/first/annotation", json=annotation_body(), headers={"Origin": "https://evil.example"}
    )
    assert response.status_code == 403
    assert annotations.load("first", app.storage.annotations_dir) is None


def test_foreign_host_header_is_refused(app):
    assert requests.get(app.base_url + "/api/state", headers={"Host": "evil.example"}).status_code == 403


@pytest.mark.parametrize("image_id", ["..%2F..%2Fescape", "unknown"])
def test_ids_outside_the_manifest_are_refused(app, image_id, tmp_path):
    response = requests.put(app.base_url + f"/api/images/{image_id}/annotation", json=annotation_body())
    assert response.status_code == 404
    assert not (tmp_path / "escape.json").exists()
    assert requests.get(app.base_url + f"/images/{image_id}").status_code == 404


def test_invalid_annotation_is_refused(app):
    body = annotation_body()
    body["points"][0]["x"] = 1.5
    assert requests.put(app.base_url + "/api/images/first/annotation", json=body).status_code == 400
    assert annotations.load("first", app.storage.annotations_dir) is None


def test_failed_save_reports_an_error(app, monkeypatch):
    def fail(*args):
        raise OSError("disk full")

    monkeypatch.setattr(annotations.os, "replace", fail)
    response = requests.put(app.base_url + "/api/images/first/annotation", json=annotation_body())
    assert response.status_code == 500


def test_empty_manifest_gives_an_empty_list(tmp_path):
    storage = server_module.Storage(manifest_path=tmp_path / "none.jsonl", annotations_dir=tmp_path, images_dir=tmp_path, previews_dir=tmp_path)
    server = server_module.create_server(SAX, storage, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        state = requests.get(f"http://127.0.0.1:{server.server_address[1]}/api/state").json()
        assert state["images"] == []
    finally:
        server.shutdown()
        server.server_close()


def test_invalid_definition_stops_the_interface_with_the_problem_named(monkeypatch, capsys):
    def refuse():
        raise instrument_module.InvalidInstrument("saxophone.json is invalid")

    monkeypatch.setattr(instrument_module, "load", refuse)
    monkeypatch.setattr("sys.argv", ["server"])
    assert server_module.main() == 1
    assert "saxophone.json is invalid" in capsys.readouterr().out


@pytest.mark.parametrize("status", ["skipped", "rejected"])
def test_skip_and_reject_are_saved_and_survive_in_the_state(app, status):
    url = app.base_url + "/api/images/first/annotation"
    assert requests.put(url, json={"status": status}).status_code == 200
    state = requests.get(app.base_url + "/api/state").json()
    assert state["images"][0]["status"] == status


def test_a_rejected_image_can_be_restored(app):
    url = app.base_url + "/api/images/first/annotation"
    requests.put(url, json={"status": "rejected"})
    assert requests.put(url, json={"status": "pending"}).status_code == 200
    assert requests.get(app.base_url + "/api/state").json()["images"][0]["status"] == "pending"


def test_every_point_hidden_is_refused_by_the_server(app):
    body = {"status": "annotated", "points": [{"name": name, "visible": False} for name in SAX.point_names]}
    assert requests.put(app.base_url + "/api/images/first/annotation", json=body).status_code == 400
    assert annotations.load("first", app.storage.annotations_dir) is None


def test_annotation_with_a_hidden_point_is_saved_and_reopened(app):
    url = app.base_url + "/api/images/first/annotation"
    body = annotation_body()
    body["points"][0] = {"name": "bell_centre", "visible": False}
    assert requests.put(url, json=body).status_code == 200
    assert requests.get(url).json()["annotation"]["points"][0] == {"name": "bell_centre", "visible": False}
