"""Loads the editable definition of an instrument's points."""
import json
from dataclasses import dataclass

from dataset_tools import paths

DEFAULT_PATH = paths.INSTRUMENTS / "saxophone.json"


class InvalidInstrument(Exception):
    pass


@dataclass(frozen=True)
class Instrument:
    class_name: str
    # Stable names stored in annotations, and the labels shown to the user, in click order.
    point_names: tuple
    point_labels: tuple
    mirror_pairs: tuple


def _parse(data):
    points = data["points"]
    names = [point["name"] for point in points]
    labels = [point["label"] for point in points]
    pairs = [tuple(pair) for pair in data.get("mirror_pairs", [])]
    if not data["class_name"] or not names:
        raise ValueError("a class name and at least one point are required")
    if len(set(names)) != len(names):
        raise ValueError("point names must be unique")
    for pair in pairs:
        if len(set(pair)) != 2 or len(pair) != 2 or not set(pair) <= set(names):
            raise ValueError(f"mirror pair {list(pair)} must name two different defined points")
    paired = [name for pair in pairs for name in pair]
    if len(set(paired)) != len(paired):
        raise ValueError("a point can belong to only one mirror pair")
    return Instrument(data["class_name"], tuple(names), tuple(labels), tuple(pairs))


def load(path=DEFAULT_PATH):
    try:
        with open(path, encoding="utf-8") as file:
            return _parse(json.load(file))
    except OSError as error:
        raise InvalidInstrument(f"{path} cannot be read: {error}") from error
    except (ValueError, KeyError, TypeError) as error:
        raise InvalidInstrument(f"{path} is invalid: {error!r}") from error
