"""Card 086 item 5: a check-now run over the whole mock.

    python -m unittest tests.test_check_now_whole_mock

A check-now list in a test's temporary folder can name every registry channel the person's motion
set leaves open, and the console's "check now" opens, reads and closes each of them on the mock and
sends nothing. The mock needed nothing added for this beyond what card 085 gave it (open_for and
close_for); these tests are what show it, and the planted defects in the commit message show they
can go red. Every list is a TEST FIXTURE in a temporary approvals/ folder and the status file goes
to a temporary folder; nothing here writes microscope_runtime/.runtime_status/ or the person's real
check-now list.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_idle_status_and_check_now as t85                    # noqa: E402  (its _Base builds the host)

op = t85.op
orch = t85.orch
_with_channels = t85._with_channels


def inert_channels() -> list[str]:
    """Every registry channel a check-now list may name: all of them but the motion set."""
    o = orch.Orchestrator(backend="mock")
    return [c for c in o.channels if c not in op.CHECK_NOW_MOTION_SET]


def mock_of(o):
    return o.module_for("camera_red")


class _Whole(t85._Base):
    def events(self, log, name):
        return [e for e in log["events"] if e.get("event") == name]


class CheckNowOverTheWholeMock(_Whole):
    def test_every_channel_the_motion_set_leaves_open_is_opened_read_and_closed(self):
        ids = inert_channels()
        self.assertGreaterEqual(len(ids), 8, ids)               # the registry's inert channels
        self.host.start()
        reply = self.check_now(self.write_list(_with_channels(*ids)))
        self.assertEqual(reply["check_now"], "started", reply)
        log = self.wait_run(reply["run_id"])
        self.assertEqual(log["ended"], "completed")
        self.assertEqual([e["channel"] for e in self.events(log, "check_now_open")], ids)
        self.assertEqual([e["channel"] for e in self.events(log, "check_now_read")], ids)
        self.assertEqual([e["channel"] for e in self.events(log, "check_now_close")], ids)
        self.assertEqual(self.events(log, "check_now_step_failed"), [])
        self.assertEqual(self.opened, ids)
        sent = [e for e in log["events"] if e.get("event") in ("apply", "apply_failed", "dispatch")]
        self.assertEqual(sent, [], "a check-now run has no apply and no dispatch")
        self.assertEqual(mock_of(self.orchestrators[0]).open_channels(), [],
                         "every channel the run opened was closed")

    def test_each_channel_is_open_while_it_is_read_and_no_other_is(self):
        ids = inert_channels()
        seen = []

        def hook(o):
            self._hook(o)
            mock = mock_of(o)
            real = mock.read_for

            def spy(cid, *a, **k):
                seen.append((cid, mock.open_channels()))
                return real(cid, *a, **k)
            mock.read_for = spy
        self.on_orchestrator = hook
        self.host.start()
        reply = self.check_now(self.write_list(_with_channels(*ids)))
        self.wait_run(reply["run_id"])
        self.assertEqual([c for c, _ in seen if c in ids][:len(ids)], ids)
        for cid, held in seen:
            if cid in ids:
                self.assertEqual(held, [cid], f"{cid} is read with exactly itself open")

    def test_the_mock_is_asked_for_no_command_at_all(self):
        ids = inert_channels()
        calls = []

        def hook(o):
            self._hook(o)
            mock = mock_of(o)
            for name in ("apply", "apply_for", "close_for_abort", "focus_z_move"):
                real = getattr(mock, name)
                setattr(mock, name, lambda *a, __n=name, __r=real, **k: (calls.append(__n), __r(*a, **k))[1])
        self.on_orchestrator = hook
        self.host.start()
        reply = self.check_now(self.write_list(_with_channels(*ids)))
        self.wait_run(reply["run_id"])
        self.assertEqual(calls, [])

    def test_the_status_file_shows_each_of_them_as_the_run_read_it(self):
        ids = inert_channels()
        self.host.start()
        reply = self.check_now(self.write_list(_with_channels(*ids)))
        self.wait_run(reply["run_id"])
        doc = self.status()
        self.assert_status_valid(doc)
        rows = doc["check_now"]["channels"]
        self.assertEqual([r["channel"] for r in rows], ids)
        for row in rows:
            self.assertTrue(row["opened"] and row["closed"], row)
            self.assertNotIn("error", row)
            self.assertIn(row["how"], ("read_back", "not_readable"), row)
        # a channel the registry says has no read-back is shown as such, never with a read value
        blind = {c: ch.read_back for c, ch in self.orchestrators[0].channels.items()}
        for row in rows:
            self.assertEqual(row["how"], "read_back" if blind[row["channel"]] else "not_readable", row)

    def test_a_list_names_only_what_it_lists(self):
        self.host.start()
        reply = self.check_now(self.write_list(_with_channels("dmd", "camera_blue")))
        log = self.wait_run(reply["run_id"])
        self.assertEqual(self.opened, ["dmd", "camera_blue"])
        self.assertEqual([e["channel"] for e in self.events(log, "check_now_read")], ["dmd", "camera_blue"])


if __name__ == "__main__":
    unittest.main()
