import pytest
import requests

from dataset_tools.http_client import MAX_ATTEMPTS, Http, RequestFailed


class FakeResponse:
    def __init__(self, status_code=200, headers=None, payload=None):
        self.status_code = status_code
        self.headers = headers or {}
        self.payload = payload
        self.text = ""

    @property
    def ok(self):
        return self.status_code < 400

    def json(self):
        return self.payload

    def close(self):
        pass


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.headers = {}
        self.calls = 0

    def get(self, *args, **kwargs):
        self.calls += 1
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def client(session):
    waits = []
    http = Http(session=session, sleep=waits.append, clock=lambda: 1000.0)
    return http, waits


def test_waits_as_requested_then_retries_after_a_rate_limit():
    session = FakeSession([FakeResponse(429, {"Retry-After": "7"}), FakeResponse(payload={"ok": True})])
    http, waits = client(session)
    assert http.get_json("https://example.org/x") == {"ok": True}
    assert 7 in waits
    assert session.calls == 2


def test_gives_up_when_the_limit_persists_without_bypassing_it():
    session = FakeSession([FakeResponse(429, {"Retry-After": "1"}) for _ in range(MAX_ATTEMPTS)])
    http, _ = client(session)
    with pytest.raises(RequestFailed):
        http.get_json("https://example.org/x")
    assert session.calls == MAX_ATTEMPTS


def test_second_request_to_a_host_is_spaced_out():
    session = FakeSession([FakeResponse(payload={}), FakeResponse(payload={})])
    http, waits = client(session)
    http.get_json("https://example.org/a")
    http.get_json("https://example.org/b")
    assert waits == [1.0]


def test_wikimedia_file_host_gets_a_longer_interval():
    session = FakeSession([FakeResponse(payload={}), FakeResponse(payload={})])
    http, waits = client(session)
    http.get_json("https://upload.wikimedia.org/a")
    http.get_json("https://upload.wikimedia.org/b")
    assert waits == [5.0]


def test_network_error_becomes_request_failed():
    http, _ = client(FakeSession([requests.ConnectionError("down")]))
    with pytest.raises(RequestFailed):
        http.get_json("https://example.org/x")


def test_http_error_becomes_request_failed():
    http, _ = client(FakeSession([FakeResponse(500)]))
    with pytest.raises(RequestFailed):
        http.get_json("https://example.org/x")


def test_does_not_wait_after_the_last_refused_attempt():
    session = FakeSession([FakeResponse(429, headers={"Retry-After": "600"}) for _ in range(4)])
    http, waits = client(session)
    with pytest.raises(RequestFailed):
        http.get_json("https://example.org/x")
    assert waits.count(600) == 3
