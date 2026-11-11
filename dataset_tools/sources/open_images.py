"""Candidates from the Open Images "Saxophone" class. Its image files live on an S3 mirror."""
import json
import os

from dataset_tools import paths
from dataset_tools.sources import Candidate

NAME = "Open Images"
SAXOPHONE_LABEL = "/m/06ncr"
CACHE_FILE = "open_images_saxophone.jsonl"
FILE_URL = "https://s3.amazonaws.com/open-images-dataset/{subset}/{image_id}.jpg"
PAGE_KEPT_FIELDS = ["ImageID", "Subset", "OriginalLandingURL", "License", "Author", "Title"]

_BASE = "https://storage.googleapis.com/openimages"
SPLITS = [
    (f"{_BASE}/v6/oidv6-train-annotations-bbox.csv", f"{_BASE}/2018_04/train/train-images-boxable-with-rotation.csv"),
    (f"{_BASE}/v5/validation-annotations-bbox.csv", f"{_BASE}/2018_04/validation/validation-images-with-rotation.csv"),
    (f"{_BASE}/v5/test-annotations-bbox.csv", f"{_BASE}/2018_04/test/test-images-with-rotation.csv"),
]


def _fetch_saxophone_rows(http):
    rows = []
    for annotations_url, metadata_url in SPLITS:
        ids = {row["ImageID"] for row in http.iter_csv_rows(annotations_url) if row["LabelName"] == SAXOPHONE_LABEL}
        rows.extend(
            {field: row.get(field) for field in PAGE_KEPT_FIELDS}
            for row in http.iter_csv_rows(metadata_url)
            if row["ImageID"] in ids
        )
    return rows


def _load_rows(http, cache_directory):
    """The train metadata is about 2 GB, so filtered rows are kept for later runs."""
    cache = cache_directory / CACHE_FILE
    if cache.exists():
        with open(cache, encoding="utf-8") as file:
            return [json.loads(line) for line in file]
    rows = _fetch_saxophone_rows(http)
    write_cache(rows, cache_directory)
    return rows


def write_cache(rows, cache_directory=paths.CACHE):
    cache = cache_directory / CACHE_FILE
    cache_directory.mkdir(parents=True, exist_ok=True)
    temporary = cache.with_suffix(".part")
    with open(temporary, "w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
    os.replace(temporary, cache)


def candidates(http, notes, cache_directory=paths.CACHE):
    for row in _load_rows(http, cache_directory):
        yield Candidate(
            image_id=f"openimages-{row['ImageID']}",
            source=NAME,
            source_url=row["OriginalLandingURL"],
            download_url=FILE_URL.format(subset=row["Subset"], image_id=row["ImageID"]),
            author=(row.get("Author") or "").strip() or None,
            license_raw=row["License"],
            license_url=row["License"],
            title=(row.get("Title") or "").strip() if "Title" in row else None,
        )
