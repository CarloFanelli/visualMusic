"""Append-only manifest: the license and attribution proof of every candidate image."""
import json
import os

from dataset_tools import paths


class CorruptManifest(Exception):
    pass


def _repair_torn_last_line(path):
    """An interrupted append can only damage the final line, which is removed."""
    with open(path, "rb") as file:
        content = file.read()
    if not content or content.endswith(b"\n"):
        return
    keep = content.rfind(b"\n") + 1
    with open(path, "r+b") as file:
        file.truncate(keep)


def load(path=paths.MANIFEST, repair=True):
    """Pass repair=False to only read, for example while a collection may be appending."""
    if not path.exists():
        return []
    if repair:
        _repair_torn_last_line(path)
    records = []
    with open(path, encoding="utf-8") as file:
        for number, line in enumerate(file, start=1):
            if not line.endswith("\n"):
                break
            try:
                records.append(json.loads(line))
            except ValueError as error:
                raise CorruptManifest(f"{path}, line {number}: {error}") from error
    return records


def rewrite(records, path=paths.MANIFEST):
    """Replaces the whole manifest at once, so an interruption leaves the previous one intact."""
    temporary = path.with_name(f".{path.name}.part")
    with open(temporary, "w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
        file.flush()
        os.fsync(file.fileno())
    os.replace(temporary, path)


def append(record, path=paths.MANIFEST):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")
        file.flush()
        os.fsync(file.fileno())
