"""Mock snapshots that get sharper toward a focus Z, so a focus search on mock can find it (card 063).

    python -m unittest microscope_agent/tests/test_mock_focus_frames.py

With FRAME_SHAPE and FOCUS_Z_UM set, mock.snap() returns a 2-D uint16 frame
whose structure is strongest at FOCUS_Z_UM and fades into a fixed noise
floor away from it. The copied core's own score then peaks there. Defaults
are unchanged: snap() returns 64 bytes. The values are synthetic, and say
nothing about any real objective or sample.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

try:
    import numpy
except ImportError:                                             # pragma: no cover
    numpy = None


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


mock = _load("_mock_focus_frames_under_test", SRC / "devices" / "mock.py")


class MockSnap(unittest.TestCase):
    def setUp(self):
        mock.reset()
        self.addCleanup(lambda: (setattr(mock, "FRAME_SHAPE", None),
                                 setattr(mock, "FOCUS_Z_UM", None)))

    def test_default_snap_is_unchanged(self):
        image, meta = mock.snap()
        self.assertEqual(image, bytes(64))

    @unittest.skipIf(numpy is None, "numpy is not installed")
    def test_sharpest_at_the_focus_z(self):
        classical = _load("_classical_for_mock_focus", SRC / "focus_classical.py")
        mock.FRAME_SHAPE, mock.FOCUS_Z_UM = (64, 64), 105.0
        scores = {}
        for z in (95.0, 100.0, 105.0, 110.0):
            mock.focus_z_move(z)
            image, meta = mock.snap()
            self.assertEqual((image.shape, str(image.dtype)), ((64, 64), "uint16"))
            scores[z] = classical.score(image, "vollath4")
        self.assertEqual(max(scores, key=scores.get), 105.0, scores)
        self.assertGreater(scores[100.0], scores[95.0])


if __name__ == "__main__":
    unittest.main()
