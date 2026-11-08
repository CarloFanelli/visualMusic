"""Drives the annotation page in real Chrome, on generated images."""
import json
import threading
from types import SimpleNamespace

import pytest
from PIL import Image

sync_api = pytest.importorskip("playwright.sync_api")

from dataset_tools import instrument, manifest  # noqa: E402
from dataset_tools.annotate import server as server_module  # noqa: E402

LOADED = "document.getElementById('photo').complete && document.getElementById('photo').naturalWidth > 0"
ANNOTATION_REQUESTS = "**/api/images/*/annotation"
IMAGE_REQUESTS = "**/images/*"
FINISHED = "Nessun'altra"


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as playwright:
        try:
            chrome = playwright.chromium.launch(channel="chrome", headless=True)
        except sync_api.Error as error:
            pytest.skip(f"Chrome is not available: {error}")
        yield chrome
        chrome.close()


def start_app(tmp_path, count):
    storage = server_module.Storage(tmp_path / "manifest.jsonl", tmp_path / "annotations", tmp_path / "images", tmp_path / "previews")
    storage.images_dir.mkdir()
    image_ids = [f"image-{number}" for number in range(count)]
    for number, image_id in enumerate(image_ids):
        manifest.append({"image_id": image_id, "file": f"{image_id}.jpg"}, storage.manifest_path)
        Image.new("RGB", (800, 600), (40 * number, 80, 120)).save(storage.images_dir / f"{image_id}.jpg")
    server = server_module.create_server(instrument.load(), storage, port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, SimpleNamespace(url=f"http://127.0.0.1:{server.server_address[1]}", ids=image_ids, storage=storage)


@pytest.fixture
def app(tmp_path):
    server, details = start_app(tmp_path, 4)
    yield details
    server.shutdown()
    server.server_close()


@pytest.fixture
def new_page(browser):
    pages = []
    errors = []

    def create():
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.on("pageerror", lambda error: errors.append(str(error)))
        pages.append(page)
        return page

    yield create
    for page in pages:
        page.close()
    assert not errors


@pytest.fixture
def page(app, new_page):
    opened = new_page()
    opened.goto(app.url)
    opened.wait_for_function(LOADED)
    return opened


def click_photo(page, x, y):
    box = page.locator("#photo").bounding_box()
    page.mouse.click(box["x"] + box["width"] * x, box["y"] + box["height"] * y)


def current(page):
    return page.locator('#list button[aria-current="true"]').get_attribute("data-id")


def row(page, image_id):
    return page.locator(f'#list button[data-id="{image_id}"]').inner_text()


def open_from_list(page, image_id):
    page.locator(f'#list button[data-id="{image_id}"]').click()
    page.wait_for_function(LOADED)


def wait_until_left(page, image_id):
    page.wait_for_function(
        "([id, finished]) => document.getElementById('prompt').textContent.startsWith(finished)"
        " || document.querySelector('#list button[aria-current=\"true\"]').dataset.id !== id",
        arg=[image_id, FINISHED],
    )


def annotate_current(page, x=0.5):
    page.wait_for_function(LOADED)
    image_id = current(page)
    for _ in range(4):
        click_photo(page, x, 0.5)
    wait_until_left(page, image_id)
    return image_id


def stored(app, image_id):
    return json.loads((app.storage.annotations_dir / f"{image_id}.json").read_text())


def is_finished(page):
    return page.inner_text("#prompt").startswith(FINISHED)


def test_page_lists_images_and_asks_for_the_first_point(page, app):
    assert page.locator("#list button").count() == len(app.ids)
    assert f"0 di {len(app.ids)}" in page.inner_text("#progress")
    assert page.inner_text("#prompt") == "Punto 1 di 4: centro campana"


def test_click_outside_the_image_is_ignored(page):
    page.mouse.click(5, 790)
    assert page.inner_text("#prompt").startswith("Punto 1")


def test_points_follow_the_order_and_save_then_the_next_image_opens(page, app):
    first = current(page)
    for x, y, label in [(0.2, 0.3, "bordo sinistro"), (0.4, 0.5, "bordo destro"), (0.6, 0.7, "bocchino")]:
        click_photo(page, x, y)
        assert label in page.inner_text("#prompt")
    assert page.locator(".marker").count() == 3
    click_photo(page, 0.8, 0.9)
    wait_until_left(page, first)

    saved = stored(app, first)["points"]
    assert [point["name"] for point in saved] == ["bell_centre", "bell_edge_left", "bell_edge_right", "mouthpiece"]
    assert saved[0]["x"] == pytest.approx(0.2, abs=0.01)
    assert saved[3]["y"] == pytest.approx(0.9, abs=0.01)
    assert f"1 di {len(app.ids)}" in page.inner_text("#progress")
    assert row(page, first).startswith("[x]")


def test_click_while_the_next_image_loads_is_ignored(app, new_page):
    held = []
    page = new_page()
    first_url = f"{app.url}/images/{app.ids[0]}"

    def hold_later_images(route):
        if route.request.url == first_url:
            route.continue_()
        else:
            held.append(route)

    page.route(IMAGE_REQUESTS, hold_later_images)
    page.goto(app.url)
    page.wait_for_function(LOADED)
    first = current(page)
    for _ in range(4):
        click_photo(page, 0.5, 0.5)
    wait_until_left(page, first)

    click_photo(page, 0.5, 0.5)
    assert page.inner_text("#prompt").startswith("Punto 1")

    for route in held:
        route.continue_()
    page.wait_for_function(LOADED)
    click_photo(page, 0.5, 0.5)
    assert page.inner_text("#prompt").startswith("Punto 2")


def test_partly_marked_image_is_discarded_on_reload(page):
    first = annotate_current(page)
    click_photo(page, 0.5, 0.5)
    page.reload()
    page.wait_for_function(LOADED)
    assert page.locator(".marker").count() == 0
    assert current(page) != first
    assert page.inner_text("#prompt").startswith("Punto 1")


def test_reopened_image_shows_saved_points_and_can_be_changed(page, app):
    first = annotate_current(page, 0.5)
    open_from_list(page, first)
    page.wait_for_selector(".marker.saved")
    assert page.locator(".marker.saved").count() == 4
    annotate_current(page, 0.25)
    assert stored(app, first)["points"][0]["x"] == pytest.approx(0.25, abs=0.01)


def test_failed_save_stays_on_the_image_and_retry_advances(page, app):
    target = current(page)
    page.route(ANNOTATION_REQUESTS, lambda route: route.abort())
    for _ in range(4):
        click_photo(page, 0.5, 0.5)
    page.wait_for_selector("#retry:not([hidden])")
    assert current(page) == target
    assert "non riuscito" in page.inner_text("#message")

    page.unroute(ANNOTATION_REQUESTS)
    page.click("#retry")
    wait_until_left(page, target)
    assert stored(app, target)["status"] == "annotated"


def test_with_two_tabs_the_last_save_wins(page, app, new_page):
    other = new_page()
    other.goto(app.url)
    other.wait_for_function(LOADED)
    target = current(page)
    annotate_current(page, 0.1)
    open_from_list(other, target)
    annotate_current(other, 0.9)
    assert stored(app, target)["points"][0]["x"] == pytest.approx(0.9, abs=0.01)


def test_unreadable_image_is_marked_and_the_others_stay_usable(app, new_page):
    broken = app.ids[-1]
    (app.storage.images_dir / f"{broken}.jpg").write_bytes(b"not an image")
    page = new_page()
    page.goto(app.url)
    for _ in app.ids[:-1]:
        annotate_current(page)
    page.wait_for_function("finished => document.getElementById('prompt').textContent.startsWith(finished)", arg=FINISHED)
    assert "Illeggibili: 1" in page.inner_text("#message")
    assert "Saltate rimaste: 0" in page.inner_text("#message")
    assert row(page, broken).startswith("[!]")
    assert f"{len(app.ids) - 1} di {len(app.ids)}" in page.inner_text("#progress")


def test_empty_state_names_the_collection_command(tmp_path, new_page):
    server, details = start_app(tmp_path, 0)
    try:
        page = new_page()
        page.goto(details.url)
        page.wait_for_function("document.getElementById('message').textContent.length > 0")
        assert "dataset_tools.collect" in page.inner_text("#message")
    finally:
        server.shutdown()
        server.server_close()


def test_undo_removes_only_the_last_point(page):
    page.click("#undo")
    assert page.inner_text("#prompt").startswith("Punto 1")
    click_photo(page, 0.2, 0.2)
    click_photo(page, 0.3, 0.3)
    page.click("#undo")
    assert page.locator(".marker").count() == 1
    assert page.inner_text("#prompt").startswith("Punto 2")


def test_hidden_point_is_saved_without_a_position(page, app):
    first = current(page)
    page.click("#hide-point")
    assert page.inner_text("#prompt").startswith("Punto 2")
    for x in (0.3, 0.4, 0.5):
        click_photo(page, x, 0.5)
    wait_until_left(page, first)
    saved = stored(app, first)["points"]
    assert saved[0] == {"name": "bell_centre", "visible": False}
    assert saved[1]["x"] == pytest.approx(0.3, abs=0.01)

    open_from_list(page, first)
    page.wait_for_selector(".marker.saved")
    assert page.locator(".marker.saved").count() == 3


def test_all_points_hidden_cannot_be_saved(page, app):
    target = current(page)
    for _ in range(4):
        page.click("#hide-point")
    assert page.inner_text("#prompt") == "Nessun punto visibile"
    assert "Non adatta" in page.inner_text("#message")
    assert not (app.storage.annotations_dir / f"{target}.json").exists()

    page.click("#undo")
    assert page.inner_text("#prompt").startswith("Punto 4")
    assert page.inner_text("#message") == ""


def test_skipped_image_survives_a_reload_and_returns_after_the_pending_ones(page, app):
    skipped = current(page)
    page.click("#skip")
    wait_until_left(page, skipped)
    assert stored(app, skipped) == {"status": "skipped"}
    assert row(page, skipped).startswith("[~]")

    page.reload()
    page.wait_for_function(LOADED)
    assert row(page, skipped).startswith("[~]")
    assert current(page) != skipped

    while not is_finished(page):
        annotate_current(page)
    assert "Saltate rimaste: 1" in page.inner_text("#message")

    page.click("#resume-skipped")
    page.wait_for_function(LOADED)
    assert current(page) == skipped
    annotate_current(page)
    assert stored(app, skipped)["status"] == "annotated"
    assert "Saltate rimaste: 0" in page.inner_text("#message")


def test_rejected_image_ignores_clicks_until_it_is_restored(page, app):
    rejected = current(page)
    page.click("#reject")
    wait_until_left(page, rejected)
    page.reload()
    page.wait_for_function(LOADED)
    assert row(page, rejected).startswith("[-]")

    open_from_list(page, rejected)
    page.wait_for_selector("#restore:not([hidden])")
    assert page.inner_text("#prompt") == "Immagine scartata"
    click_photo(page, 0.5, 0.5)
    assert page.locator(".marker").count() == 0

    page.click("#restore")
    page.wait_for_function("document.getElementById('prompt').textContent.startsWith('Punto 1')")
    assert row(page, rejected).startswith("[ ]")


def test_failed_skip_stays_on_the_image_and_retry_finishes_it(page, app):
    target = current(page)
    page.route(ANNOTATION_REQUESTS, lambda route: route.abort())
    page.click("#skip")
    page.wait_for_selector("#retry:not([hidden])")
    assert current(page) == target

    page.unroute(ANNOTATION_REQUESTS)
    page.click("#retry")
    wait_until_left(page, target)
    assert stored(app, target) == {"status": "skipped"}
