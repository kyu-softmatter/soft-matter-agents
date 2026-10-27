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


class T2TheExposureStepOption(unittest.TestCase):
    """Card 096: the option that asks for the one writing part, three values or nothing."""

    run_cli = T1TheCommandLineRefusesWithExitTwo.run_cli

    def test_the_step_is_off_unless_named(self):
        seen = {}

        def fake(run_id, **kw):
            seen.update(kw)
            raise cli.op.Refusal("stopped here")

        real = cli.op.run_device_reading
        cli.op.run_device_reading = fake
        try:
            self.run_cli("--run-id", "run-test-096-cli", "--mm-config", "x.cfg")
        finally:
            cli.op.run_device_reading = real
        self.assertIsNone(seen["exposure_step"])

    def test_three_values_are_passed_through_as_numbers(self):
        seen = {}

        def fake(run_id, **kw):
            seen.update(kw)
            raise cli.op.Refusal("stopped here")

        real = cli.op.run_device_reading
        cli.op.run_device_reading = fake
        try:
            self.run_cli("--run-id", "run-test-096-cli", "--mm-config", "x.cfg", "--exposure-step", "5", "20", "80")
        finally:
            cli.op.run_device_reading = real
        self.assertEqual(list(seen["exposure_step"]), [5.0, 20.0, 80.0])

    def test_two_values_are_refused_by_the_parser_before_anything_runs(self):
        with self.assertRaises(SystemExit) as caught:
            self.run_cli("--run-id", "run-test-096-cli", "--mm-config", "x.cfg", "--exposure-step", "5", "20")
        self.assertEqual(caught.exception.code, 2)

    def test_a_non_positive_value_is_refused_with_exit_two_and_leaves_no_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            code, err = self.run_cli("--run-id", "run-test-096-cli", "--mm-config", str(Path(tmp) / "x.cfg"),
                                     "--runs-root", str(runs), "--exposure-step", "5", "0", "80")
            left = list(runs.glob("*")) if runs.exists() else []
        self.assertEqual(code, 2)
        self.assertIn("positive", err)
        self.assertEqual(left, [])

    def test_a_refused_step_exits_nonzero(self):
        record = {"run_id": "r", "ended": "failed", "approved_commands": {"sha256": "0" * 64},
                  "events": [{"event": "exposure_step_refused", "why": "Aura (Aura III) reads '1' (on)"}]}
        real = cli.op.run_device_reading
        cli.op.run_device_reading = lambda run_id, **kw: record
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                code = cli.main(["--run-id", "r", "--mm-config", "x.cfg", "--exposure-step", "5", "20", "80"])
        finally:
            cli.op.run_device_reading = real
        self.assertEqual(code, 1)
        self.assertIn("REFUSED", out.getvalue())
        self.assertIn("Aura", out.getvalue())


if __name__ == "__main__":
    unittest.main()
