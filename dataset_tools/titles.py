"""Adds the titles their authors gave to images collected before titles were recorded."""
import sys
from dataclasses import dataclass, field
from urllib.parse import unquote

from dataset_tools import manifest, paths
from dataset_tools.http_client import Http, RequestFailed
from dataset_tools.sources import commons, open_images, openverse

OPEN_IMAGES_PREFIX = "openimages-"
OPENVERSE_PREFIX = "openverse-"


@dataclass
class Report:
    added: int = 0
    not_found: list = field(default_factory=list)
    failures: list = field(default_factory=list)

    def lines(self):
        lines = [f"Titles added: {self.added}"]
        lines.extend(f"Not found at the source, so still unknown: {image_id}" for image_id in self.not_found)
        lines.extend(f"FAILED: {failure}" for failure in self.failures)
        return lines


def commons_title(record):
    url = record.get("source_url") or ""
    return unquote(url.split("/wiki/File:", 1)[1]).replace("_", " ") if "/wiki/File:" in url else None


def _open_images_titles(http, cache_dir, report):
    """Reads the Open Images metadata again, and refreshes the cache so that later collections have titles too."""
    try:
        rows = open_images._fetch_saxophone_rows(http)
    except RequestFailed as error:
        report.failures.append(f"{open_images.NAME}: {error}")
        return {}
    open_images.write_cache(rows, cache_dir)
    return {OPEN_IMAGES_PREFIX + row["ImageID"]: (row.get("Title") or "").strip() for row in rows}


def _openverse_title(http, record, report):
    try:
        result = http.get_json(f"{openverse.API}{record['image_id'][len(OPENVERSE_PREFIX):]}/")
    except RequestFailed as error:
        report.failures.append(f"{record['image_id']}: {error}")
        return None
    return (result.get("title") or "").strip()


def backfill(http, manifest_path=paths.MANIFEST, cache_dir=paths.CACHE):
    records = manifest.load(manifest_path)
    missing = [record for record in records if record.get("title") is None]
    report = Report()
    open_images_titles = None
    for record in missing:
        if record["source"] == commons.NAME:
            title = commons_title(record)
        elif record["source"] == open_images.NAME:
            if open_images_titles is None:
                print("Reading the Open Images metadata: this takes several minutes...", flush=True)
                open_images_titles = _open_images_titles(http, cache_dir, report)
            title = open_images_titles.get(record["image_id"])
            if title is None and not report.failures:
                report.not_found.append(record["image_id"])
        elif record["source"] == openverse.NAME:
            title = _openverse_title(http, record, report)
        else:
            continue
        if title is not None:
            record["title"] = title
            report.added += 1
    if report.added:
        manifest.rewrite(records, manifest_path)
    return report


def main():
    report = backfill(Http())
    print("\n".join(report.lines()))
    return 1 if report.failures else 0


if __name__ == "__main__":
    sys.exit(main())
