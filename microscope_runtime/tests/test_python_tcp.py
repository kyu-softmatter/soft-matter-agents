"""Card 037's rules for the tweezers module, against a scripted fake GUI.

The fake is one end of a socketpair, so no port is opened and no Tweez300
process is involved. Run: python -m unittest microscope_agent/tests/test_python_tcp.py
"""

from __future__ import annotations

import importlib.util
import socket
import tempfile
import threading
import unittest
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "src" / "devices" / "python_tcp.py"
_spec = importlib.util.spec_from_file_location("python_tcp_under_test", _PATH)
tcp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tcp)


class FakeGUI:
    """Answers each received line with the next scripted reply; None is silence."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.received: list[str] = []
        self.ours, self._theirs = socket.socketpair()
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        buf = b""
        try:
            while True:
                chunk = self._theirs.recv(1024)
                if not chunk:
                    return
                buf += chunk
                while b"\r\n" in buf:
                    line, buf = buf.split(b"\r\n", 1)
                    self.received.append(line.decode())
                    reply = self.replies.pop(0) if self.replies else None
                    if reply is not None:
                        self._theirs.sendall(f"{reply}\r\n".encode())
        except OSError:
            return


def link(gui: FakeGUI, log: Path, busy_retries=3) -> "tcp.Link":
    return tcp.Link("fake", 0, connect_timeout_s=1, reply_timeout_s=0.3, min_gap_s=0,
                    busy_retries=busy_retries, busy_backoff_s=0, log_path=log,
                    numbers_from="test scaffolding, not a measurement", sock=gui.ours)


class Rules(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.log = Path(self.dir.name) / "exchanges.jsonl"

    def tearDown(self):
        self.dir.cleanup()

    def test_a_zero_is_not_a_verification(self):
        gui = FakeGUI([0])
        entry = link(gui, self.log).send("TRAP_POSITION", "t1", 1.0, 2.0)
        self.assertEqual(entry["outcome"], "accepted")
        self.assertEqual(entry["verification"], "none")
        self.assertIn('"verification": "none"', self.log.read_text())

    def test_every_dispatch_records_no_verification_whatever_came_back(self):
        gui = FakeGUI([0, -25, -27])
        lk = link(gui, self.log)
        for _ in range(3):
            self.assertEqual(lk.send("TRAP_OFF", "t1")["verification"], "none")

    def test_a_missing_reply_is_never_resent(self):
        gui = FakeGUI([None, 0])
        lk = link(gui, self.log)
        with self.assertRaises(tcp.NoReply):
            lk.send("TRAP_POSITION_REL", "t1", 1.0, 0.0)
        self.assertEqual(gui.received, ["TRAP_POSITION_REL t1 1.0 0.0"])

    def test_after_a_silence_nothing_but_the_safe_direction_goes_out(self):
        gui = FakeGUI([None, 0])
        lk = link(gui, self.log)
        with self.assertRaises(tcp.NoReply):
            lk.send("TRAP_POSITION_REL", "t1", 1.0, 0.0)
        with self.assertRaises(tcp.Refused):
            lk.send("TRAP_POSITION_REL", "t1", 1.0, 0.0)
        self.assertEqual(len(gui.received), 1)
        self.assertEqual(lk.send("TRAP_OFF", "t1")["outcome"], "accepted")
        lk.acknowledge_unknown(by="test", observed="trap moved once")
        gui.replies.append(0)
        self.assertEqual(lk.send("TRAP_ON", "t1")["outcome"], "accepted")

    def test_an_explicit_busy_is_resent(self):
        gui = FakeGUI([tcp.BUSY, tcp.BUSY, 0])
        entry = link(gui, self.log).send("SIMPLE_TRAP_CREATE", "t1")
        self.assertEqual(entry["outcome"], "accepted")
        self.assertEqual(len(gui.received), 3)

    def test_busy_resends_stop_at_the_callers_count(self):
        gui = FakeGUI([tcp.BUSY] * 5)
        entry = link(gui, self.log, busy_retries=2).send("SIMPLE_TRAP_CREATE", "t1")
        self.assertEqual(entry["outcome"], "rejected")
        self.assertEqual(len(gui.received), 3)

    def test_laser_on_is_refused_before_anything_is_sent(self):
        gui = FakeGUI([0])
        with self.assertRaises(tcp.Refused):
            link(gui, self.log).send("LASER_ON")
        self.assertEqual(gui.received, [])

    def test_an_unwrapped_command_is_refused_before_anything_is_sent(self):
        gui = FakeGUI([0])
        with self.assertRaises(tcp.Refused):
            link(gui, self.log).send("LOAD_PROJECT", "x.tpj")
        self.assertEqual(gui.received, [])

    def test_after_abort_the_beam_is_assumed_on_even_when_laser_off_answered_zero(self):
        gui = FakeGUI([0, 0])
        tcp._LINK = link(gui, self.log)
        try:
            tcp._LINK.person_shows_beam_blocked(by="test", observed="shutter closed")
            out = tcp.abort(traps=["t1"])
            self.assertEqual([e["outcome"] for e in out["dispatched"]], ["accepted", "accepted"])
            self.assertEqual(out["beam"]["state"], "assumed on")
            self.assertEqual(tcp.read()["beam"]["state"], "assumed on")
        finally:
            tcp._LINK = None

    def test_a_person_saying_blocked_holds_only_until_the_next_command(self):
        gui = FakeGUI([0])
        lk = link(gui, self.log)
        lk.person_shows_beam_blocked(by="test", observed="laser off at the hand control")
        self.assertEqual(lk.beam["shown_blocked_by"], "test")
        self.assertEqual(lk.send("TRAP_OFF", "t1")["beam"]["state"], "assumed on")

    def test_a_pattern_file_is_the_vendors_format(self):
        out = tcp.write_pattern(Path(self.dir.name) / "p.tpf", [(1, 0, 1), (0, -1, 0.5)])
        self.assertTrue(out.is_absolute())
        self.assertEqual(out.read_bytes(),
                         b"colX\tcolY\tcolStr\r\n1.0000\t0.0000\t1.0000\r\n"
                         b"0.0000\t-1.0000\t0.5000\r\n")

    def test_a_pattern_strength_outside_zero_to_one_is_refused(self):
        with self.assertRaises(tcp.Refused):
            tcp.write_pattern(Path(self.dir.name) / "p.tpf", [(0, 0, 1.5)])

    def test_readiness_codes_are_theirs_until_measured_here(self):
        for status in (0, -22, -25):
            answer = tcp.classify(status)
            self.assertEqual(answer["means"], "up")
            self.assertFalse(answer["measured_here"])
            self.assertIn("agentic-microscope", answer["source"])

    def test_an_objective_change_makes_both_calibrations_unknown(self):
        gui = FakeGUI([0])
        lk = link(gui, self.log)
        lk.confirm_calibration(by="test", objective="60x", pixel_to_um="done by hand",
                               aod_field="done by hand")
        lk.objective_changed(to="20x")
        entry = lk.send("TRAP_POSITION", "t1", 1.0, 2.0)
        self.assertEqual(entry["calibration"]["pixel_to_um"], "unknown")
        self.assertEqual(entry["calibration"]["aod_field"], "unknown")


if __name__ == "__main__":
    unittest.main()
