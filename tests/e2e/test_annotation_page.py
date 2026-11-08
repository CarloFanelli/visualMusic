"""Drives the annotation page in real Chrome, on generated images."""
import json
import threading
from types import SimpleNamespace

import pytest
from PIL import Image

sync_api = pytest.importorskip("playwright.sync_api")

from dataset_tools import annotations, instrument, manifest, proposals  # noqa: E402
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
    storage = server_module.Storage(tmp_path / "manifest.jsonl", tmp_path / "annotations", tmp_path / "images", tmp_path / "previews", tmp_path / "proposals")
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


def choose_point(page, index):
    page.locator("#points button").nth(index).click()


def after_confirm_delay(page):
    page.wait_for_timeout(350)


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
    for x, y, label in [(0.2, 0.3, "bordo sinistro"), (0.4, 0.5, "bordo destro"), (0.6, 0.7, "kiver")]:
        click_photo(page, x, y)
        assert label in page.inner_text("#prompt")
    assert page.locator(".marker").count() == 3
    click_photo(page, 0.8, 0.9)
    wait_until_left(page, first)

    saved = stored(app, first)["points"]
    assert [point["name"] for point in saved] == ["bell_centre", "bell_edge_left", "bell_edge_right", "neck"]
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
    page.wait_for_selector(".marker.movable")
    assert page.locator(".marker").count() == 4
    assert page.inner_text("#prompt") == "Controlla i punti e conferma"
    choose_point(page, 0)
    click_photo(page, 0.25, 0.5)
    after_confirm_delay(page)
    page.keyboard.press("Enter")
    wait_until_left(page, first)
    assert stored(app, first)["points"][0]["x"] == pytest.approx(0.25, abs=0.01)
    assert stored(app, first)["points"][1]["x"] == pytest.approx(0.5, abs=0.01)


def test_reopened_image_left_without_confirming_keeps_its_saved_points(page, app):
    first = annotate_current(page, 0.5)
    before = stored(app, first)
    open_from_list(page, first)
    page.wait_for_selector(".marker.movable")
    saved_position = page.locator(".marker").first.get_attribute("style")
    choose_point(page, 0)
    click_photo(page, 0.1, 0.1)
    assert page.locator(".marker").first.get_attribute("style") != saved_position
    open_from_list(page, app.ids[-1])
    assert stored(app, first) == before
    open_from_list(page, first)
    page.wait_for_selector(".marker.movable")
    assert page.locator(".marker").first.get_attribute("style") == saved_position


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
    other.reload()
    open_from_list(other, target)
    other.wait_for_selector(".marker.movable")
    choose_point(other, 0)
    click_photo(other, 0.9, 0.5)
    after_confirm_delay(other)
    other.keyboard.press("Enter")
    wait_until_left(other, target)
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
    page.wait_for_selector(".marker.movable")
    assert page.locator(".marker").count() == 3


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


PROPOSED = "document.querySelectorAll('.marker').length === 4"


def propose_for(app, *image_ids):
    points = [{"name": name, "x": 0.2 * (i + 1), "y": 0.5, "visible": True} for i, name in enumerate(instrument.load().point_names)]
    for image_id in image_ids:
        proposals.save(image_id, points, app.storage.proposals_dir)


def open_proposal_page(app, new_page):
    page = new_page()
    page.goto(app.url)
    page.wait_for_function(LOADED)
    page.wait_for_function(PROPOSED)
    return page


def drag_marker(page, index, x, y):
    box = page.locator("#photo").bounding_box()
    marker = page.locator(f'.marker[data-index="{index}"]').bounding_box()
    page.mouse.move(marker["x"] + marker["width"] / 2, marker["y"] + marker["height"] / 2)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] * x, box["y"] + box["height"] * y, steps=4)
    page.mouse.up()


def confirm_and_read(page, app, image_id):
    after_confirm_delay(page)
    page.keyboard.press("Enter")
    wait_until_left(page, image_id)
    return stored(app, image_id)["points"]


def test_proposal_shows_its_points_with_no_click_and_saves_nothing_until_confirmed(app, new_page):
    propose_for(app, app.ids[0])
    page = open_proposal_page(app, new_page)
    assert current(page) == app.ids[0]
    assert page.inner_text("#prompt") == "Controlla i punti e conferma"
    assert not (app.storage.annotations_dir / f"{app.ids[0]}.json").exists()

    page.reload()
    page.wait_for_function(PROPOSED)
    assert current(page) == app.ids[0]
    assert not (app.storage.annotations_dir / f"{app.ids[0]}.json").exists()


@pytest.mark.parametrize("confirm", [lambda page: page.keyboard.press("Enter"), lambda page: page.click("#confirm")])
def test_enter_and_conferma_save_the_points_and_open_the_next_image(app, new_page, confirm):
    propose_for(app, app.ids[0])
    page = open_proposal_page(app, new_page)
    after_confirm_delay(page)
    confirm(page)
    wait_until_left(page, app.ids[0])
    saved = stored(app, app.ids[0])
    assert saved["status"] == "annotated"
    assert [point["x"] for point in saved["points"]] == pytest.approx([0.2, 0.4, 0.6, 0.8])
    assert "1 di" in page.inner_text("#progress")


def test_click_does_not_change_a_proposal(app, new_page):
    propose_for(app, app.ids[0])
    page = open_proposal_page(app, new_page)
    click_photo(page, 0.9, 0.9)
    assert page.locator(".marker").first.get_attribute("style") == "left: 20%; top: 50%;"
    assert page.inner_text("#prompt") == "Controlla i punti e conferma"


def test_images_with_a_proposal_open_before_those_without(app, new_page):
    propose_for(app, app.ids[2])
    page = open_proposal_page(app, new_page)
    assert current(page) == app.ids[2]
    assert "Da fare: 1 con proposta, 3 senza" in page.inner_text("#progress")
    after_confirm_delay(page)
    page.keyboard.press("Enter")
    wait_until_left(page, app.ids[2])
    page.wait_for_function(LOADED)
    assert current(page) == app.ids[0]
    assert page.inner_text("#prompt").startswith("Punto 1")
    assert "Da fare: 0 con proposta, 3 senza" in page.inner_text("#progress")


def test_holding_enter_confirms_one_image(app, new_page):
    propose_for(app, *app.ids)
    page = open_proposal_page(app, new_page)
    after_confirm_delay(page)
    page.keyboard.down("Enter")
    for _ in range(5):
        page.keyboard.down("Enter")
    page.keyboard.up("Enter")
    wait_until_left(page, app.ids[0])
    page.wait_for_function(PROPOSED)
    page.wait_for_timeout(100)
    assert (app.storage.annotations_dir / f"{app.ids[0]}.json").exists()
    assert not (app.storage.annotations_dir / f"{app.ids[1]}.json").exists()


def test_enter_right_after_the_next_image_appears_is_ignored(app, new_page):
    propose_for(app, *app.ids)
    page = open_proposal_page(app, new_page)
    after_confirm_delay(page)
    page.keyboard.press("Enter")
    wait_until_left(page, app.ids[0])
    page.wait_for_function(PROPOSED)
    page.keyboard.press("Enter")
    page.wait_for_timeout(100)
    assert not (app.storage.annotations_dir / f"{app.ids[1]}.json").exists()
    after_confirm_delay(page)
    page.keyboard.press("Enter")
    wait_until_left(page, app.ids[1])
    assert stored(app, app.ids[1])["status"] == "annotated"


def test_enter_before_the_image_has_loaded_is_ignored(app, new_page):
    propose_for(app, app.ids[0])
    held = []
    page = new_page()
    page.route(IMAGE_REQUESTS, lambda route: held.append(route))
    page.goto(app.url)
    page.wait_for_function(PROPOSED)
    page.wait_for_timeout(350)
    page.keyboard.press("Enter")
    page.wait_for_timeout(100)
    assert not (app.storage.annotations_dir / f"{app.ids[0]}.json").exists()
    for route in held:
        route.continue_()


def test_enter_confirms_without_firing_the_focused_button(app, new_page):
    propose_for(app, app.ids[0])
    page = open_proposal_page(app, new_page)
    page.focus("#reject")
    after_confirm_delay(page)
    page.keyboard.press("Enter")
    wait_until_left(page, app.ids[0])
    assert stored(app, app.ids[0])["status"] == "annotated"


def test_enter_on_an_image_without_a_proposal_fires_nothing(page, app):
    target = current(page)
    page.focus("#reject")
    page.keyboard.press("Enter")
    page.wait_for_timeout(100)
    assert current(page) == target
    assert not (app.storage.annotations_dir / f"{target}.json").exists()


def test_failed_confirmation_stays_on_the_image_and_retry_advances(app, new_page):
    propose_for(app, app.ids[0])
    page = open_proposal_page(app, new_page)
    page.route(ANNOTATION_REQUESTS, lambda route: route.abort())
    after_confirm_delay(page)
    page.keyboard.press("Enter")
    page.wait_for_selector("#retry:not([hidden])")
    assert current(page) == app.ids[0]
    assert page.locator(".marker").count() == 4

    page.unroute(ANNOTATION_REQUESTS)
    page.click("#retry")
    wait_until_left(page, app.ids[0])
    assert stored(app, app.ids[0])["status"] == "annotated"


def test_last_confirmation_shows_completion(tmp_path, new_page):
    server, details = start_app(tmp_path, 1)
    try:
        propose_for(details, details.ids[0])
        page = open_proposal_page(details, new_page)
        after_confirm_delay(page)
        page.keyboard.press("Enter")
        page.wait_for_function("finished => document.getElementById('prompt').textContent.startsWith(finished)", arg=FINISHED)
        assert "Saltate rimaste: 0" in page.inner_text("#message")
    finally:
        server.shutdown()
        server.server_close()


def test_with_two_tabs_the_last_confirmation_wins(app, new_page):
    propose_for(app, app.ids[0])
    first = open_proposal_page(app, new_page)
    second = open_proposal_page(app, new_page)
    after_confirm_delay(first)
    first.keyboard.press("Enter")
    wait_until_left(first, app.ids[0])
    second.keyboard.press("Enter")
    wait_until_left(second, app.ids[0])
    assert stored(app, app.ids[0])["status"] == "annotated"


def test_skip_and_reject_work_on_an_image_with_a_proposal(app, new_page):
    propose_for(app, app.ids[0], app.ids[1])
    page = open_proposal_page(app, new_page)
    page.click("#skip")
    wait_until_left(page, app.ids[0])
    assert stored(app, app.ids[0]) == {"status": "skipped"}
    page.wait_for_function(PROPOSED)
    page.click("#reject")
    wait_until_left(page, app.ids[1])
    assert stored(app, app.ids[1]) == {"status": "rejected"}


def test_skipped_image_returns_with_its_proposal(tmp_path, new_page):
    server, details = start_app(tmp_path, 1)
    try:
        propose_for(details, details.ids[0])
        page = open_proposal_page(details, new_page)
        page.click("#skip")
        page.wait_for_selector("#resume-skipped:not([hidden])")
        page.click("#resume-skipped")
        page.wait_for_function(PROPOSED)
        assert page.inner_text("#prompt") == "Controlla i punti e conferma"
    finally:
        server.shutdown()
        server.server_close()


def test_rejected_image_restored_opens_with_its_proposal(app, new_page):
    propose_for(app, app.ids[0], app.ids[1])
    page = open_proposal_page(app, new_page)
    page.click("#reject")
    wait_until_left(page, app.ids[0])
    open_from_list(page, app.ids[0])
    page.wait_for_selector("#restore:not([hidden])")
    assert page.locator(".marker").count() == 0
    page.click("#restore")
    page.wait_for_function(PROPOSED)
    assert page.inner_text("#prompt") == "Controlla i punti e conferma"


def test_proposal_that_cannot_be_fetched_opens_for_clicking_by_hand(app, new_page):
    propose_for(app, app.ids[0])
    page = new_page()
    page.route("**/api/images/*/proposal", lambda route: route.abort())
    page.goto(app.url)
    page.wait_for_function("document.getElementById('prompt').textContent.startsWith('Punto 1')")
    assert "a mano" in page.inner_text("#message")
    page.wait_for_function(LOADED)
    click_photo(page, 0.5, 0.5)
    assert page.inner_text("#prompt").startswith("Punto 2")


def test_recomputed_proposal_is_used_when_its_image_opens(app, new_page):
    propose_for(app, app.ids[0], app.ids[1])
    page = open_proposal_page(app, new_page)
    moved = [{"name": name, "x": 0.1, "y": 0.1, "visible": True} for name in instrument.load().point_names]
    proposals.save(app.ids[1], moved, app.storage.proposals_dir)
    after_confirm_delay(page)
    page.keyboard.press("Enter")
    wait_until_left(page, app.ids[0])
    page.wait_for_function("document.querySelector('.marker')?.style.left === '10%'")


def test_dragging_a_point_moves_only_that_point(app, new_page):
    propose_for(app, app.ids[0])
    page = open_proposal_page(app, new_page)
    drag_marker(page, 1, 0.9, 0.1)
    points = confirm_and_read(page, app, app.ids[0])
    assert points[1]["x"] == pytest.approx(0.9, abs=0.02)
    assert points[1]["y"] == pytest.approx(0.1, abs=0.02)
    assert [point["x"] for point in (points[0], points[2], points[3])] == pytest.approx([0.2, 0.6, 0.8])


def test_point_dragged_beyond_the_image_stops_at_its_edge(app, new_page):
    propose_for(app, app.ids[0])
    page = open_proposal_page(app, new_page)
    drag_marker(page, 0, -0.5, 1.5)
    points = confirm_and_read(page, app, app.ids[0])
    assert (points[0]["x"], points[0]["y"]) == (0, 1)


def test_selecting_from_the_list_reaches_a_point_covered_by_others(app, new_page):
    overlapping = [{"name": name, "x": 0.5, "y": 0.5, "visible": True} for name in instrument.load().point_names]
    proposals.save(app.ids[0], overlapping, app.storage.proposals_dir)
    page = open_proposal_page(app, new_page)
    choose_point(page, 1)
    click_photo(page, 0.1, 0.2)
    points = confirm_and_read(page, app, app.ids[0])
    assert points[1]["x"] == pytest.approx(0.1, abs=0.01)
    assert points[0]["x"] == points[2]["x"] == points[3]["x"] == 0.5


def test_clicking_a_marker_selects_it_and_a_short_press_does_not_move_it(app, new_page):
    propose_for(app, app.ids[0])
    page = open_proposal_page(app, new_page)
    page.locator('.marker[data-index="2"]').click()
    assert page.locator("#points button").nth(2).get_attribute("aria-pressed") == "true"
    assert page.locator('.marker[data-index="2"]').get_attribute("style") == "left: 60%; top: 50%;"


def test_stray_click_with_no_point_selected_changes_nothing(app, new_page):
    propose_for(app, app.ids[0])
    page = open_proposal_page(app, new_page)
    click_photo(page, 0.9, 0.9)
    choose_point(page, 0)
    click_photo(page, 0.1, 0.1)
    click_photo(page, 0.9, 0.9)
    points = confirm_and_read(page, app, app.ids[0])
    assert points[0]["x"] == pytest.approx(0.1, abs=0.01)


def test_hidden_point_is_saved_without_position_and_can_come_back(app, new_page):
    propose_for(app, app.ids[0], app.ids[1])
    page = open_proposal_page(app, new_page)
    assert page.locator("#hide-point").is_disabled()
    choose_point(page, 0)
    page.click("#hide-point")
    assert page.locator(".marker").count() == 3
    assert "non visibile" in page.locator("#points button").nth(0).inner_text()
    choose_point(page, 1)
    page.click("#hide-point")
    choose_point(page, 1)
    click_photo(page, 0.3, 0.3)
    assert page.locator(".marker").count() == 3
    points = confirm_and_read(page, app, app.ids[0])
    assert points[0] == {"name": "bell_centre", "visible": False}
    assert points[1]["visible"] is True
    assert points[1]["x"] == pytest.approx(0.3, abs=0.01)


def test_all_points_hidden_cannot_be_confirmed_until_undone(app, new_page):
    propose_for(app, app.ids[0])
    page = open_proposal_page(app, new_page)
    for index in range(4):
        choose_point(page, index)
        page.click("#hide-point")
    assert page.inner_text("#prompt") == "Nessun punto visibile"
    assert "Non adatta" in page.inner_text("#message")
    after_confirm_delay(page)
    page.keyboard.press("Enter")
    page.wait_for_timeout(100)
    assert not (app.storage.annotations_dir / f"{app.ids[0]}.json").exists()

    page.click("#undo")
    assert page.inner_text("#prompt") == "Controlla i punti e conferma"
    assert page.inner_text("#message") == ""
    assert page.locator(".marker").count() == 1


def test_undo_reverts_one_change_at_a_time(app, new_page):
    propose_for(app, app.ids[0])
    page = open_proposal_page(app, new_page)
    page.click("#undo")
    assert page.locator(".marker").count() == 4
    drag_marker(page, 0, 0.9, 0.9)
    choose_point(page, 1)
    page.click("#hide-point")
    page.click("#undo")
    assert page.locator(".marker").count() == 4
    assert page.locator('.marker[data-index="0"]').get_attribute("style") != "left: 20%; top: 50%;"
    page.click("#undo")
    assert page.locator('.marker[data-index="0"]').get_attribute("style") == "left: 20%; top: 50%;"


def test_failed_save_keeps_moves_and_retry_sends_a_later_move(app, new_page):
    propose_for(app, app.ids[0])
    page = open_proposal_page(app, new_page)
    page.route(ANNOTATION_REQUESTS, lambda route: route.abort())
    drag_marker(page, 0, 0.9, 0.9)
    after_confirm_delay(page)
    page.keyboard.press("Enter")
    page.wait_for_selector("#retry:not([hidden])")
    assert page.locator('.marker[data-index="0"]').get_attribute("style") != "left: 20%; top: 50%;"

    page.unroute(ANNOTATION_REQUESTS)
    drag_marker(page, 1, 0.1, 0.1)
    assert page.locator("#retry").is_hidden()
    points = confirm_and_read(page, app, app.ids[0])
    assert points[0]["x"] == pytest.approx(0.9, abs=0.02)
    assert points[1]["x"] == pytest.approx(0.1, abs=0.02)


def test_retry_sends_the_points_shown_now(app, new_page):
    propose_for(app, app.ids[0])
    page = open_proposal_page(app, new_page)
    page.route(ANNOTATION_REQUESTS, lambda route: route.abort())
    drag_marker(page, 0, 0.9, 0.9)
    after_confirm_delay(page)
    page.keyboard.press("Enter")
    page.wait_for_selector("#retry:not([hidden])")
    page.unroute(ANNOTATION_REQUESTS)
    page.click("#retry")
    wait_until_left(page, app.ids[0])
    assert stored(app, app.ids[0])["points"][0]["x"] == pytest.approx(0.9, abs=0.02)


def test_reload_discards_moves_and_shows_the_proposal_again(app, new_page):
    propose_for(app, app.ids[0])
    page = open_proposal_page(app, new_page)
    drag_marker(page, 0, 0.9, 0.9)
    page.reload()
    page.wait_for_function(PROPOSED)
    assert page.locator('.marker[data-index="0"]').get_attribute("style") == "left: 20%; top: 50%;"


def test_selected_point_moves_when_the_click_lands_on_another_point(app, new_page):
    propose_for(app, app.ids[0])
    page = open_proposal_page(app, new_page)
    choose_point(page, 0)
    click_photo(page, 0.8, 0.5)
    points = confirm_and_read(page, app, app.ids[0])
    assert points[0]["x"] == pytest.approx(0.8, abs=0.01)
    assert points[3]["x"] == pytest.approx(0.8)


def test_selected_point_can_move_a_little_onto_its_own_position(app, new_page):
    propose_for(app, app.ids[0])
    page = open_proposal_page(app, new_page)
    choose_point(page, 0)
    click_photo(page, 0.205, 0.505)
    points = confirm_and_read(page, app, app.ids[0])
    assert points[0]["x"] == pytest.approx(0.205, abs=0.002)


def test_unreadable_image_leaves_the_pending_count(app, new_page):
    (app.storage.images_dir / f"{app.ids[0]}.jpg").write_bytes(b"not an image")
    page = new_page()
    page.goto(app.url)
    page.wait_for_function("document.querySelector('#list button[data-id=\"image-0\"]').textContent.startsWith('[!]')")
    assert f"Da fare: 0 con proposta, {len(app.ids) - 1} senza" in page.inner_text("#progress")


def test_reopened_image_rejected_in_another_tab_does_not_ask_to_move_points(page, app, new_page):
    first = annotate_current(page)
    other = new_page()
    other.goto(app.url)
    other.wait_for_function(LOADED)
    annotations.save(first, {"status": "rejected"}, app.storage.annotations_dir)
    open_from_list(other, first)
    other.wait_for_function("document.getElementById('prompt').textContent.startsWith('Punto 1')")
    assert "sposta i punti" not in other.inner_text("#message")



def test_number_keys_select_and_arrows_move_the_selected_point(app, new_page):
    propose_for(app, app.ids[0])
    page = open_proposal_page(app, new_page)
    width = page.locator("#photo").bounding_box()["width"]
    page.keyboard.press("2")
    assert page.locator("#points button").nth(1).get_attribute("aria-pressed") == "true"
    for _ in range(10):
        page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowDown")
    assert page.locator("#points button").nth(1).get_attribute("aria-pressed") == "true"
    points = confirm_and_read(page, app, app.ids[0])
    assert points[1]["x"] == pytest.approx(0.4 + 10 / width)
    assert points[1]["y"] > 0.5
    assert points[0]["x"] == pytest.approx(0.2)


def test_arrows_without_a_selected_point_change_nothing_and_stop_at_the_edge(app, new_page):
    edge = [{"name": name, "x": 1.0, "y": 0.5, "visible": True} for name in instrument.load().point_names]
    proposals.save(app.ids[0], edge, app.storage.proposals_dir)
    page = open_proposal_page(app, new_page)
    page.keyboard.press("ArrowLeft")
    page.keyboard.press("1")
    page.keyboard.press("ArrowRight")
    points = confirm_and_read(page, app, app.ids[0])
    assert points[0]["x"] == 1.0
    assert points[1]["x"] == 1.0


def test_backspace_hides_the_selected_point_and_annulla_brings_it_back(app, new_page):
    propose_for(app, app.ids[0])
    page = open_proposal_page(app, new_page)
    page.keyboard.press("Backspace")
    assert page.locator(".marker").count() == 4
    page.keyboard.press("3")
    page.keyboard.press("Backspace")
    assert page.locator(".marker").count() == 3
    page.click("#undo")
    assert page.locator(".marker").count() == 4
    page.keyboard.press("3")
    page.keyboard.press("Backspace")
    points = confirm_and_read(page, app, app.ids[0])
    assert points[2] == {"name": "bell_edge_right", "visible": False}


def test_keys_do_nothing_on_an_image_marked_by_hand(page, app):
    target = current(page)
    click_photo(page, 0.5, 0.5)
    for key in ("1", "ArrowRight", "Backspace"):
        page.keyboard.press(key)
    assert current(page) == target
    assert page.locator(".marker").count() == 1
    assert page.inner_text("#prompt").startswith("Punto 2")


def test_s_hides_and_shows_the_points_without_changing_them(app, new_page):
    propose_for(app, app.ids[0], app.ids[1])
    page = open_proposal_page(app, new_page)
    page.keyboard.press("s")
    assert not page.locator(".marker").first.is_visible()
    assert page.locator(".marker").count() == 4
    page.keyboard.press("s")
    assert page.locator(".marker").first.is_visible()
    page.keyboard.press("S")
    points = confirm_and_read(page, app, app.ids[0])
    assert [point["x"] for point in points] == pytest.approx([0.2, 0.4, 0.6, 0.8])
    assert all(point["visible"] for point in points)


def test_next_image_opens_with_its_points_showing(app, new_page):
    propose_for(app, app.ids[0], app.ids[1])
    page = open_proposal_page(app, new_page)
    page.keyboard.press("s")
    after_confirm_delay(page)
    page.keyboard.press("Enter")
    wait_until_left(page, app.ids[0])
    page.wait_for_function(PROPOSED)
    assert page.locator(".marker").first.is_visible()
