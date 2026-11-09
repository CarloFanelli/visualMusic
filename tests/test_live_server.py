import contextlib
import http.client
import io
import socket
import struct
import threading
from types import SimpleNamespace

import pytest
import requests
import torch
from PIL import Image

from dataset_tools import instrument as instrument_module
from dataset_tools import paths
from live_tracking import server as server_module

SAX = instrument_module.load()
POSITIONS = [[(0.1, 0.2), (0.3, 0.4), (0.5, 0.6), (0.7, 0.8)]]


class FakeModel:
    points = len(SAX.point_names)

    def __init__(self, source):
        self.model = SimpleNamespace(kpt_shape=[FakeModel.points, 3])
        self.seen = []

    def predict(self, image, **arguments):
        self.seen.append(image.shape)
        return [
            SimpleNamespace(
                boxes=SimpleNamespace(conf=torch.tensor([0.9])),
                keypoints=SimpleNamespace(xyn=torch.tensor(POSITIONS), conf=torch.tensor([[0.9, 0.9, 0.2, 0.9]])),
            )
        ]


def jpeg():
    buffer = io.BytesIO()
    Image.new("RGB", (64, 48), "white").save(buffer, "JPEG")
    return buffer.getvalue()


@pytest.fixture
def app():
    server = server_module.create_server(SAX, FakeModel("model"), "cpu", port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    server.base_url = f"http://127.0.0.1:{server.server_address[1]}"
    yield server
    server.shutdown()
    server.server_close()


@pytest.fixture
def start(monkeypatch, tmp_path, capsys):
    """Runs the command on a free port and returns its exit code and output."""
    model = tmp_path / "latest.pt"
    model.write_bytes(b"model")
    monkeypatch.setattr(paths, "LATEST_MODEL", model)
    monkeypatch.setattr(server_module, "YOLO", FakeModel)

    def run(port):
        monkeypatch.setattr("sys.argv", ["live_tracking.server", "--port", str(port)])
        code = server_module.main()
        return code, capsys.readouterr().out

    run.model = model
    return run


def new_session(app):
    return requests.post(app.base_url + "/api/sessions").json()["session"]


def send_frame(app, session, body=None, time=0.0):
    return requests.post(
        app.base_url + "/api/frames",
        params={"session": session, "time": time},
        data=jpeg() if body is None else body,
        headers={"Content-Type": "image/jpeg"},
    )


def test_only_this_computer_can_reach_the_server(app):
    assert app.server_address[0] == "127.0.0.1"


def test_page_offers_the_source_choice(app):
    response = requests.get(app.base_url + "/")
    assert response.status_code == 200
    assert "text/html" in response.headers["Content-Type"]
    assert "Scegli la sorgente" in response.text


def test_health_answers_while_the_program_runs(app):
    assert requests.get(app.base_url + "/api/health").status_code == 200


def test_unknown_path_is_not_found(app):
    assert requests.get(app.base_url + "/nothing").status_code == 404
    assert requests.post(app.base_url + "/nothing").status_code == 404


@pytest.mark.parametrize("headers", [{"Host": "evil.example"}, {"Origin": "https://evil.example"}])
def test_other_websites_are_refused(app, headers):
    assert requests.get(app.base_url + "/", headers=headers).status_code == 403
    assert requests.post(app.base_url + "/api/sessions", headers=headers).status_code == 403


def test_missing_model_stops_and_names_the_training_command(start):
    start.model.unlink()
    code, output = start(0)
    assert code == 1
    assert "dataset_tools.train" in output


def test_model_with_other_points_stops_and_explains(start, monkeypatch):
    monkeypatch.setattr(FakeModel, "points", len(SAX.point_names) + 1)
    code, output = start(0)
    assert code == 1
    assert "points" in output


def test_port_in_use_stops_and_says_the_page_may_be_open(start):
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        code, output = start(taken.getsockname()[1])
    assert code == 1
    assert "already be open" in output


def test_a_second_program_on_the_same_port_stops(start, app):
    code, output = start(app.server_address[1])
    assert code == 1
    assert "already be open" in output


def test_an_instrument_without_the_bell_points_stops_and_explains(start, monkeypatch):
    other = instrument_module.Instrument("flute", ("a", "b", "c", "d"), ("a", "b", "c", "d"), ())
    monkeypatch.setattr(instrument_module, "load", lambda: other)
    code, output = start(0)
    assert code == 1
    assert "bell_centre" in output


def test_a_normal_start_warms_the_model_up_and_ends_cleanly_on_ctrl_c(start, monkeypatch):
    models = []

    def load(source):
        models.append(FakeModel(source))
        return models[-1]

    def interrupted(server):
        raise KeyboardInterrupt

    monkeypatch.setattr(server_module, "YOLO", load)
    monkeypatch.setattr(server_module.ThreadingHTTPServer, "serve_forever", interrupted)
    code, output = start(0)
    assert code == 0
    assert "http://127.0.0.1:" in output
    assert len(models[0].seen) == 1


def test_a_frame_returns_the_confident_points(app):
    response = send_frame(app, new_session(app))
    assert response.status_code == 200
    assert [point["name"] for point in response.json()["points"]] == ["bell_centre", "bell_edge_left", "neck"]
    assert response.json()["points"][0]["x"] == pytest.approx(0.1)


def test_a_frame_returns_the_sound_point_and_whether_a_saxophone_is_found(app):
    reply = send_frame(app, new_session(app)).json()
    assert reply["sound_point"] == pytest.approx({"x": 0.1, "y": 0.2})
    assert reply["found"] is True


def test_a_new_session_forgets_the_previous_points(app):
    model = app.RequestHandlerClass.model
    send_frame(app, new_session(app))
    model.predict = lambda image, **arguments: [SimpleNamespace(boxes=SimpleNamespace(conf=torch.tensor([])), keypoints=None)]
    assert send_frame(app, new_session(app), time=0.1).json()["points"] == []


@pytest.mark.parametrize("time", ["", "soon", "nan", "inf"])
def test_a_frame_without_a_valid_time_is_refused(app, time):
    assert send_frame(app, new_session(app), time=time).status_code == 400


def test_a_frame_of_a_replaced_session_is_refused(app):
    old = new_session(app)
    new_session(app)
    assert send_frame(app, old).status_code == 409


def test_a_frame_with_no_valid_session_is_refused(app):
    assert send_frame(app, "nothing").status_code == 409


@pytest.mark.parametrize("body", [b"", b"not an image"])
def test_an_undecodable_frame_is_refused(app, body):
    assert send_frame(app, new_session(app), body).status_code == 400


def test_an_oversized_frame_is_refused_without_reading_it(app):
    response = requests.post(
        app.base_url + "/api/frames",
        params={"session": new_session(app)},
        data=b"x" * (server_module.MAX_FRAME_BYTES + 1),
    )
    assert response.status_code == 413


@pytest.mark.parametrize("length", ["-1", "many"])
def test_an_invalid_frame_length_is_refused(app, length):
    with contextlib.closing(http.client.HTTPConnection(*app.server_address, timeout=5)) as connection:
        connection.putrequest("POST", "/api/frames?session=any&time=0")
        connection.putheader("Content-Length", length)
        connection.endheaders()
        assert connection.getresponse().status == 400


def test_a_frame_with_no_session_before_any_session_is_refused(app):
    response = requests.post(app.base_url + "/api/frames", params={"time": 0}, data=jpeg())
    assert response.status_code == 409
    assert app.RequestHandlerClass.model.seen == []


def test_a_model_failure_is_reported_as_a_failed_analysis(app):
    def failing(image, **arguments):
        raise RuntimeError("out of memory")

    session = new_session(app)
    app.RequestHandlerClass.model.predict = failing
    assert send_frame(app, session).status_code == 500


def test_a_tab_closed_during_the_analysis_is_not_an_error(app):
    model = app.RequestHandlerClass.model
    predict = model.predict
    analysing, closed, handled = threading.Event(), threading.Event(), threading.Event()
    errors = []

    def waiting(image, **arguments):
        analysing.set()
        closed.wait(5)
        return predict(image, **arguments)

    session = new_session(app)
    model.predict = waiting
    app.handle_error = lambda request, client: errors.append(client)
    shutdown_request = app.shutdown_request

    def closed_by_server(request):
        shutdown_request(request)
        handled.set()

    app.shutdown_request = closed_by_server
    connection = http.client.HTTPConnection(*app.server_address, timeout=5)
    connection.connect()
    # Closes at once with a reset, as a browser does, so the reply fails instead of being buffered.
    connection.sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
    connection.request("POST", f"/api/frames?session={session}&time=0", jpeg())
    assert analysing.wait(5)
    connection.close()
    closed.set()
    assert handled.wait(5)
    assert errors == []


def test_nothing_is_saved_on_disk(app, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    send_frame(app, new_session(app))
    assert list(tmp_path.iterdir()) == []


def test_frames_from_many_threads_never_run_on_the_model_at_once(app):
    active = []
    overlaps = []
    model = app.RequestHandlerClass.model
    predict = model.predict

    def guarded(image, **arguments):
        active.append(1)
        overlaps.append(len(active))
        threading.Event().wait(0.01)
        active.pop()
        return predict(image, **arguments)

    model.predict = guarded
    session = new_session(app)
    threads = [threading.Thread(target=send_frame, args=(app, session)) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(overlaps) == 6
    assert max(overlaps) == 1
