"""The DINO wrapper maps a reading to a verdict; importing the package pulls in no torch."""

import subprocess
import sys

import numpy as np
import pytest

from dino_autofocus.focus import DinoVerdict, Verdict


class FakeReading:
    def __init__(self, score, sigma, where="box"):
        self.score, self.sigma, self.n_used, self.tiles, self.where = score, sigma, 1, [0], where

    @property
    def sign_known(self):
        return abs(self.score) > self.sigma


def test_wrapper_passes_region_and_reports_where():
    seen = {}

    def scorer(img, region=None):
        seen["region"], seen["shape"] = region, img.shape
        return FakeReading(4.0, 1.0)

    v = DinoVerdict(scorer)(np.zeros((32, 32), np.uint16), z_um=3001.5, frame_index=2,
                            region=(0, 0, 16))
    assert seen == {"region": (0, 0, 16), "shape": (32, 32)}
    assert v.verdict is Verdict.STEP_DOWN and v.z_um == 3001.5 and "[box]" in v.reason


def test_wrapper_thresholds_are_passed_on():
    v = DinoVerdict(lambda img, region=None: FakeReading(1.5, 0.5), in_focus_dof=2.0)(
        np.zeros((4, 4), np.uint16), z_um=0.0)
    assert v.verdict is Verdict.IN_FOCUS


def test_import_does_not_load_torch():
    code = ("import sys, dino_autofocus.focus; "
            "bad = {'torch', 'dino_autofocus.live', 'dino_autofocus.backbone'} & set(sys.modules); "
            "assert not bad, bad")
    subprocess.run([sys.executable, "-c", code], check=True)


def test_from_head_loads_the_real_scorer_lazily(tmp_path):
    pytest.importorskip("torch")  # the ml extra (live imports the backbone)
    with pytest.raises(FileNotFoundError):
        DinoVerdict.from_head(tmp_path / "missing.joblib")
