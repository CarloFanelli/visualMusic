"""Local page that tracks the saxophone in real time. Reachable only from this computer."""
import argparse
import contextlib
import errno
import math
import sys
import threading
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import cv2
import numpy as np
from ultralytics import YOLO

from dataset_tools import instrument as instrument_module
from dataset_tools import paths, propose, trial
from dataset_tools.local_server import HOST, LocalHandler, serve_until_stopped
from live_tracking import tracking

DEFAULT_PORT = 8766
MAX_FRAME_BYTES = 2 * 1024 * 1024
PAGE = Path(__file__).parent / "static" / "index.html"


def parse_time(query):
    """Returns the time of an image in the source, or None if it is not a usable number."""
    try:
        time = float(query.get("time", [""])[0])
    except ValueError:
        return None
    return time if math.isfinite(time) else None


def frame_length(headers):
    """Returns the declared size of an image, or None if it is not a usable number."""
    try:
        length = int(headers.get("Content-Length", 0))
    except ValueError:
        return None
    return length if length >= 0 else None


def decode_image(body):
    """Returns the image, or None if the bytes are not one."""
    if not body:
        return None
    try:
        return cv2.imdecode(np.frombuffer(body, np.uint8), cv2.IMREAD_COLOR)
    except cv2.error:
        return None


class Handler(LocalHandler):
    instrument: instrument_module.Instrument
    model: object
    device: str
    # Frames can come from more than one browser, and the model must see them one at a time.
    lock: threading.Lock
    session: str = None
    tracker: tracking.Tracker = None

    def do_GET(self):
        if not self._request_is_local():
            self._send_json(403, {"error": "forbidden"})
            return
        path = urlsplit(self.path).path
        if path == "/":
            self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        elif path == "/api/health":
            self._send_json(200, {"status": "running"})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        if not self._request_is_local():
            self._send_json(403, {"error": "forbidden"})
            return
        path = urlsplit(self.path).path
        if path == "/api/sessions":
            self._start_session()
        elif path == "/api/frames":
            self._track_frame()
        else:
            self._send_json(404, {"error": "not found"})

    def _start_session(self):
        session = uuid.uuid4().hex
        with self.lock:
            type(self).session = session
            type(self).tracker = tracking.Tracker(self.instrument)
        self._send_json(200, {"session": session})

    def _track_frame(self):
        length = frame_length(self.headers)
        if length is None:
            self._send_json(400, {"error": "not a valid length"})
            return
        if length > MAX_FRAME_BYTES:
            self._send_json(413, {"error": "frame too large"})
            return
        image = decode_image(self.rfile.read(length))
        if image is None:
            self._send_json(400, {"error": "not an image"})
            return
        query = parse_qs(urlsplit(self.path).query)
        time = parse_time(query)
        if time is None:
            self._send_json(400, {"error": "not a valid time"})
            return
        session = query.get("session", [None])[0]
        with self.lock:
            if session is None or session != self.session:
                self._send_json(409, {"error": "another session is running"})
                return
            try:
                result = self.model.predict(image, device=self.device, verbose=False)[0]
            except RuntimeError as error:
                self._send_json(500, {"error": str(error)})
                return
            state = self.tracker.update(result, time)
        # A tab closed during the analysis is a normal way to stop.
        with contextlib.suppress(BrokenPipeError, ConnectionResetError):
            self._send_json(200, state)


def create_server(instrument, model, device, port=DEFAULT_PORT):
    attributes = {"instrument": instrument, "model": model, "device": device, "lock": threading.Lock()}
    return ThreadingHTTPServer((HOST, port), type("BoundHandler", (Handler,), attributes))


def warm_up(model, device):
    """The first prediction is far slower than the others, and must not delay the first image."""
    model.predict(np.zeros((480, 640, 3), np.uint8), device=device, verbose=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    arguments = parser.parse_args()
    device = trial.default_device()
    try:
        instrument = instrument_module.load()
        tracking.require_sound_point_sources(instrument)
        model = propose.load_model(instrument, paths.LATEST_MODEL, YOLO)
        server = create_server(instrument, model, device, arguments.port)
    except (instrument_module.InvalidInstrument, propose.ProposalError) as error:
        print(f"Cannot start: {error}")
        return 1
    except OSError as error:
        if error.errno != errno.EADDRINUSE:
            raise
        print(f"Cannot start: port {arguments.port} is in use. The page may already be open.")
        return 1
    warm_up(model, device)
    serve_until_stopped(server)
    return 0


if __name__ == "__main__":
    sys.exit(main())
