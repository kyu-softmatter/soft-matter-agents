"""Mock frames a viewer can draw, and the host's mock-only flags (card 063 step 1).

    python -m unittest microscope_agent/tests/test_live_view_mock_frames.py

The mock's default frames are 64 bytes with no image shape, which the
console cannot draw (it said so in card 061). With FRAME_SHAPE set, and
numpy installed, the mock produces 2-D uint16 frames whose pattern moves with
the frame index, so a person watching sees a live view that changes. The
default is unchanged. The live-view host's --mock-frame-shape and
--mock-frame-delay set them, and refuse with any backend but mock.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


mock = _load("_mock_frames_under_test", SRC / "devices" / "mock.py")
lv = _load("_live_view_flags_under_test", SRC / "live_view.py")

try:
    import numpy
except ImportError:                                             # pragma: no cover
    numpy = None


class MockFrames(unittest.TestCase):
    def setUp(self):
        mock.reset()
        self.addCleanup(setattr, mock, "FRAME_SHAPE", None)

    def test_default_frames_are_unchanged(self):
        got = []
        mock.sequence(2, lambda i, img, md: got.append(img))
        self.assertEqual(got, [bytes([0]) * 64, bytes([1]) * 64])

    @unittest.skipIf(numpy is None, "numpy is not installed")
    def test_a_shape_gives_2d_uint16_frames_that_change(self):
        mock.FRAME_SHAPE = (32, 48)
        got = []
        mock.sequence(3, lambda i, img, md: got.append(img))
        self.assertEqual((got[0].shape, str(got[0].dtype)), ((32, 48), "uint16"))
        self.assertFalse(numpy.array_equal(got[0], got[1]))


class HostFlags(unittest.TestCase):
    def test_mock_flags_refuse_with_another_backend(self):
        import contextlib
        import io
        for flag in (["--mock-frame-shape", "64x64"], ["--mock-frame-delay", "0.1"]):
            err = io.StringIO()
            with self.assertRaises(SystemExit) as caught, contextlib.redirect_stderr(err):
                lv.main(["--backend", "micromanager", *flag])
            self.assertNotEqual(caught.exception.code, 0, flag)
            # the refusal is the host's own, not argparse rejecting an unknown flag
            self.assertIn("only with --backend mock", err.getvalue(), flag)

    def test_the_shape_flag_parses(self):
        self.assertEqual(lv.parse_shape("256x320"), (256, 320))
        for bad in ("256", "0x10", "ax2", "10x10x10"):
            with self.assertRaises(ValueError, msg=bad):
                lv.parse_shape(bad)


if __name__ == "__main__":
    unittest.main()
