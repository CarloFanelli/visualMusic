"""Drives the live tracking page in real Chrome, with Chrome's fake camera and a scripted model."""
import base64
import math
import threading
import time
import wave
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
REFUSED_MICROPHONE = """const realGetUserMedia = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
navigator.mediaDevices.getUserMedia = async constraints => {
  if (constraints.audio) throw new DOMException("refused", "NotAllowedError");
  return realGetUserMedia(constraints);
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


def write_tone(path, hertz, amplitude=0.5, seconds=2, rate=48000, then_breath=False):
    """Chrome's fake microphone plays this file in a loop. Without a frequency it plays noise, like breath."""
    index = np.arange(seconds * rate)
    sound = np.sin(2 * np.pi * hertz * index / rate) if hertz else np.random.default_rng(1).uniform(-1, 1, index.size)
    if then_breath:
        sound = np.concatenate([sound, np.random.default_rng(1).uniform(-1, 1, index.size)])
    with wave.open(str(path), "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(rate)
        file.writeframes((amplitude * 32767 * sound).round().astype("<i2").tobytes())
    return path


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
def microphone_browser(playwright, tmp_path):
    """Returns a browser whose fake microphone plays a tone of the given frequency and loudness.

    Chrome's default fake microphone is not silent: it beeps loudly every so often.
    """
    browsers = []

    def start(hertz, amplitude=0.5, then_breath=False):
        tone = write_tone(tmp_path / f"tone-{hertz}-{amplitude}-{then_breath}.wav", hertz, amplitude, then_breath=then_breath)
        browsers.append(launch(playwright, TWO_FAKE_CAMERAS, "--use-fake-ui-for-media-stream", f"--use-file-for-fake-audio-capture={tone}"))
        return browsers[-1]

    yield start
    for running in browsers:
        running.close()


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


def chart_state(page):
    return page.evaluate("window.chartState")


def wait_for_dot(page):
    page.wait_for_function("window.chartState.dot !== null")
    return chart_state(page)["dot"]


def height_of(hertz):
    return math.log2(hertz / 80) / math.log2(1600 / 80)


def test_every_microphone_can_be_chosen(browser, server):
    context = browser.new_context()
    page = open_page(context, server)
    start_camera(page)
    page.get_by_role("button", name="Ferma").click()
    options = page.locator("#microphone-list option")
    expect(options).not_to_have_count(0)
    chosen = options.last.get_attribute("value")
    page.locator("#microphone-list").select_option(chosen)
    start_camera(page)
    page.wait_for_function("current && current.microphone")
    used = page.evaluate("current.microphone.getAudioTracks()[0].getSettings().deviceId")
    assert used == chosen
    context.close()


def test_the_microphone_is_heard_without_voice_processing(microphone_browser, server):
    page = open_page(microphone_browser(220), server)
    start_camera(page)
    page.wait_for_function("current && current.microphone")
    settings = page.evaluate("current.microphone.getAudioTracks()[0].getSettings()")
    assert not settings["echoCancellation"]
    assert not settings["noiseSuppression"]
    assert not settings["autoGainControl"]


def test_a_steady_tone_puts_the_dot_at_its_frequency(microphone_browser, server):
    page = open_page(microphone_browser(220), server)
    start_camera(page)
    dot = wait_for_dot(page)
    assert dot["y"] == pytest.approx(height_of(220), abs=math.log2(1.03) / math.log2(20))


def one_after_another(pages, measure):
    """The program tracks one page at a time, so each page is measured and stopped before the next."""
    results = []
    for page in pages:
        start_camera(page)
        results.append(measure(page))
        page.get_by_role("button", name="Ferma").click()
    return results


def test_a_louder_sound_moves_the_dot_right(microphone_browser, server):
    pages = [open_page(microphone_browser(220, amplitude=amplitude), server) for amplitude in (0.05, 0.8)]
    quiet, loud = one_after_another(pages, wait_for_dot)
    assert quiet["x"] < loud["x"] - 0.2


def test_a_frequency_above_the_chart_sits_on_its_top_edge(microphone_browser, server):
    page = open_page(microphone_browser(2000), server)
    start_camera(page)
    assert wait_for_dot(page)["y"] == 1


def test_silence_shows_no_dot(microphone_browser, server):
    page = open_page(microphone_browser(0, amplitude=0), server)
    start_camera(page)
    page.wait_for_function("current && current.microphone")
    expect(page.locator("#chart")).to_be_visible()
    page.wait_for_timeout(300)
    assert chart_state(page)["dot"] is None


def test_the_chart_sits_in_the_bottom_right_corner_at_the_same_size(microphone_browser, server):
    page = open_page(microphone_browser(220), server)
    start_camera(page)
    expect(page.locator("#chart")).to_be_visible()
    for size in [{"width": 1280, "height": 720}, {"width": 500, "height": 700}]:
        page.set_viewport_size(size)
        frame, chart = page.locator("#frame").bounding_box(), page.locator("#chart").bounding_box()
        assert (chart["width"], chart["height"]) == (160, 120)
        assert frame["x"] + frame["width"] - (chart["x"] + chart["width"]) == pytest.approx(8, abs=1)
        assert frame["y"] + frame["height"] - (chart["y"] + chart["height"]) == pytest.approx(8, abs=1)


def test_a_refused_microphone_keeps_tracking_and_explains(browser, server):
    page = open_page(browser, server, REFUSED_MICROPHONE)
    start_camera(page)
    expect(page.locator("#message")).to_contain_text("permesso per il microfono")
    expect(page.locator("#chart")).to_be_hidden()
    before = page.evaluate("window.frameTimes.length")
    page.wait_for_function(f"window.frameTimes.length > {before}")


def test_no_microphone_disables_the_choice_and_the_camera_still_works(browser, server):
    cameras_only = """const realEnumerate = navigator.mediaDevices.enumerateDevices.bind(navigator.mediaDevices);
    navigator.mediaDevices.enumerateDevices = async () => (await realEnumerate()).filter(device => device.kind !== "audioinput");"""
    page = open_page(browser, server, cameras_only)
    expect(page.locator("#microphone-list")).to_be_disabled()
    expect(page.locator("#microphone-note")).to_contain_text("Nessun microfono")
    start_camera(page)
    expect(page.locator("#chart")).to_be_hidden()


def test_a_microphone_that_stops_keeps_tracking_and_says_so(browser, server):
    page = open_page(browser, server)
    errors = []
    page.on("pageerror", lambda error: errors.append(error))
    start_camera(page)
    page.wait_for_function("current && current.microphone")
    page.evaluate("""(() => {
      const track = current.microphone.getAudioTracks()[0];
      track.stop();
      track.dispatchEvent(new Event('ended'));
    })()""")
    expect(page.locator("#message")).to_contain_text("microfono si è fermato")
    expect(page.locator("#chart")).to_be_hidden()
    expect(page.locator("#tracking")).to_be_visible()
    page.wait_for_timeout(200)
    assert errors == []


def test_stop_turns_the_microphone_off(browser, server):
    page = open_page(browser, server)
    start_camera(page)
    page.wait_for_function("current && current.microphone")
    page.evaluate("window.heldMicrophone = current.microphone")
    page.get_by_role("button", name="Ferma").click()
    assert page.evaluate("window.heldMicrophone.getTracks().every(track => track.readyState === 'ended')")


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
    chooser.value.set_files(path if isinstance(path, dict) else str(path))


RECORD_VIDEO = """async hertz => {
  const canvas = Object.assign(document.createElement('canvas'), { width: 160, height: 120 });
  const paint = canvas.getContext('2d');
  const stream = canvas.captureStream(30);
  const context = new AudioContext();
  await context.resume();
  if (hertz) {
    const tone = context.createOscillator();
    const output = context.createMediaStreamDestination();
    tone.frequency.value = hertz;
    tone.connect(output);
    tone.start();
    stream.addTrack(output.stream.getAudioTracks()[0]);
  }
  const recorder = new MediaRecorder(stream, { mimeType: hertz ? 'video/webm;codecs=vp8,opus' : 'video/webm;codecs=vp8' });
  const parts = [];
  recorder.ondataavailable = event => parts.push(event.data);
  recorder.start();
  for (let step = 0; step < 90; step++) {
    paint.fillStyle = `rgb(${step * 2}, 80, 80)`;
    paint.fillRect(0, 0, 160, 120);
    await new Promise(resolve => setTimeout(resolve, 33));
  }
  recorder.stop();
  await new Promise(resolve => { recorder.onstop = resolve; });
  const bytes = new Uint8Array(await new Blob(parts).arrayBuffer());
  let text = '';
  for (const byte of bytes) text += String.fromCharCode(byte);
  return btoa(text);
}"""


def recorded_video(page, hertz):
    """A short video recorded by Chrome itself, since no tool here can add sound to a video."""
    return {"name": "clip.webm", "mimeType": "video/webm", "buffer": base64.b64decode(page.evaluate(RECORD_VIDEO, hertz))}


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


def test_a_video_with_sound_is_heard_and_drives_the_chart(browser, server):
    page = open_page(browser, server)
    clip = recorded_video(page, 330)
    start_video(page, clip)
    assert page.evaluate("document.getElementById('view').muted") is False
    dot = wait_for_dot(page)
    assert dot["y"] == pytest.approx(height_of(330), abs=math.log2(1.03) / math.log2(20))


def test_a_video_chosen_again_still_drives_the_chart(browser, server):
    page = open_page(browser, server)
    clip = recorded_video(page, 330)
    start_video(page, clip)
    wait_for_dot(page)
    page.get_by_role("button", name="Ferma").click()
    start_video(page, clip)
    wait_for_dot(page)
    expect(page.locator("#message")).to_be_empty()


def test_a_video_without_sound_says_so_and_keeps_tracking(browser, server):
    page = open_page(browser, server)
    start_video(page, recorded_video(page, 0))
    expect(page.locator("#message")).to_contain_text("non ha audio")
    expect(page.locator("#chart")).to_be_hidden()


def test_a_paused_video_shows_no_dot_and_its_trail_fades(browser, server):
    page = open_page(browser, server)
    start_video(page, recorded_video(page, 330))
    wait_for_dot(page)
    page.get_by_role("button", name="Pausa").click()
    page.wait_for_function("window.chartState.dot === null")
    page.wait_for_timeout(2100)
    assert chart_state(page)["trail"] == []


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


def glow_state(page):
    return page.evaluate("""(() => {
      const glow = document.getElementById('glow');
      return { left: parseFloat(glow.style.left), top: parseFloat(glow.style.top), width: parseFloat(glow.style.width),
               opacity: parseFloat(glow.style.opacity), shown: parseFloat(getComputedStyle(glow).opacity),
               colour: glow.style.getPropertyValue('--glow-color') };
    })()""")


def glowing(page):
    page.wait_for_function("parseFloat(document.getElementById('glow').style.opacity) > 0")
    return glow_state(page)


def hue_of(colour):
    return float(colour.removeprefix("hsl(").split()[0])


def test_the_glow_sits_on_the_mirrored_sound_point(microphone_browser, server):
    page = open_page(microphone_browser(220), server)
    start_camera(page)
    glow = glowing(page)
    assert (glow["left"], glow["top"]) == pytest.approx((80, 25), abs=0.01)


def test_a_louder_sound_gives_a_larger_brighter_glow(microphone_browser, server):
    pages = [open_page(microphone_browser(220, amplitude=amplitude), server) for amplitude in (0.05, 0.8)]
    small, large = one_after_another(pages, glowing)
    assert small["width"] < large["width"]
    assert small["opacity"] < large["opacity"]


def test_the_glow_lights_up_at_once_when_a_note_starts(microphone_browser, server):
    page = open_page(microphone_browser(220), server)
    start_camera(page)
    target, shown = page.wait_for_function("""(() => {
      const glow = document.getElementById('glow');
      const target = parseFloat(glow.style.opacity);
      return target > 0 && [target, parseFloat(getComputedStyle(glow).opacity)];
    })()""").json_value()
    assert shown == pytest.approx(target, abs=0.05)


def test_silence_gives_no_glow(microphone_browser, server):
    page = open_page(microphone_browser(0, amplitude=0), server)
    start_camera(page)
    page.wait_for_function("current && current.microphone")
    page.wait_for_timeout(500)
    assert glow_state(page)["shown"] == 0


@pytest.mark.parametrize(("hertz", "hue"), [(80, 20), (1600, 230), (60, 20), (2000, 230)])
def test_the_colour_goes_from_warm_low_to_cold_high(microphone_browser, server, hertz, hue):
    page = open_page(microphone_browser(hertz), server)
    start_camera(page)
    page.wait_for_function("document.getElementById('glow').style.getPropertyValue('--glow-color').startsWith('hsl')")
    assert hue_of(glow_state(page)["colour"]) == pytest.approx(hue, abs=5)


def test_breath_without_a_frequency_gives_a_white_glow(microphone_browser, server):
    page = open_page(microphone_browser(0, amplitude=0.3), server)
    start_camera(page)
    assert glowing(page)["colour"] == "#fff"


def test_breath_after_a_note_keeps_its_colour_briefly_then_turns_white(microphone_browser, server):
    page = open_page(microphone_browser(220, then_breath=True), server)
    start_camera(page)
    page.wait_for_function("document.getElementById('glow').style.getPropertyValue('--glow-color').startsWith('hsl')")
    page.wait_for_function("document.getElementById('glow').style.getPropertyValue('--glow-color') === '#fff'", timeout=5000)


def test_the_glow_fades_out_when_the_sound_point_goes(microphone_browser, server):
    model = server.RequestHandlerClass.model
    page = open_page(microphone_browser(220), server)
    start_camera(page)
    glowing(page)
    model.confidences = [0.1, 0.1, 0.1, 0.9]
    expect(page.locator("#sound-point")).to_be_hidden()
    page.wait_for_timeout(350)
    assert glow_state(page)["shown"] == 0


def test_the_glow_glides_when_the_sound_point_jumps(browser, server):
    page = open_page(browser, server)
    transition = page.locator("#glow").evaluate("element => getComputedStyle(element).transitionProperty")
    assert "left" in transition and "top" in transition


def test_points_can_be_hidden_while_the_glow_stays(microphone_browser, server):
    page = open_page(microphone_browser(220), server)
    start_camera(page)
    page.get_by_role("button", name="Nascondi punti").click()
    expect(page.locator(".marker").first).to_be_hidden()
    expect(page.locator("#sound-point")).to_be_hidden()
    assert glowing(page)["opacity"] > 0
    page.get_by_role("button", name="Mostra punti").click()
    expect(page.locator(".marker").first).to_be_visible()


def test_points_are_shown_again_at_each_new_start(browser, server):
    page = open_page(browser, server)
    start_camera(page)
    page.get_by_role("button", name="Nascondi punti").click()
    page.get_by_role("button", name="Ferma").click()
    start_camera(page)
    expect(page.locator(".marker").first).to_be_visible()
    expect(page.get_by_role("button", name="Nascondi punti")).to_be_visible()


def test_a_refused_microphone_gives_no_glow(browser, server):
    page = open_page(browser, server, REFUSED_MICROPHONE)
    start_camera(page)
    expect(page.locator("#message")).to_contain_text("microfono")
    assert glow_state(page)["shown"] == 0
