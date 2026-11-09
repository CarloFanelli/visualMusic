from types import SimpleNamespace

import numpy as np
import pytest
import torch

from dataset_tools import instrument as instrument_module
from live_tracking import tracking

SAX = instrument_module.load()
POSITIONS = [(0.1, 0.2), (0.3, 0.4), (0.5, 0.6), (0.7, 0.8)]


NOTHING = SimpleNamespace(boxes=SimpleNamespace(conf=torch.tensor([])), keypoints=None)
NO_CENTRE = (0.0, 0.9, 0.9, 0.9)
ONE_EDGE = (0.0, 0.9, 0.0, 0.9)
NECK_ONLY = (0.0, 0.0, 0.0, 0.9)


def result(*detections, positions=POSITIONS):
    """Each detection is (box confidence, point confidences)."""
    return SimpleNamespace(
        boxes=SimpleNamespace(conf=torch.tensor([box for box, _ in detections])),
        keypoints=SimpleNamespace(
            xyn=torch.tensor([positions for _ in detections]),
            conf=torch.tensor([points for _, points in detections]),
        ),
    )


def detection(positions=POSITIONS, confidences=(0.9, 0.9, 0.9, 0.9)):
    return result((0.9, list(confidences)), positions=positions)


def names(points):
    return [point["name"] for point in points]


def test_no_saxophone_gives_no_points():
    assert tracking.confident_points(NOTHING, SAX) == []


def test_point_below_half_confidence_is_left_out():
    points = tracking.confident_points(result((0.9, [0.9, 0.49, 0.9, 0.9])), SAX)
    assert names(points) == ["bell_centre", "bell_edge_right", "neck"]


def test_point_at_exactly_half_confidence_is_kept():
    points = tracking.confident_points(result((0.9, [0.5, 0.5, 0.5, 0.5])), SAX)
    assert names(points) == list(SAX.point_names)


def test_positions_are_those_of_the_model():
    point = tracking.confident_points(result((0.9, [0.9, 0.0, 0.0, 0.0])), SAX)[0]
    assert point["x"] == pytest.approx(0.1)
    assert point["y"] == pytest.approx(0.2)


def test_only_the_most_confident_saxophone_is_used():
    points = tracking.confident_points(result((0.4, [0.9, 0.9, 0.9, 0.9]), (0.8, [0.9, 0.0, 0.0, 0.0])), SAX)
    assert names(points) == ["bell_centre"]


def centre_of(state):
    return next((point for point in state["points"] if point["name"] == "bell_centre"), None)


@pytest.fixture
def tracker():
    return tracking.Tracker(SAX)


def test_sound_point_is_the_bell_centre_when_drawn(tracker):
    state = tracker.update(detection(), 0.0)
    assert state["sound_point"] == pytest.approx({"x": 0.1, "y": 0.2})


def test_sound_point_is_midway_between_the_edges_without_a_centre(tracker):
    state = tracker.update(detection(confidences=NO_CENTRE), 0.0)
    assert state["sound_point"] == pytest.approx({"x": 0.4, "y": 0.5})


@pytest.mark.parametrize("confidences", [ONE_EDGE, NECK_ONLY])
def test_otherwise_no_sound_point_and_visible_points_stay(tracker, confidences):
    state = tracker.update(detection(confidences=confidences), 0.0)
    assert state["sound_point"] is None
    assert names(state["points"])[-1] == "neck"


def test_a_centre_being_held_still_gives_the_sound_point(tracker):
    tracker.update(detection(), 0.0)
    state = tracker.update(detection(confidences=NECK_ONLY), 0.1)
    assert state["sound_point"] == pytest.approx({"x": 0.1, "y": 0.2})


def test_sound_point_moves_to_the_midpoint_when_the_centre_is_gone(tracker):
    tracker.update(detection(), 0.0)
    state = tracker.update(detection(confidences=NO_CENTRE), 0.3)
    assert state["sound_point"] == pytest.approx({"x": 0.4, "y": 0.5})


def test_a_lost_point_stays_for_exactly_the_hold_then_disappears(tracker):
    tracker.update(detection(), 0.0)
    assert centre_of(tracker.update(NOTHING, 0.2))["x"] == pytest.approx(0.1)
    assert centre_of(tracker.update(NOTHING, 0.21)) is None


def test_hold_counts_source_time_only(tracker):
    tracker.update(detection(), 100.0)
    assert centre_of(tracker.update(NOTHING, 100.1)) is not None


def test_a_flickering_point_stays_drawn(tracker):
    for step, confidence in enumerate([0.9, 0.4, 0.9, 0.4, 0.9, 0.4]):
        state = tracker.update(detection(confidences=(confidence, 0.9, 0.9, 0.9)), step / 30)
        assert centre_of(state) is not None


def test_saxophone_counts_as_lost_only_after_more_than_the_hold(tracker):
    assert tracker.update(detection(), 0.0)["found"] is True
    assert tracker.update(NOTHING, 0.2)["found"] is True
    assert tracker.update(NOTHING, 0.21)["found"] is False
    assert tracker.update(detection(), 0.3)["found"] is True


def test_a_start_with_no_saxophone_waits_the_hold_too(tracker):
    assert tracker.update(NOTHING, 5.0)["found"] is True
    assert tracker.update(NOTHING, 5.21)["found"] is False


def positions_at(x, y=0.5):
    return [(x, y), (0.3, 0.4), (0.5, 0.6), (0.7, 0.8)]


def test_a_still_saxophone_trembles_less_than_the_model(tracker):
    random = np.random.default_rng(1)
    raw, drawn = [], []
    for step in range(120):
        x = 0.5 + random.normal(0, 0.003)
        raw.append(x)
        drawn.append(centre_of(tracker.update(detection(positions_at(x)), step / 30))["x"])
    assert np.std(drawn[30:]) < np.std(raw[30:]) / 2


def test_a_fast_movement_is_followed_within_the_hold(tracker):
    for step in range(30):
        tracker.update(detection(positions_at(0.2)), step / 30)
    state = None
    for step in range(30, 37):
        state = tracker.update(detection(positions_at(0.7)), step / 30)
    assert centre_of(state)["x"] == pytest.approx(0.7, abs=0.02)


def test_a_steady_movement_does_not_trail_far_behind(tracker):
    state = None
    for step in range(60):
        x = 0.1 + step * 0.012
        state = tracker.update(detection(positions_at(x)), step / 30)
    assert centre_of(state)["x"] == pytest.approx(x, abs=0.02)


def test_a_point_that_reappears_starts_at_its_new_position(tracker):
    tracker.update(detection(positions_at(0.2)), 0.0)
    tracker.update(NOTHING, 0.5)
    state = tracker.update(detection(positions_at(0.8)), 0.6)
    assert centre_of(state)["x"] == pytest.approx(0.8)


def test_a_point_that_reappears_after_a_gap_with_no_images_starts_at_its_new_position(tracker):
    tracker.update(detection(positions_at(0.2)), 0.0)
    state = tracker.update(detection(positions_at(0.8)), 0.5)
    assert centre_of(state)["x"] == pytest.approx(0.8)


def test_exactly_the_hold_counts_as_within_it_despite_rounding(tracker):
    tracker.update(detection(), 5.1)
    state = tracker.update(NOTHING, 5.3)
    assert centre_of(state) is not None
    assert state["found"] is True


def test_positions_stay_inside_the_image(tracker):
    state = tracker.update(detection(positions_at(1.2, -0.1)), 0.0)
    assert centre_of(state)["x"] == 1.0
    assert centre_of(state)["y"] == 0.0


def test_an_instrument_without_the_bell_points_is_refused():
    other = instrument_module.Instrument("flute", ("mouth", "end"), ("a", "b"), ())
    with pytest.raises(instrument_module.InvalidInstrument, match="bell_centre"):
        tracking.require_sound_point_sources(other)
