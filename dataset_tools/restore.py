"""Brings back missing online-sourced image files listed in the manifest."""
import hashlib
import sys
from pathlib import Path

from dataset_tools import images, manifest, paths
from dataset_tools.http_client import Http, RequestFailed


class RestoreReport:
    def __init__(self):
        self.present = 0
        self.restored = 0
        self.missing = []
        self.user_owned_missing = []

    def lines(self):
        lines = [
            f"Already present: {self.present}",
            f"Restored: {self.restored}",
            f"Missing, no longer available: {len(self.missing)}",
            f"Missing, restorable only from your videos: {len(self.user_owned_missing)}",
        ]
        lines.extend(f"  missing: {image_id}" for image_id in self.missing)
        lines.extend(f"  run the frames command on your video for: {image_id}" for image_id in self.user_owned_missing)
        return lines


def _is_valid(path, sha256):
    if not path.exists():
        return False
    with open(path, "rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest() == sha256


def _download(http, record, images_dir):
    """Keeps the downloaded file only if it is exactly the recorded one."""
    try:
        file_name, sha256 = images.fetch(http, record["download_url"], images_dir, record["image_id"])
    except (RequestFailed, images.UnsupportedImage):
        return False
    if sha256 != record["sha256"] or file_name != record["file"]:
        (images_dir / file_name).unlink()
        return False
    return True


def restore(http, images_dir=paths.IMAGES, manifest_path=paths.MANIFEST):
    report = RestoreReport()
    for record in manifest.load(manifest_path, repair=False):
        path = images_dir / record["file"]
        if Path(record["file"]).name != record["file"]:
            report.missing.append(record["image_id"])
        elif _is_valid(path, record["sha256"]):
            report.present += 1
        elif not record.get("download_url"):
            report.user_owned_missing.append(record["image_id"])
        else:
            path.unlink(missing_ok=True)
            if _download(http, record, images_dir):
                report.restored += 1
            else:
                report.missing.append(record["image_id"])
    return report


def main():
    print("\n".join(restore(Http()).lines()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
