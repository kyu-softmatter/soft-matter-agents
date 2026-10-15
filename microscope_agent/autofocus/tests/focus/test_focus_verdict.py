"""Both verdict mappings, every branch; the verdict z is always a real frame's encoder z."""

import json
from dataclasses import dataclass, field

import numpy as np
import pytest

from dino_autofocus.focus import FrameStats, Verdict, from_reading, from_sweep, verdict_model


def stats_for(scores, means=None, sat=None, dyn=500.0):
    n = len(scores)
    means = means or [1000.0] * n
    sat = sat or [0.0] * n
    return [FrameStats(score=float(s), metric="vollath4", mean=m, median=m - 5, p999=m - 5 + dyn,
                       max=int(m + dyn), saturated_fraction=f)
            for s, m, f in zip(scores, means, sat, strict=True)]


# encoder readbacks: not round numbers, as on the bench (3037 commanded / 3036.x read)
Z = [3036.02, 3038.05, 3039.97, 3042.01, 3044.03, 3045.98, 3048.04]


def test_interior_peak_is_in_focus_at_the_nearest_real_frame():
    s = [1.0, 2.0, 3.0, 4.0, 3.6, 2.0, 1.0]  # vertex a little above Z[3]
    v = from_sweep(Z, stats_for(s))
    assert v.verdict is Verdict.IN_FOCUS and v.source == "sweep"
    assert v.z_um in Z and v.frame_index == 3 and v.z_um == Z[3]
    vertex = next(e for e in v.evidence if e.name == "z_vertex_um")
    assert vertex.grade == "computed" and vertex.value != v.z_um
    assert not verdict_model.has_model_numbers(v)


def test_peak_at_top_is_step_up_and_at_bottom_step_down():
    up = from_sweep(Z, stats_for([1, 2, 3, 4, 5, 6, 7]))
    assert up.verdict is Verdict.STEP_UP and up.z_um == Z[-1]
    down = from_sweep(Z, stats_for([7, 6, 5, 4, 3, 2, 1]))
    assert down.verdict is Verdict.STEP_DOWN and down.z_um == Z[0]


def test_dark_frames_are_no_sample_here():
    v = from_sweep(Z, stats_for([0.1, 0.3, 0.2, 0.1, 0.2, 0.3, 0.1], means=[102.0] * 7,
                                dyn=6.0))
    assert v.verdict is Verdict.NO_SAMPLE_HERE and v.z_um is None


def test_flat_curve_is_unsure():
    v = from_sweep(Z, stats_for([5.0, 5.01, 5.0, 5.02, 5.0, 5.01, 5.0]))
    assert v.verdict is Verdict.UNSURE and "flat" in v.reason


def test_too_few_readable_frames_is_unsure():
    sat = [0.0, 0.01, 0.01, 0.01, 0.01, 0.01, 0.0]  # in-focus frames clipped
    v = from_sweep(Z, stats_for([1, 2, 3, 4, 3, 2, 1], sat=sat))
    assert v.verdict is Verdict.UNSURE and "readable" in v.reason
    assert from_sweep([], []).verdict is Verdict.UNSURE
    with pytest.raises(ValueError):
        from_sweep(Z[:2], stats_for([1.0]))


def test_dropout_frame_does_not_become_the_peak():
    s = [1.0, 2.0, 3.0, 4.0, 3.0, 9.0, 1.0]
    means = [1000.0, 1000.0, 1000.0, 1000.0, 1000.0, 770.0, 1000.0]
    v = from_sweep(Z, stats_for(s, means=means))
    assert v.verdict is Verdict.IN_FOCUS and v.z_um == Z[3]
    assert "dropout" in v.reason


def test_sweep_record_is_json_ready():
    rec = from_sweep(Z, stats_for([1, 2, 3, 4, 3, 2, 1])).as_record()
    back = json.loads(json.dumps(rec))
    assert back["verdict"] == "in_focus" and back["z_grade"] == "measured"
    assert {e["grade"] for e in back["evidence"]} <= {"measured", "computed", "model"}


@dataclass
class Reading:  # same fields as dino_autofocus.live.FocusReading
    score: float | None
    sigma: float | None
    n_used: int
    tiles: list = field(default_factory=list)

    @property
    def sign_known(self):
        return self.score is not None and self.sigma is not None and abs(self.score) > self.sigma


TILES = [object(), object()]


@pytest.mark.parametrize("reading, expected", [
    (Reading(None, None, 0, []), Verdict.NO_SAMPLE_HERE),
    (Reading(None, None, 0, TILES), Verdict.UNSURE),            # tiles, none readable
    (Reading(0.5, 4.0, 2, TILES), Verdict.UNSURE),              # sigma too large
    (Reading(float("nan"), 1.0, 2, TILES), Verdict.UNSURE),
    (Reading(-0.8, 0.5, 2, TILES), Verdict.IN_FOCUS),
    (Reading(3.0, 1.0, 2, TILES), Verdict.STEP_DOWN),           # stage above focus
    (Reading(-3.0, 1.0, 2, TILES), Verdict.STEP_UP),            # stage below focus
    (Reading(2.0, 2.5, 2, TILES), Verdict.UNSURE),              # |dz| <= sigma
])
def test_reading_branches(reading, expected):
    v = from_reading(reading, z_um=2988.45, frame_index=7)
    assert v.verdict is expected and v.source == "dino"
    assert v.z_um == 2988.45 and v.frame_index == 7  # the caller's encoder z, not dz
    assert verdict_model.has_model_numbers(v)
    assert {e.name for e in v.evidence if e.grade == "model"} >= {"dz", "sigma"}
    json.dumps(v.as_record())


def test_real_focus_reading_fits_the_protocol():
    pytest.importorskip("torch")  # the ml extra (live imports the backbone)
    from dino_autofocus.live import FocusReading, Tile

    r = FocusReading(score=-2.5, sigma=0.8, n_used=1, tiles=[Tile(0, 0, 1.0)])
    assert from_reading(r, z_um=np.float64(3000.0)).verdict is Verdict.STEP_UP
