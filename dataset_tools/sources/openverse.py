"""Candidates from Openverse searches for tenor and alto saxophones."""
from dataset_tools.http_client import RequestFailed
from dataset_tools.sources import Candidate

API = "https://api.openverse.org/v1/images/"
NAME = "Openverse"
QUERIES = ["tenor saxophone", "alto saxophone"]
PAGE_SIZE = 20
# Openverse refuses anonymous requests deeper than this many results.
ANONYMOUS_RESULT_LIMIT = 240
DEPTH_ERROR = "pagination depth"


def _candidate(result):
    return Candidate(
        image_id=f"openverse-{result['id']}",
        source=NAME,
        source_url=result.get("foreign_landing_url") or "",
        download_url=result.get("url") or "",
        author=(result.get("creator") or "").strip() or None,
        license_raw=result.get("license"),
        license_url=result.get("license_url"),
        title=(result.get("title") or "").strip(),
    )


def _search(http, query, notes, seen):
    page = 1
    while True:
        if page * PAGE_SIZE > ANONYMOUS_RESULT_LIMIT:
            notes.append(f'Search "{query}" stopped at the anonymous limit of {ANONYMOUS_RESULT_LIMIT} results.')
            return
        try:
            data = http.get_json(
                API, {"q": query, "license": "by,cc0,pdm", "page_size": PAGE_SIZE, "page": page}
            )
        except RequestFailed as error:
            if DEPTH_ERROR in str(error):
                notes.append(f'Search "{query}" stopped at the anonymous limit.')
                return
            raise
        for result in data.get("results", []):
            if result["id"] not in seen:
                seen.add(result["id"])
                yield _candidate(result)
        if page >= data.get("page_count", 0):
            return
        page += 1


def candidates(http, notes, cache_directory=None):
    notes.append("Disallowed licenses are filtered by Openverse itself, so they are not in the rejection counts.")
    seen = set()
    for query in QUERIES:
        yield from _search(http, query, notes, seen)
