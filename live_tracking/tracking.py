"""Turns what the model finds in each image into the points to draw and the sound point."""
import math

from dataset_tools import instrument as instrument_module
from dataset_tools import propose, trial

MIN_CONFIDENCE = 0.5
HOLD_SECONDS = 0.2
# Source times are decimals with rounding errors: 5.3 - 5.1 is slightly more than 0.2.
TIME_TOLERANCE = 1e-6
BELL_CENTRE = "bell_centre"
BELL_EDGES = ("bell_edge_left", "bell_edge_right")

# One Euro filter: positions are in fractions of the image, and speeds in fractions per second.
# Slow movement is smoothed down to the minimum cutoff, and faster movement raises it by SPEED_GAIN.
MINIMUM_CUTOFF_HZ = 1.5
SPEED_GAIN = 20.0
SPEED_CUTOFF_HZ = 1.0


def require_sound_point_sources(instrument):
    missing = {BELL_CENTRE, *BELL_EDGES} - set(instrument.point_names)
    if missing:
        raise instrument_module.InvalidInstrument(f"The sound point needs these points: {sorted(missing)}")


def confident_points(result, instrument):
    if not trial.has_detection(result):
        return []
    best = int(result.boxes.conf.argmax())
    confidences = result.keypoints.conf[best].tolist()
    return [
        {"name": point["name"], "x": point["x"], "y": point["y"]}
        for point, confidence in zip(propose.points_of(result, instrument), confidences)
        if confidence >= MIN_CONFIDENCE
    ]


def _within_hold(since, time):
    return time - since <= HOLD_SECONDS + TIME_TOLERANCE


def _blend(new, old, cutoff_hz, seconds):
    weight = 1 / (1 + 1 / (2 * math.pi * cutoff_hz * seconds))
    return weight * new + (1 - weight) * old


class _SteadyCoordinate:
    def __init__(self, value):
        self.value = value
        self.speed = 0.0

    def update(self, value, seconds):
        if seconds <= 0:
            return self.value
        self.speed = _blend((value - self.value) / seconds, self.speed, SPEED_CUTOFF_HZ, seconds)
        cutoff = MINIMUM_CUTOFF_HZ + SPEED_GAIN * abs(self.speed)
        self.value = _blend(value, self.value, cutoff, seconds)
        return self.value


class _HeldPoint:
    def __init__(self, point, time):
        self.x = _SteadyCoordinate(point["x"])
        self.y = _SteadyCoordinate(point["y"])
        self.seen_at = time

    def update(self, point, time):
        seconds = time - self.seen_at
        self.x.update(point["x"], seconds)
        self.y.update(point["y"], seconds)
        self.seen_at = time


class Tracker:
    """Follows one source. Time is the source's own, so a paused video does not age its points."""

    def __init__(self, instrument):
        self.instrument = instrument
        self.held = {}
        self.saxophone_seen_at = None

    def update(self, result, time):
        if trial.has_detection(result) or self.saxophone_seen_at is None:
            self.saxophone_seen_at = time
        self._forget_expired(time)
        for point in confident_points(result, self.instrument):
            if point["name"] in self.held:
                self.held[point["name"]].update(point, time)
            else:
                self.held[point["name"]] = _HeldPoint(point, time)
        self._forget_expired(time)
        points = [
            {"name": name, "x": self.held[name].x.value, "y": self.held[name].y.value}
            for name in self.instrument.point_names
            if name in self.held
        ]
        return {
            "points": points,
            "sound_point": self._sound_point({point["name"]: point for point in points}),
            "found": _within_hold(self.saxophone_seen_at, time),
        }

    def _forget_expired(self, time):
        self.held = {name: held for name, held in self.held.items() if _within_hold(held.seen_at, time)}

    @staticmethod
    def _sound_point(drawn):
        if BELL_CENTRE in drawn:
            return {"x": drawn[BELL_CENTRE]["x"], "y": drawn[BELL_CENTRE]["y"]}
        if all(edge in drawn for edge in BELL_EDGES):
            left, right = (drawn[edge] for edge in BELL_EDGES)
            return {"x": (left["x"] + right["x"]) / 2, "y": (left["y"] + right["y"]) / 2}
        return None
