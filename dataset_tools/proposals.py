"""Stores the points a trained model suggests for one image, separate from annotations."""
from dataset_tools import annotations, paths


def load(image_id, instrument, directory=paths.PROPOSALS):
    """Returns the stored points, or None if there are none usable with this instrument."""
    stored = annotations.load(image_id, directory)
    points = stored.get("points") if isinstance(stored, dict) else None
    try:
        annotations.validate({"status": annotations.ANNOTATED, "points": points}, instrument)
    except annotations.InvalidAnnotation:
        return None
    return points


def save(image_id, points, directory=paths.PROPOSALS):
    annotations.save(image_id, {"points": points}, directory)


def remove(image_id, directory=paths.PROPOSALS):
    (directory / f"{image_id}.json").unlink(missing_ok=True)
