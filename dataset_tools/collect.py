"""Collects candidate saxophone images with safe licenses, recording proof for each one."""
import argparse
import collections
import datetime
import sys

from dataset_tools import images, licenses, manifest, paths
from dataset_tools.http_client import Http, RequestFailed
from dataset_tools.sources import commons, open_images, openverse

SOURCES = [
    (commons.NAME, commons.candidates),
    (open_images.NAME, open_images.candidates),
    (openverse.NAME, openverse.candidates),
]


class SourceReport:
    def __init__(self, name):
        self.name = name
        self.kept = 0
        self.already_known = 0
        self.rejected = collections.Counter()
        self.notes = []
        self.failure = None

    def lines(self):
        lines = [f"{self.name}: {self.kept} kept, {self.already_known} already known, {sum(self.rejected.values())} rejected"]
        lines.extend(f"  rejected, {reason}: {count}" for reason, count in sorted(self.rejected.items()))
        lines.extend(f"  note: {note}" for note in self.notes)
        if self.failure:
            lines.append(f"  FAILED: {self.failure}")
        return lines


def rejection_reason(candidate):
    """Returns the license family as (family, None), or (None, reason) for an unusable candidate."""
    if candidate.unsupported_reason:
        return None, candidate.unsupported_reason
    family, reason = licenses.classify(candidate.license_raw)
    if family is None:
        return None, reason
    if not candidate.source_url:
        return None, "no-source-url"
    if family == licenses.CC_BY and not candidate.author:
        return None, "no-author"
    if family == licenses.CC_BY and not candidate.license_url:
        return None, "no-license-url"
    if not candidate.download_url:
        return None, "no-file"
    return family, None


def _record(candidate, family, file_name, sha256, today):
    return {
        "image_id": candidate.image_id,
        "source": candidate.source,
        "source_url": candidate.source_url,
        "download_url": candidate.download_url,
        "author": candidate.author or "unknown",
        "license": family,
        "license_raw": candidate.license_raw,
        "license_url": candidate.license_url,
        "title": candidate.title,
        "collected_on": today,
        "sha256": sha256,
        "file": file_name,
    }


def _collect_source(http, candidates, report, known_ids, known_hashes, images_dir, manifest_path, cache_dir, limit, today):
    for candidate in candidates(http, report.notes, cache_dir):
        if limit is not None and report.kept >= limit:
            return
        if candidate.image_id in known_ids:
            report.already_known += 1
            continue
        family, reason = rejection_reason(candidate)
        if family is None:
            report.rejected[reason] += 1
            continue
        try:
            file_name, sha256 = images.fetch(http, candidate.download_url, images_dir, candidate.image_id)
        except RequestFailed:
            report.rejected["download-failed"] += 1
            continue
        except images.UnsupportedImage:
            report.rejected["unsupported-format"] += 1
            continue
        if sha256 in known_hashes:
            (images_dir / file_name).unlink()
            report.rejected["duplicate"] += 1
            continue
        manifest.append(_record(candidate, family, file_name, sha256, today), manifest_path)
        known_ids.add(candidate.image_id)
        known_hashes.add(sha256)
        report.kept += 1


def collect(http, sources=SOURCES, images_dir=paths.IMAGES, manifest_path=paths.MANIFEST, cache_dir=paths.CACHE, limit=None, today=None):
    today = today or datetime.date.today().isoformat()
    records = manifest.load(manifest_path)
    known_ids = {record["image_id"] for record in records}
    known_hashes = {record["sha256"] for record in records}
    reports = []
    for name, candidates in sources:
        report = SourceReport(name)
        reports.append(report)
        print(f"Collecting from {name}...", flush=True)
        try:
            _collect_source(http, candidates, report, known_ids, known_hashes, images_dir, manifest_path, cache_dir, limit, today)
        except RequestFailed as error:
            report.failure = str(error)
    return reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, help="stop after keeping this many new images per source")
    arguments = parser.parse_args()
    reports = collect(Http(), limit=arguments.limit)
    for report in reports:
        print("\n".join(report.lines()))
    return 1 if all(report.failure for report in reports) else 0


if __name__ == "__main__":
    sys.exit(main())
