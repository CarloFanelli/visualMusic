"""Polite HTTP access: one request at a time per host, honouring rate limits."""
import csv
import hashlib
import time
from urllib.parse import urlsplit

import requests

USER_AGENT = "visualMusic-dataset/0.1"
TIMEOUT = (15, 120)
MAX_ATTEMPTS = 4
DEFAULT_RETRY_AFTER = 30
MIN_INTERVAL = 1.0
# This host imposed a 600-second wait when asked for one file per second.
HOST_INTERVALS = {"upload.wikimedia.org": 5.0}


class RequestFailed(Exception):
    pass


def _retry_after(response):
    try:
        return max(int(response.headers.get("Retry-After", "")), 1)
    except ValueError:
        return DEFAULT_RETRY_AFTER


class Http:
    def __init__(self, session=None, sleep=time.sleep, clock=time.monotonic):
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.sleep = sleep
        self.clock = clock
        self.last_request = {}

    def _wait_turn(self, host):
        last = self.last_request.get(host)
        if last is not None:
            remaining = HOST_INTERVALS.get(host, MIN_INTERVAL) - (self.clock() - last)
            if remaining > 0:
                self.sleep(remaining)
        self.last_request[host] = self.clock()

    def _get(self, url, params=None, stream=False):
        for attempt in range(1, MAX_ATTEMPTS + 1):
            self._wait_turn(urlsplit(url).netloc)
            try:
                response = self.session.get(url, params=params, stream=stream, timeout=TIMEOUT)
            except requests.RequestException as error:
                raise RequestFailed(f"{url}: {error}") from error
            if response.status_code != 429:
                if not response.ok:
                    detail = response.text[:200]
                    response.close()
                    raise RequestFailed(f"{url}: HTTP {response.status_code}: {detail}")
                return response
            wait = _retry_after(response)
            response.close()
            if attempt < MAX_ATTEMPTS:
                print(f"Rate limited by {urlsplit(url).netloc}, waiting {wait} seconds.", flush=True)
                self.sleep(wait)
        raise RequestFailed(f"{url}: still rate limited after {MAX_ATTEMPTS} attempts")

    def get_json(self, url, params=None):
        response = self._get(url, params=params)
        try:
            return response.json()
        except ValueError as error:
            raise RequestFailed(f"{url}: invalid JSON") from error

    def iter_csv_rows(self, url):
        """Streams a CSV so very large files never have to fit in memory."""
        response = self._get(url, stream=True)
        response.encoding = "utf-8"
        try:
            yield from csv.DictReader(response.iter_lines(decode_unicode=True))
        except requests.RequestException as error:
            raise RequestFailed(f"{url}: {error}") from error
        finally:
            response.close()

    def download(self, url, destination):
        """Saves the response body to destination and returns its SHA-256."""
        digest = hashlib.sha256()
        response = self._get(url, stream=True)
        try:
            with open(destination, "wb") as file:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    file.write(chunk)
                    digest.update(chunk)
        except requests.RequestException as error:
            raise RequestFailed(f"{url}: {error}") from error
        finally:
            response.close()
        return digest.hexdigest()
