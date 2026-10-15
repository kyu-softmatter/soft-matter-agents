"""The live -10..+10 gauge reading (engine/live_dz.py): the mock's truth and the DINO reader."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
import pytest

from dino_autofocus.engine.backends.mock import MockBackend
from dino_autofocus.engine.live_dz import DzReader, focus_dz, truth_dz


@dataclass
class Tile:  # the fields DzReader uses of dino_autofocus.live.Tile (that module loads torch)
    y0: int
    x0: int
    signal: float


@dataclass
class FocusReading:  # likewise dino_autofocus.live.FocusReading
    score: float | None
    sigma: float | None
    n_used: int
    tiles: list = field(default_factory=list)
    where: str = "frame"

    @property
    def sign_known(self) -> bool:
        return self.score is not None and self.sigma is not None and abs(self.score) > self.sigma


def test_mock_frames_carry_the_true_dz_in_depths_of_field():
    b = MockBackend(seed=1)
    b.open()
    try:
        b.set_roi(64)
        w = b.world
        dof = w.objective.dof_um
        w.move_z(w.in_focus_z() + 2.5 * dof)  # test set-up, as at_sample() in test_backends_mock
        assert b.snap().dz_truth_dof == pytest.approx(2.5)
        w.move_z(w.in_focus_z() - 4 * dof)
        assert b.snap().dz_truth_dof == pytest.approx(-4.0)  # below focus: negative
    finally:
        b.all_off()
        b.close()


def test_truth_and_empty_readings():
    t = truth_dz(-3.25)
    assert t == {"dz_dof": -3.25, "sigma_dof": None, "source": "mock_truth",
                 "note": "mock truth, not a measurement", "sign_known": True}
    nan = focus_dz(float("nan"), 0.5, "model", "x")
    assert nan["dz_dof"] is None and nan["sign_known"] is False
    assert focus_dz(0.3, 0.8, "model")["sign_known"] is False  # within sigma: side unknown


class Scripted:
    """A FocusScorer stand-in that returns the next score of a list (None: nothing readable)."""

    def __init__(self, scores):
        self.scores = list(scores)

    def __call__(self, img):
        s = self.scores.pop(0)
        if isinstance(s, Exception):
            raise s
        tiles = [Tile(0, 0, 1.0), Tile(0, 224, 1.0)]
        return FocusReading(s, None if s is None else 0.5, 0 if s is None else 2, tiles)


def test_reader_shows_the_median_of_the_last_five():
    r = DzReader(Scripted([1.0, 9.0, 2.0, 3.0, 2.5, 8.0, 7.0]))
    img = np.zeros((4, 4), np.uint16)
    outs = [r.read_now(img) for _ in range(7)]
    assert [o["dz_dof"] for o in outs[:3]] == [1.0, 5.0, 2.0]
    assert outs[4]["dz_dof"] == 2.5  # median of 1, 9, 2, 3, 2.5
    assert outs[6]["dz_dof"] == 3.0  # median of 2, 3, 2.5, 8, 7: the 1.0 and 9.0 left
    assert outs[6]["source"] == "model" and outs[6]["note"] == "frame: 2/2 tiles"
    assert r.latest() == outs[6]


def test_reader_empty_view_resets_and_a_failure_is_shown():
    r = DzReader(Scripted([4.0, None, -2.0, RuntimeError("cuda")]))
    img = np.zeros((4, 4), np.uint16)
    r.read_now(img)
    empty = r.read_now(img)
    assert empty["dz_dof"] is None and empty["note"] == "no readable sample in view"
    assert r.read_now(img)["dz_dof"] == -2.0  # the 4.0 before the gap is not in the median
    bad = r.read_now(img)
    assert bad["dz_dof"] is None and bad["note"] == "reading failed: RuntimeError"


def test_reader_thread_scores_the_newest_frame():
    seen = []

    def scorer(img):
        seen.append(int(img[0, 0]))
        return FocusReading(float(img[0, 0]), 0.5, 1, [Tile(0, 0, 1.0)])

    r = DzReader(scorer)
    try:
        assert r.feed(np.full((2, 2), 3, np.uint16)) is None  # nothing read yet
        deadline = time.monotonic() + 5
        while r.latest() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert r.latest()["dz_dof"] == 3.0 and seen == [3]
    finally:
        r.stop()
