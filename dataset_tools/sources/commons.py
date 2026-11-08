"""Candidates from the Wikimedia Commons tenor and alto saxophone categories."""
from html.parser import HTMLParser

from dataset_tools.sources import Candidate

API = "https://commons.wikimedia.org/w/api.php"
NAME = "Wikimedia Commons"
CATEGORIES = ["Category:Tenor saxophones", "Category:Alto saxophones"]
SUBCATEGORY_DEPTH = 1
SUPPORTED_MIME = {"image/jpeg", "image/png"}


class _TextOnly(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def author_from_html(value):
    """The Commons author field is HTML; returns None when no author is identifiable."""
    parser = _TextOnly()
    parser.feed(value or "")
    parser.close()
    author = " ".join("".join(parser.parts).split())
    if not author or author.lower().startswith("unknown"):
        return None
    return author


def _candidate(page):
    info = (page.get("imageinfo") or [{}])[0]
    metadata = info.get("extmetadata", {})
    mime = info.get("mime", "")
    return Candidate(
        image_id=f"commons-{page['pageid']}",
        source=NAME,
        source_url=info.get("descriptionurl", ""),
        download_url=info.get("url", "").split("?")[0],
        author=author_from_html(metadata.get("Artist", {}).get("value")),
        license_raw=metadata.get("LicenseShortName", {}).get("value"),
        license_url=metadata.get("LicenseUrl", {}).get("value") or info.get("descriptionurl"),
        unsupported_reason=None if mime in SUPPORTED_MIME else "unsupported-format",
    )


def _walk(http, category, depth, seen_categories, seen_pages):
    if category in seen_categories:
        return
    seen_categories.add(category)
    continuation = {}
    while True:
        data = http.get_json(
            API,
            {
                "action": "query",
                "format": "json",
                "generator": "categorymembers",
                "gcmtitle": category,
                "gcmtype": "file|subcat",
                "gcmlimit": 50,
                "prop": "imageinfo",
                "iiprop": "url|mime|extmetadata",
                "iiextmetadatafilter": "LicenseShortName|LicenseUrl|Artist",
                **continuation,
            },
        )
        for page in data.get("query", {}).get("pages", {}).values():
            if page["title"].startswith("Category:"):
                if depth > 0:
                    yield from _walk(http, page["title"], depth - 1, seen_categories, seen_pages)
            elif page["pageid"] not in seen_pages:
                seen_pages.add(page["pageid"])
                yield _candidate(page)
        if "continue" not in data:
            return
        continuation = data["continue"]


def candidates(http, notes, cache_directory=None):
    seen_categories, seen_pages = set(), set()
    for category in CATEGORIES:
        yield from _walk(http, category, SUBCATEGORY_DEPTH, seen_categories, seen_pages)
