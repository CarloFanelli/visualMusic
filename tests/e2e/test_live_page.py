"""Drives the live tracking page in real Chrome, with Chrome's fake camera and a scripted model."""
import threading
import time
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import cv2
import numpy as np
import pytest
import torch

sync_api = pytest.importorskip("playwright.sync_api")

from dataset_tools import instrument as instrument_module  # noqa: E402
from live_tracking import server as server_module  # noqa: E402

expect = sync_api.expect
SAX = instrument_module.load()
FRAMES = "**/api/frames*"
TWO_FAKE_CAMERAS = "--use-fake-device-for-media-stream=device-count=2"
NO_CAMERA = "navigator.mediaDevices.enumerateDevices = async () => [];"
REFUSED = """navigator.mediaDevices.getUserMedia = async () => {
  throw new DOMException("refused", "NotAllowedError");
};"""


class ScriptedModel:
    def __init__(self):
        self.model = SimpleNamespace(kpt_shape=[len(SAX.point_names), 3])
        self.positions = [(0.2, 0.25), (0.4, 0.5), (0.6, 0.5), (0.7, 0.8)]
        self.confidences = [0.9, 0.9, 0.9, 0.9]
        self.detected = True
        self.delay = 0

    def predict(self, image, **arguments):
        time.sleep(self.delay)
        if not self.detected:
            return [SimpleNamespace(boxes=SimpleNamespace(conf=torch.tensor([])), keypoints=None)]
        return [
            SimpleNamespace(
                boxes=SimpleNamespace(conf=torch.tensor([0.9])),
                keypoints=SimpleNamespace(xyn=torch.tensor([self.positions]), conf=torch.tensor([self.confidences])),
            )
        ]


@pytest.fixture(scope="module")
def playwright():
    with sync_api.sync_playwright() as running:
        yield running


def launch(playwright, *arguments):
    try:
        return playwright.chromium.launch(channel="chrome", headless=True, args=list(arguments))
    except sync_api.Error as error:
        pytest.skip(f"Chrome is not available: {error}")


@pytest.fixture(scope="module")
def browser(playwright):
    chrome = launch(playwright, TWO_FAKE_CAMERAS, "--use-fake-ui-for-media-stream")
    yield chrome
    chrome.close()


@pytest.fixture
def server():
    running = server_module.create_server(SAX, ScriptedModel(), "cpu", port=0)
    threading.Thread(target=running.serve_forever, daemon=True).start()
    yield running
    running.shutdown()
    running.server_close()


def open_page(context, server, init_script=None):
    page = context.new_page()
    if init_script:
        page.add_init_script(init_script)
    page.goto(f"http://127.0.0.1:{server.server_address[1]}/")
    return page


def marker_position(page, index=0):
    return page.locator(".marker").nth(index).evaluate("element => [parseFloat(element.style.left), parseFloat(element.style.top)]")


def marker_centre(page):
    """Read in one step, because markers are replaced at every update."""
    return page.evaluate("""() => {
      const box = document.querySelector('.marker').getBoundingClientRect();
      return [box.x + box.width / 2, box.y + box.height / 2];
    }""")


def camera_is_live(page):
    return page.evaluate("() => { const s = document.getElementById('view').srcObject; return !!s && s.getTracks().some(t => t.readyState === 'live'); }")


def start_camera(page):
    page.get_by_role("button", name="Webcam").click()
    expect(page.locator(".marker")).to_have_count(4)


def test_page_offers_a_camera_and_a_video_file(browser, server):
    page = open_page(browser, server)
    expect(page.get_by_role("heading")).to_have_text("Scegli la sorgente")
    expect(page.get_by_role("button", name="Webcam")).to_be_enabled()
    expect(page.get_by_role("button", name="Video registrato")).to_be_visible()
    expect(page.locator("#message")).to_be_empty()


def test_stopping_the_program_shows_how_to_restart_it(browser, server):
    page = open_page(browser, server)
    server.shutdown()
    server.server_close()
    expect(page.locator("#message")).to_contain_text("python -m live_tracking.server", timeout=10000)


def test_every_camera_can_be_chosen(browser, server):
    context = browser.new_context()
    page = open_page(context, server)
    expect(page.locator("#camera-list option")).to_have_count(2)
    second = page.locator("#camera-list option").nth(1).get_attribute("value")
    page.locator("#camera-list").select_option(second)
    start_camera(page)
    used = page.evaluate("document.getElementById('view').srcObject.getVideoTracks()[0].getSettings().deviceId")
    assert used == second
    context.close()


def test_points_are_drawn_mirrored_on_a_mirrored_image(browser, server):
    page = open_page(browser, server)
    start_camera(page)
    assert marker_position(page) == pytest.approx([80, 25], abs=0.01)
    assert "matrix(-1" in page.locator("#view").evaluate("element => getComputedStyle(element).transform")


def test_points_stay_aligned_and_the_image_is_not_stretched_after_resizing(browser, server):
    page = open_page(browser, server)
    start_camera(page)
    ratio = page.evaluate("(() => { const v = document.getElementById('view'); return v.videoWidth / v.videoHeight; })()")
    page.set_viewport_size({"width": 500, "height": 700})
    box = page.locator("#frame").bounding_box()
    assert box["width"] / box["height"] == pytest.approx(ratio, abs=0.02)
    assert box["x"] >= 0 and box["x"] + box["width"] <= 500
    assert marker_centre(page) == pytest.approx([box["x"] + 0.8 * box["width"], box["y"] + 0.25 * box["height"]], abs=2)


def test_an_uncertain_point_is_not_drawn(browser, server):
    server.RequestHandlerClass.model.confidences = [0.9, 0.2, 0.5, 0.9]
    page = open_page(browser, server)
    page.get_by_role("button", name="Webcam").click()
    expect(page.locator(".marker")).to_have_count(3)


def test_sound_point_is_highlighted_on_the_mirrored_bell_centre(browser, server):
    page = open_page(browser, server)
    start_camera(page)
    expect(page.locator("#sound-point")).to_be_visible()
    position = page.locator("#sound-point").evaluate("element => [parseFloat(element.style.left), parseFloat(element.style.top)]")
    assert position == pytest.approx([80, 25], abs=0.01)


def test_sound_point_disappears_with_only_one_bell_edge(browser, server):
    model = server.RequestHandlerClass.model
    page = open_page(browser, server)
    start_camera(page)
    model.confidences = [0.1, 0.9, 0.1, 0.9]
    expect(page.locator("#sound-point")).to_be_hidden()
    expect(page.locator(".marker")).to_have_count(2)


def test_message_appears_when_the_saxophone_is_lost_and_goes_when_it_returns(browser, server):
    model = server.RequestHandlerClass.model
    page = open_page(browser, server)
    start_camera(page)
    expect(page.locator("#not-found")).to_be_hidden()
    model.detected = False
    expect(page.locator("#not-found")).to_have_text("sax non trovato")
    expect(page.locator(".marker")).to_have_count(0)
    model.detected = True
    expect(page.locator("#not-found")).to_be_hidden()
    expect(page.locator(".marker")).to_have_count(4)


def test_stop_clears_the_sound_point_and_the_message(browser, server):
    server.RequestHandlerClass.model.detected = False
    page = open_page(browser, server)
    page.get_by_role("button", name="Webcam").click()
    expect(page.locator("#not-found")).to_be_visible()
    page.get_by_role("button", name="Ferma").click()
    page.get_by_role("button", name="Webcam").click()
    expect(page.locator("#not-found")).to_be_hidden()


def test_stop_turns_the_camera_off_and_returns_to_the_choice(browser, server):
    page = open_page(browser, server)
    start_camera(page)
    assert camera_is_live(page)
    page.get_by_role("button", name="Ferma").click()
    expect(page.get_by_role("heading")).to_be_visible()
    expect(page.locator("#tracking")).to_be_hidden()
    assert not camera_is_live(page)


def test_a_double_click_on_the_camera_starts_once_with_no_message(browser, server):
    page = open_page(browser, server)
    expect(page.get_by_role("button", name="Webcam")).to_be_enabled()
    page.evaluate("(() => { const camera = document.getElementById('camera'); camera.click(); camera.click(); })()")
    expect(page.locator(".marker")).to_have_count(4)
    expect(page.locator("#message")).to_be_empty()


def test_a_model_failure_says_the_analysis_failed(browser, server):
    def failing(image, **arguments):
        raise RuntimeError("out of memory")

    server.RequestHandlerClass.model.predict = failing
    page = open_page(browser, server)
    page.get_by_role("button", name="Webcam").click()
    expect(page.locator("#sources")).to_be_visible()
    expect(page.locator("#message")).to_contain_text("analizzare")
    page.wait_for_timeout(2500)
    expect(page.locator("#message")).to_contain_text("analizzare")


def test_a_camera_that_cannot_play_blames_the_camera(browser, server):
    cannot_play = 'HTMLMediaElement.prototype.play = () => Promise.reject(new DOMException("no", "AbortError"));'
    page = open_page(browser, server, cannot_play)
    page.get_by_role("button", name="Webcam").click()
    expect(page.locator("#sources")).to_be_visible()
    expect(page.locator("#message")).to_contain_text("usare la webcam")


def test_stop_pressed_twice_is_handled_once(browser, server):
    page = open_page(browser, server)
    start_camera(page)
    page.evaluate("(() => { const stop = document.getElementById('stop'); stop.click(); stop.click(); })()")
    expect(page.locator("#sources")).to_be_visible()
    expect(page.locator("#message")).to_be_empty()
    assert not camera_is_live(page)
    start_camera(page)


def test_stop_while_still_starting_leaves_the_camera_off(browser, server):
    slow = """const realGetUserMedia = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    window.grantedStreams = [];
    navigator.mediaDevices.getUserMedia = async constraints => {
      await new Promise(resolve => setTimeout(resolve, 300));
      const stream = await realGetUserMedia(constraints);
      window.grantedStreams.push(stream);
      return stream;
    };"""
    page = open_page(browser, server, slow)
    page.get_by_role("button", name="Webcam").click()
    page.get_by_role("button", name="Ferma").click()
    expect(page.locator("#sources")).to_be_visible()
    page.wait_for_function("window.grantedStreams.length === 1")
    page.wait_for_function("window.grantedStreams[0].getTracks().every(t => t.readyState === 'ended')")


def test_a_reply_arriving_after_stop_draws_nothing(browser, server):
    page = open_page(browser, server)
    held = []
    page.route(FRAMES, lambda route: held.append(route))
    page.get_by_role("button", name="Webcam").click()
    page.wait_for_timeout(500)
    assert held
    page.get_by_role("button", name="Ferma").click()
    held[0].continue_()
    page.wait_for_timeout(300)
    expect(page.locator(".marker")).to_have_count(0)


def test_a_second_tab_says_tracking_is_open_elsewhere_and_the_first_continues(browser, server):
    context = browser.new_context()
    first = open_page(context, server)
    start_camera(first)
    second = open_page(context, server)
    expect(second.locator("#message")).to_contain_text("altra scheda")
    second.get_by_role("button", name="Webcam").click()
    expect(second.locator("#sources")).to_be_visible()
    expect(second.locator("#message")).to_contain_text("altra scheda")
    assert not camera_is_live(second)
    before = first.evaluate("window.frameTimes.length")
    first.wait_for_function(f"window.frameTimes.length > {before} || window.frameTimes.length >= 300")
    context.close()


def test_closing_the_tab_leaves_the_program_ready_for_a_new_start(browser, server):
    context = browser.new_context()
    first = open_page(context, server)
    start_camera(first)
    first.close()
    second = open_page(context, server)
    start_camera(second)
    expect(second.locator("#message")).to_be_empty()
    context.close()


def test_tracking_from_another_browser_stops_the_first_with_a_message(browser, server):
    first_context = browser.new_context()
    second_context = browser.new_context()
    first = open_page(first_context, server)
    start_camera(first)
    start_camera(open_page(second_context, server))
    expect(first.locator("#sources")).to_be_visible()
    expect(first.locator("#message")).to_contain_text("altra scheda")
    assert not camera_is_live(first)
    first_context.close()
    second_context.close()


def test_no_camera_disables_the_choice_and_explains(browser, server):
    page = open_page(browser, server, NO_CAMERA)
    expect(page.get_by_role("button", name="Webcam")).to_be_disabled()
    expect(page.locator("#camera-note")).to_contain_text("Nessuna webcam")


def test_first_use_works_before_chrome_reveals_the_camera_identifiers(browser, server):
    hidden_until_allowed = """const realEnumerate = navigator.mediaDevices.enumerateDevices.bind(navigator.mediaDevices);
    let allowed = false;
    const realGetUserMedia = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    navigator.mediaDevices.getUserMedia = async constraints => {
      const stream = await realGetUserMedia(constraints);
      allowed = true;
      return stream;
    };
    navigator.mediaDevices.enumerateDevices = async () => allowed
      ? realEnumerate()
      : [{ kind: "videoinput", deviceId: "", label: "" }];"""
    page = open_page(browser, server, hidden_until_allowed)
    expect(page.locator("#camera-list option")).to_have_count(1)
    start_camera(page)
    expect(page.locator("#camera-list option")).to_have_count(2)


def test_refused_permission_explains_how_to_grant_it(browser, server):
    page = open_page(browser, server, REFUSED)
    page.get_by_role("button", name="Webcam").click()
    expect(page.locator("#sources")).to_be_visible()
    expect(page.locator("#message")).to_contain_text("permesso")


def test_a_camera_that_stops_during_tracking_returns_to_the_choice(browser, server):
    page = open_page(browser, server)
    start_camera(page)
    page.evaluate("""(() => {
      const track = document.getElementById('view').srcObject.getVideoTracks()[0];
      track.stop();
      track.dispatchEvent(new Event('ended'));
    })()""")
    expect(page.locator("#sources")).to_be_visible()
    expect(page.locator("#message")).to_contain_text("webcam")


def test_stopping_the_program_during_tracking_shows_how_to_restart_it(browser, server):
    page = open_page(browser, server)
    start_camera(page)
    server.shutdown()
    server.server_close()
    expect(page.locator("#sources")).to_be_visible(timeout=10000)
    expect(page.locator("#message")).to_contain_text("python -m live_tracking.server")
    assert not camera_is_live(page)


def write_video(path, width=320, height=240, seconds=3, rate=30):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"avc1"), rate, (width, height))
    assert writer.isOpened()
    for number in range(seconds * rate):
        writer.write(np.full((height, width, 3), number % 255, np.uint8))
    writer.release()
    return path


def choose_file(page, path):
    with page.expect_file_chooser() as chooser:
        page.get_by_role("button", name="Video registrato").click()
    chooser.value.set_files(str(path))


def start_video(page, path):
    choose_file(page, path)
    expect(page.locator(".marker")).to_have_count(4)


@pytest.fixture
def video(tmp_path):
    return write_video(tmp_path / "clip.mp4")


def current_time(page):
    return page.evaluate("document.getElementById('view').currentTime")


def test_a_video_plays_with_points_that_are_not_mirrored(browser, server, video):
    page = open_page(browser, server)
    start_video(page, video)
    assert marker_position(page) == pytest.approx([20, 25], abs=0.01)
    assert page.locator("#view").evaluate("element => getComputedStyle(element).transform") == "none"
    expect(page.get_by_role("button", name="Pausa")).to_be_visible()
    expect(page.get_by_role("button", name="Ricomincia")).to_be_visible()


def test_the_camera_shows_no_video_controls_and_stays_mirrored_after_a_video(browser, server, video):
    page = open_page(browser, server)
    start_video(page, video)
    page.get_by_role("button", name="Ferma").click()
    start_camera(page)
    assert marker_position(page) == pytest.approx([80, 25], abs=0.01)
    expect(page.get_by_role("button", name="Pausa")).to_be_hidden()
    expect(page.get_by_role("button", name="Ricomincia")).to_be_hidden()


def test_a_vertical_video_keeps_its_proportions_and_aligned_points(browser, server, tmp_path):
    page = open_page(browser, server)
    start_video(page, write_video(tmp_path / "vertical.mp4", width=240, height=320))
    box = page.locator("#frame").bounding_box()
    assert box["width"] / box["height"] == pytest.approx(0.75, abs=0.02)
    assert marker_centre(page)[0] == pytest.approx(box["x"] + 0.2 * box["width"], abs=2)


def test_no_file_chosen_changes_nothing(browser, server):
    page = open_page(browser, server)
    with page.expect_file_chooser() as chooser:
        page.get_by_role("button", name="Video registrato").click()
    chooser.value.set_files([])
    page.wait_for_timeout(200)
    expect(page.locator("#sources")).to_be_visible()
    expect(page.locator("#message")).to_be_empty()


def test_a_file_that_is_not_a_video_returns_to_the_choice(browser, server, tmp_path):
    bad = tmp_path / "notes.mp4"
    bad.write_text("this is not a video")
    page = open_page(browser, server)
    choose_file(page, bad)
    expect(page.locator("#sources")).to_be_visible()
    expect(page.locator("#message")).to_contain_text("non riesco a leggere")


def test_the_video_keeps_normal_speed_when_analysis_is_slower(browser, server, tmp_path):
    server.RequestHandlerClass.model.delay = 0.25
    page = open_page(browser, server)
    start_video(page, write_video(tmp_path / "long.mp4", seconds=6))
    start_time, started = current_time(page), time.monotonic()
    page.wait_for_timeout(2000)
    assert current_time(page) - start_time == pytest.approx(time.monotonic() - started, abs=0.4)
    assert page.evaluate("window.frameTimes.length") < 20


def test_pause_freezes_image_and_points(browser, server, video):
    model = server.RequestHandlerClass.model
    page = open_page(browser, server)
    start_video(page, video)
    page.get_by_role("button", name="Pausa").click()
    expect(page.get_by_role("button", name="Riprendi")).to_be_visible()
    page.wait_for_timeout(200)
    frozen_at = current_time(page)
    updates = page.evaluate("window.frameTimes.length")
    model.detected = False
    page.wait_for_timeout(500)
    assert current_time(page) == frozen_at
    assert page.evaluate("window.frameTimes.length") == updates
    expect(page.locator(".marker")).to_have_count(4)


def test_time_stands_still_during_a_pause(browser, server, tmp_path):
    page = open_page(browser, server)
    start_video(page, write_video(tmp_path / "long.mp4", seconds=6))
    page.get_by_role("button", name="Pausa").click()
    expect(page.get_by_role("button", name="Riprendi")).to_be_visible()
    page.wait_for_timeout(100)
    frozen_at = current_time(page)
    page.wait_for_timeout(600)
    with page.expect_request(FRAMES) as frame:
        page.get_by_role("button", name="Riprendi").click()
    sent = float(parse_qs(urlsplit(frame.value.url).query)["time"][0])
    assert sent == pytest.approx(frozen_at, abs=0.3)


def test_resuming_continues_from_the_same_point(browser, server, tmp_path):
    page = open_page(browser, server)
    start_video(page, write_video(tmp_path / "long.mp4", seconds=6))
    page.get_by_role("button", name="Pausa").click()
    page.wait_for_timeout(100)
    frozen_at = current_time(page)
    page.get_by_role("button", name="Riprendi").click()
    page.wait_for_function(f"document.getElementById('view').currentTime > {frozen_at}")
    assert not page.evaluate("document.getElementById('view').paused")


def test_restart_goes_back_without_carrying_points_over(browser, server, tmp_path):
    model = server.RequestHandlerClass.model
    page = open_page(browser, server)
    start_video(page, write_video(tmp_path / "long.mp4", seconds=6))
    page.wait_for_timeout(1000)
    model.confidences = [0.1, 0.1, 0.1, 0.9]
    page.get_by_role("button", name="Ricomincia").click()
    expect(page.locator(".marker")).to_have_count(1)
    assert current_time(page) < 1
    expect(page.locator("#tracking")).to_be_visible()
    expect(page.locator("#message")).to_be_empty()


def test_a_reply_from_before_a_restart_does_not_stop_tracking(browser, server, tmp_path):
    page = open_page(browser, server)
    start_video(page, write_video(tmp_path / "long.mp4", seconds=6))
    held = []
    page.route(FRAMES, lambda route: held.append(route) if not held else route.continue_())
    page.wait_for_timeout(300)
    assert held
    page.get_by_role("button", name="Ricomincia").click()
    page.wait_for_timeout(300)
    held[0].continue_()
    updates = page.evaluate("window.frameTimes.length")
    page.wait_for_function(f"window.frameTimes.length > {updates}")
    expect(page.locator("#tracking")).to_be_visible()
    expect(page.locator("#message")).to_be_empty()


def test_when_the_video_ends_the_last_image_stays_and_restart_works(browser, server, tmp_path):
    page = open_page(browser, server)
    start_video(page, write_video(tmp_path / "short.mp4", seconds=1))
    page.wait_for_function("document.getElementById('view').ended")
    expect(page.locator("#tracking")).to_be_visible()
    expect(page.get_by_role("button", name="Pausa")).to_be_disabled()
    updates = page.evaluate("window.frameTimes.length")
    page.get_by_role("button", name="Ricomincia").click()
    page.wait_for_function(f"window.frameTimes.length > {updates}")
    expect(page.get_by_role("button", name="Pausa")).to_be_enabled()
    assert not page.evaluate("document.getElementById('view').ended")


def test_a_failure_partway_keeps_the_last_image_and_offers_restart(browser, server, tmp_path):
    page = open_page(browser, server)
    start_video(page, write_video(tmp_path / "long.mp4", seconds=6))
    page.evaluate("document.getElementById('view').dispatchEvent(new Event('error'))")
    expect(page.locator("#message")).to_contain_text("danneggiato")
    expect(page.locator("#tracking")).to_be_visible()
    expect(page.get_by_role("button", name="Ricomincia")).to_be_enabled()
    expect(page.get_by_role("button", name="Pausa")).to_be_disabled()


def test_a_message_does_not_crop_the_image(browser, server, tmp_path):
    page = open_page(browser, server)
    start_video(page, write_video(tmp_path / "long.mp4", seconds=6))
    page.evaluate("document.getElementById('view').dispatchEvent(new Event('error'))")
    expect(page.locator("#message")).to_contain_text("danneggiato")
    frame, stage = page.locator("#frame").bounding_box(), page.locator("#stage").bounding_box()
    assert frame["y"] >= stage["y"]
    assert frame["y"] + frame["height"] <= stage["y"] + stage["height"]


def test_a_restart_stopped_midway_leaves_the_next_video_alone(browser, server, tmp_path):
    clip = write_video(tmp_path / "long.mp4", seconds=6)
    page = open_page(browser, server)
    start_video(page, clip)
    held = []
    page.route("**/api/sessions", lambda route: held.append((route, route.fetch())) if not held else route.continue_())
    page.get_by_role("button", name="Ricomincia").click()
    page.wait_for_timeout(300)
    assert held
    page.get_by_role("button", name="Ferma").click()
    start_video(page, clip)
    page.wait_for_function("document.getElementById('view').currentTime > 1")
    route, reply = held[0]
    route.fulfill(response=reply)
    page.wait_for_timeout(300)
    assert current_time(page) > 1


def test_stopping_a_video_releases_it_and_returns_to_the_choice(browser, server, video):
    page = open_page(browser, server)
    start_video(page, video)
    page.get_by_role("button", name="Ferma").click()
    expect(page.locator("#sources")).to_be_visible()
    assert page.evaluate("(() => { const v = document.getElementById('view'); return !v.hasAttribute('src') && v.readyState === 0; })()")


def test_the_same_video_can_be_chosen_again(browser, server, video):
    page = open_page(browser, server)
    start_video(page, video)
    page.get_by_role("button", name="Ferma").click()
    start_video(page, video)


def test_a_second_tab_cannot_start_a_video_while_tracking_runs(browser, server, video):
    context = browser.new_context()
    first = open_page(context, server)
    start_camera(first)
    second = open_page(context, server)
    choose_file(second, video)
    expect(second.locator("#sources")).to_be_visible()
    expect(second.locator("#message")).to_contain_text("altra scheda")
    context.close()
