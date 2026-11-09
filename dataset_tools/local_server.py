"""What every page reachable only from this computer has in common."""
import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlsplit

HOST = "127.0.0.1"


def serve_until_stopped(server):
    print(f"Open http://{HOST}:{server.server_address[1]} (press Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


class LocalHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, status, body=b"", content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status, value):
        self._send(status, json.dumps(value, ensure_ascii=False).encode("utf-8"))

    def _allowed_hosts(self):
        port = self.server.server_address[1]
        return {f"{HOST}:{port}", f"localhost:{port}"}

    def _request_is_local(self):
        """Stops other websites open in the browser from reaching this server."""
        if self.headers.get("Host") not in self._allowed_hosts():
            return False
        origin = self.headers.get("Origin")
        return origin is None or urlsplit(origin).netloc in self._allowed_hosts()
