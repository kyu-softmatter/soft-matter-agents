"""Motion patterns (T-20261002-2205 stage 2): shape, checks, interpolation. Moves nothing."""

import pytest

from dino_autofocus.engine.patterns import (
    MAX_TRAPS,
    PIEZO_RANGE_UM,
    PatternError,
    Point,
    pattern_from_dict,
)


def square(target="piezo", side=10.0, period=4.0):
    s = side
    return {"target": target, "points": [[0, 0, 0, 0], [period / 4, s, 0, 0],
                                         [period / 2, s, s, 0], [3 * period / 4, 0, s, 0],
                                         [period, 0, 0, 0]]}


def test_a_pattern_round_trips_and_interpolates():
    p = pattern_from_dict({"id": "sq-1", "name": "  Square   piezo ", "loop": True,
                           "tracks": [square(), square("trap:0", 5.0, 2.0)]})
    assert p.name == "Square piezo" and p.duration_s == 4.0
    assert p.tracks[0].at(0.5) == Point(0.5, 5.0, 0.0, 0.0)
    assert p.tracks[1].at(3.0) == p.tracks[1].points[-1]  # a shorter track holds its end
    assert p.at(5.0)["piezo"] == Point(1.0, 10.0, 0.0, 0.0)  # loop wraps at 4 s
    assert pattern_from_dict(p.to_dict()) == p


def test_points_may_be_short_lists_or_objects():
    p = pattern_from_dict({"id": "z", "tracks": [{"target": "piezo", "points": [
        [0], {"t_s": 1, "z_um": 2.5}]}]})
    assert p.tracks[0].points == (Point(0.0), Point(1.0, 0.0, 0.0, 2.5))


@pytest.mark.parametrize(("track", "says"), [
    ({"target": "stage", "points": [[0]]}, "target must be"),
    ({"target": f"trap:{MAX_TRAPS}", "points": [[0]]}, "trap"),
    ({"target": "piezo", "points": []}, "no points"),
    ({"target": "piezo", "points": [[0.5, 0, 0, 0]]}, "t = 0"),
    ({"target": "piezo", "points": [[0], [1], [1]]}, "time must go up"),
    ({"target": "piezo", "points": [[0], [1, PIEZO_RANGE_UM["x"][1] + 1]]}, "provisional piezo"),
    ({"target": "trap:1", "points": [[0], [1, 0, -61]]}, "provisional trap:1"),
    ({"target": "piezo", "points": [[0], [1, float("nan")]]}, "finite"),
    ({"target": "piezo", "points": [[0], [4000]]}, "at most"),
])
def test_bad_tracks_are_refused_with_the_reason(track, says):
    with pytest.raises(PatternError, match=says):
        pattern_from_dict({"id": "bad", "tracks": [track]})


def test_bad_patterns_are_refused():
    for bad_id in ("Has Space", "abc\n", "../x"):
        with pytest.raises(PatternError, match="id"):
            pattern_from_dict({"id": bad_id, "tracks": [square()]})
    with pytest.raises(PatternError, match="one track only"):
        pattern_from_dict({"id": "dup", "tracks": [square(), square()]})
    with pytest.raises(PatternError, match="at least one track"):
        pattern_from_dict({"id": "none", "tracks": []})
    with pytest.raises(PatternError, match="version"):
        pattern_from_dict({"id": "v", "version": 2, "tracks": [square()]})
