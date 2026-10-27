"""Card 092: the command line over the device reading refuses before it loads anything.

    python -m unittest microscope_runtime/tests/test_read_devices_cli.py

Only refusals are run here, because a run needs a core. The run itself is held by
test_device_reading_run.py against a fake one.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import tempfile
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


cli = _load("_read_devices_card092_under_test", SRC / "read_devices.py")


class T1TheCommandLineRefusesWithExitTwo(unittest.TestCase):
    def run_cli(self, *argv):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = cli.main(list(argv))
        return code, err.getvalue()

    def test_the_mock_backend_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "x.cfg"
            cfg.write_text("# not approved\n")
            code, err = self.run_cli("--run-id", "run-test-092-cli", "--mm-config", str(cfg), "--backend", "mock")
        self.assertEqual(code, 2)
        self.assertIn("REFUSED", err)
        self.assertIn("mock", err)

    def test_a_file_nobody_approved_is_refused_and_leaves_no_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "x.cfg"
            cfg.write_text("# not approved\n")
            runs = Path(tmp) / "runs"
            code, err = self.run_cli("--run-id", "run-test-092-cli", "--mm-config", str(cfg),
                                     "--runs-root", str(runs))
            left = list(runs.glob("*")) if runs.exists() else []
        self.assertEqual(code, 2)
        self.assertIn("approved list", err)
        self.assertEqual(left, [])


if __name__ == "__main__":
    unittest.main()
