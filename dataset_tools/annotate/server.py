"""Local page for marking points on images. Reachable only from this computer."""
import argparse
import json
import sys
from dataclasses import dataclass
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from PIL import Image, ImageOps

from dataset_tools import annotations, manifest, paths, proposals
from dataset_tools import instrument as instrument_module
from dataset_tools.local_server import HOST, LocalHandler, serve_until_stopped

DEFAULT_PORT = 8765
PREVIEW_MAX_SIDE = 1600
MAX_BODY_BYTES = 64 * 1024
PAGE = Path(__file__).parent / "static" / "index.html"


@dataclass
class Storage:
    manifest_path: Path = paths.MANIFEST
    annotations_dir: Path = paths.ANNOTATIONS
    images_dir: Path = paths.IMAGES
    previews_dir: Path = paths.PREVIEWS
    proposals_dir: Path = paths.PROPOSALS


def create_preview(source, destination):
    """Upright, like the images training reads, so normalized points fit both."""
    with Image.open(source) as image:
        upright = ImageOps.exif_transpose(image).convert("RGB")
        upright.thumbnail((PREVIEW_MAX_SIDE, PREVIEW_MAX_SIDE))
        with annotations.atomic_writer(destination) as file:
            upright.save(file, "JPEG", quality=85)


class Handler(LocalHandler):
    storage: Storage
    instrument: instrument_module.Instrument

    def _records(self):
        return {record["image_id"]: record for record in manifest.load(self.storage.manifest_path, repair=False)}

    def _proposal(self, image_id):
        return proposals.load(image_id, self.instrument, self.storage.proposals_dir)

    def _state(self):
        images = [
            {
                "image_id": image_id,
                "status": annotations.status_of(annotations.load(image_id, self.storage.annotations_dir), self.instrument),
                # Independent of the status, so an image that is restored regains its proposal.
                "has_proposal": self._proposal(image_id) is not None,
            }
            for image_id in self._records()
        ]
        points = [{"name": n, "label": l} for n, l in zip(self.instrument.point_names, self.instrument.point_labels)]
        return {"points": points, "images": images}

    def _send_preview(self, image_id, record):
        preview = self.storage.previews_dir / f"{image_id}.jpg"
        if not preview.exists():
            try:
                create_preview(self.storage.images_dir / record["file"], preview)
            except (OSError, ValueError, Image.DecompressionBombError):
                self._send_json(404, {"error": "unreadable image"})
                return
        self._send(200, preview.read_bytes(), "image/jpeg")

    def _send_annotation(self, image_id):
        annotation = annotations.load(image_id, self.storage.annotations_dir)
        if annotations.status_of(annotation, self.instrument) == annotations.PENDING:
            annotation = None
        self._send_json(200, {"annotation": annotation})

    def _route(self):
        """Returns (kind, image_id, record); only ids in the manifest ever reach the disk."""
        parts = [unquote(part) for part in urlsplit(self.path).path.split("/")[1:]]
        if parts == [""]:
            return "page", None, None
        if parts == ["api", "state"]:
            return "state", None, None
        if len(parts) == 2 and parts[0] == "images":
            image_id, kind = parts[1], "preview"
        elif len(parts) == 4 and parts[:2] == ["api", "images"] and parts[3] in {"annotation", "proposal"}:
            image_id, kind = parts[2], parts[3]
        else:
            return None, None, None
        record = self._records().get(image_id)
        return (kind, image_id, record) if record else (None, None, None)

    def do_GET(self):
        if not self._request_is_local():
            self._send_json(403, {"error": "forbidden"})
            return
        kind, image_id, record = self._route()
        if kind == "page":
            self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        elif kind == "state":
            self._send_json(200, self._state())
        elif kind == "preview":
            self._send_preview(image_id, record)
        elif kind == "annotation":
            self._send_annotation(image_id)
        elif kind == "proposal":
            self._send_json(200, {"proposal": self._proposal(image_id)})
        else:
            self._send_json(404, {"error": "not found"})

    def do_PUT(self):
        if not self._request_is_local():
            self._send_json(403, {"error": "forbidden"})
            return
        kind, image_id, _ = self._route()
        if kind != "annotation":
            self._send_json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > MAX_BODY_BYTES:
                raise ValueError("body too large")
            annotation = json.loads(self.rfile.read(length))
            annotations.validate(annotation, self.instrument)
        except (ValueError, annotations.InvalidAnnotation) as error:
            self._send_json(400, {"error": str(error)})
            return
        try:
            annotations.save(image_id, annotation, self.storage.annotations_dir)
        except OSError as error:
            self._send_json(500, {"error": str(error)})
            return
        self._send_json(200, {"status": annotation["status"]})


def create_server(instrument, storage=None, port=DEFAULT_PORT):
    handler = type("BoundHandler", (Handler,), {"instrument": instrument, "storage": storage or Storage()})
    return ThreadingHTTPServer((HOST, port), handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    arguments = parser.parse_args()
    try:
        instrument = instrument_module.load()
    except instrument_module.InvalidInstrument as error:
        print(f"Cannot start: {error}")
        return 1
    server = create_server(instrument, port=arguments.port)
    serve_until_stopped(server)
    return 0


if __name__ == "__main__":
    sys.exit(main())
