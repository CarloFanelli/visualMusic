"""Stores each image's annotation in its own versioned file."""
import contextlib
import json
import os
import tempfile

from dataset_tools import paths

PENDING = "pending"
ANNOTATED = "annotated"
SKIPPED = "skipped"
REJECTED = "rejected"


class InvalidAnnotation(Exception):
    pass


def _path(image_id, directory):
    return directory / f"{image_id}.json"


def load(image_id, directory=paths.ANNOTATIONS):
    """Returns the stored annotation, or None if there is none usable."""
    try:
        with open(_path(image_id, directory), encoding="utf-8") as file:
            return json.load(file)
    except (OSError, ValueError):
        return None


def _is_coordinate(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1


def validate(annotation, instrument):
    status = annotation.get("status") if isinstance(annotation, dict) else None
    if not isinstance(status, str):
        raise InvalidAnnotation("unknown status")
    if status in {PENDING, SKIPPED, REJECTED}:
        if "points" in annotation:
            raise InvalidAnnotation(f"status {status} cannot have points")
        return
    if status != ANNOTATED:
        raise InvalidAnnotation("unknown status")
    points = annotation.get("points")
    if not isinstance(points, list) or not all(isinstance(point, dict) for point in points):
        raise InvalidAnnotation("points do not match the instrument definition")
    if [point.get("name") for point in points] != list(instrument.point_names):
        raise InvalidAnnotation("points do not match the instrument definition")
    for point in points:
        if point.get("visible") is False:
            if "x" in point or "y" in point:
                raise InvalidAnnotation(f"hidden point {point['name']} cannot have a position")
        elif point.get("visible") is not True or not _is_coordinate(point.get("x")) or not _is_coordinate(point.get("y")):
            raise InvalidAnnotation(f"point {point['name']} is outside the image")
    if not any(point["visible"] for point in points):
        raise InvalidAnnotation("at least one point must be visible")


@contextlib.contextmanager
def atomic_writer(destination):
    """Yields a binary file that replaces destination only if the block succeeds, so a failure leaves any earlier file intact."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=destination.parent, prefix=f".{destination.name}.", suffix=".part")
    try:
        with os.fdopen(descriptor, "wb") as file:
            yield file
        os.replace(temporary, destination)
    except BaseException:
        os.unlink(temporary)
        raise


def save(image_id, annotation, directory=paths.ANNOTATIONS):
    with atomic_writer(_path(image_id, directory)) as file:
        file.write((json.dumps(annotation, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def status_of(annotation, instrument):
    """An annotation made with other points counts as pending, but its file is kept."""
    if annotation is None:
        return PENDING
    try:
        validate(annotation, instrument)
    except InvalidAnnotation:
        return PENDING
    return annotation["status"]
