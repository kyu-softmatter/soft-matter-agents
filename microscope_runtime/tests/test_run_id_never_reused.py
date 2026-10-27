"""Card 086 tests 9-11: a run id is never reused.

    python -m unittest tests.test_run_id_never_reused

Card 085 gave the runs the live-view host starts the ids run-YYYYMMDD-900 to -999. What keeps them
apart from the ids a plan run is given is the run folder: operator.py refuses a folder that exists,
in the plan run, the live view and the check-now run, and the host's _next_run_id skips any id whose
folder exists. The run lock is taken before an id is used, so two runs cannot meet in flight. A plan
run without --write makes no folder, so a repeated id there collides with nothing, and no refusal
by range is wanted for it.

Mock only. Every folder, list and status file is in a temporary directory; nothing here writes
microscope_runtime/runs/ or .runtime_status/.
"""

from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_idle_status_and_check_now as t85                    # noqa: E402  (its _Base builds the host)

op = t85.op
orch = t85.orch
lock_mod = t85.lock_mod

TODAY = datetime.now().strftime("%Y%m%d")
PLAN = {"card": "plan", "id": "plan-test-086-runid", "revision": 1,
        "numbers": [{"name": "n", "value": 1, "unit": "1", "source": "test", "grade": "E5"}],
        "actions": [{"id": "a_red", "tier": 0, "device": "camera_red", "action": "acquire", "reversible": True}],
        "stop_criteria": [{"id": "n", "number": "n", "metric": "n", "comparator": ">="}]}
SENT = ("open_for", "apply_for", "read_for", "snap_for", "sequence_for")


def tree(folder: Path) -> dict:
    """Every file under a folder by relative path, with its bytes: what 'byte-identical' compares."""
    return {str(p.relative_to(folder)): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()}


class _RunIds(t85._Base):
    def setUp(self):
        super().setUp()
        # Until the software-motion check resolves a registry name to its Micro-Manager label (card
        # 091) it refuses a plan naming a camera. This lets that one check pass and changes nothing else.
        real = orch.Orchestrator.check_software_motion_for
        orch.Orchestrator.check_software_motion_for = lambda o, plan, commands: None
        self.addCleanup(setattr, orch.Orchestrator, "check_software_motion_for", real)
        self.sent = []                                          # every call that would reach a device
        self.plan_path = Path(self.tmp.name) / "plan.json"
        self.plan_path.write_text(json.dumps(PLAN), encoding="utf-8")
        self.runs.mkdir()

    def _hook(self, o):
        super()._hook(o)
        mock = o.module_for("camera_red")
        for name in SENT:
            real = getattr(mock, name)
            setattr(mock, name, lambda *a, __n=name, __r=real, **k: (self.sent.append(__n), __r(*a, **k))[1])

    def plan_run(self, run_id):
        return op.run(self.plan_path, run_id, backend="mock", observe=lambda m: 9.0, runs_root=self.runs,
                      status_dir=self.status_dir, on_orchestrator=self.on_orchestrator)

    def live_run(self, run_id):
        path = self.approvals / "live.json"
        path.write_text(json.dumps(t85.LIVE_LIST), encoding="utf-8")
        return op.run_live_view(path, run_id, runs_root=self.runs, backend="mock",
                                on_orchestrator=self.on_orchestrator, status_dir=self.status_dir)

    def check_now_run(self, run_id):
        path = self.approvals / "check-now.json"
        path.write_text(json.dumps(t85.CHECK_NOW_LIST), encoding="utf-8")
        return op.run_check_now(path, run_id, runs_root=self.runs, backend="mock",
                                on_orchestrator=self.on_orchestrator, status_dir=self.status_dir)

    def occupied(self, run_id) -> Path:
        """A folder an earlier run left under this id, with a file in it that nothing may touch."""
        folder = self.runs / run_id
        (folder / "inner").mkdir(parents=True)
        (folder / "log.json").write_bytes(b'{"kept": "as the earlier run left it"}\r\n')
        (folder / "inner" / "frame.bin").write_bytes(bytes(range(256)))
        return folder

    def assert_lock_free(self):
        lock = lock_mod.RunLock(self.lock_path)
        lock.acquire({"kind": "test", "run_id": "probe"})       # raises RunLockHeld if the refusal kept it
        lock.release()


# --------------------------------------------------------------------------- #
# 9. a plan run with --write into an existing 9NN folder is refused
# --------------------------------------------------------------------------- #

class T9ARepeatedHostRangeIdIsRefusedAtThePlanRun(_RunIds):
    def test_the_refusal_comes_before_any_command_and_the_folder_is_untouched(self):
        run_id = f"run-{TODAY}-905"
        folder = self.occupied(run_id)
        before = tree(folder)
        with self.assertRaises(op.Refusal) as caught:
            self.plan_run(run_id)
        self.assertIn("A run id is never reused", str(caught.exception))
        self.assertIn(str(folder), str(caught.exception))
        self.assertEqual(self.sent, [], "nothing was sent to the mock before the refusal")
        self.assertEqual(tree(folder), before, "the folder is byte-identical after")
        self.assertEqual(sorted(p.name for p in self.runs.iterdir()), [run_id])
        self.assert_lock_free()

    def test_a_folder_an_earlier_plan_run_wrote_is_refused_the_same_way(self):
        run_id = f"run-{TODAY}-906"
        first = self.plan_run(run_id)
        self.assertEqual(first["ended"], "completed")
        folder = self.runs / run_id
        self.assertTrue((folder / "events.jsonl").exists())
        before = tree(folder)
        self.sent.clear()
        with self.assertRaises(op.Refusal) as caught:
            self.plan_run(run_id)
        self.assertIn("A run id is never reused", str(caught.exception))
        self.assertEqual(self.sent, [])
        self.assertEqual(tree(folder), before)
        self.assert_lock_free()

    def test_a_plan_run_without_write_makes_no_folder_and_a_repeated_id_collides_with_nothing(self):
        run_id = f"run-{TODAY}-907"
        for _ in range(2):
            op.run(self.plan_path, run_id, backend="mock", observe=lambda m: 9.0, status_dir=self.status_dir,
                   on_orchestrator=self.on_orchestrator)
        self.assertEqual(list(self.runs.iterdir()), [], "no --write, no run folder")


# --------------------------------------------------------------------------- #
# 10. the host skips a 9NN folder a plan run wrote
# --------------------------------------------------------------------------- #

class T10TheHostSkipsAFolderAPlanRunWrote(_RunIds):
    def test_the_next_id_is_the_first_free_one_after_the_plan_runs_folder(self):
        self.assertEqual(self.host._next_run_id(), f"run-{TODAY}-900", "an empty runs folder starts at 900")
        self.plan_run(f"run-{TODAY}-900")                       # a plan run was given a host-range id
        self.assertEqual(self.host._next_run_id(), f"run-{TODAY}-901")
        self.plan_run(f"run-{TODAY}-901")
        self.occupied(f"run-{TODAY}-902")
        self.assertEqual(self.host._next_run_id(), f"run-{TODAY}-903")

    def test_a_gap_is_filled_and_other_days_and_other_names_are_not_counted(self):
        self.plan_run(f"run-{TODAY}-901")
        (self.runs / "run-20000101-900").mkdir()                # another day
        (self.runs / f"run-{TODAY}-90x").mkdir()                # not a number
        (self.runs / "notes").mkdir()
        self.assertEqual(self.host._next_run_id(), f"run-{TODAY}-900", "900 is free, 901 is taken")

    def test_the_host_never_gives_out_an_id_whose_folder_exists(self):
        self.host.start()
        seen = set()
        for _ in range(3):
            reply = self.check_now(self.write_list(t85.CHECK_NOW_LIST))
            self.assertEqual(reply["check_now"], "started", reply)
            self.assertNotIn(reply["run_id"], seen)
            seen.add(reply["run_id"])
            self.wait_run(reply["run_id"])
        self.assertEqual(sorted(seen), [f"run-{TODAY}-{n}" for n in (900, 901, 902)])
        self.assertEqual(sorted(p.name for p in self.runs.iterdir()), sorted(seen))

    def test_all_hundred_taken_is_an_error_and_not_a_reused_id(self):
        for n in range(900, 1000):
            (self.runs / f"run-{TODAY}-{n}").mkdir()
        with self.assertRaises(RuntimeError) as caught:
            self.host._next_run_id()
        self.assertIn("taken", str(caught.exception))


# --------------------------------------------------------------------------- #
# 11. each entry point refuses an existing run folder with the same refusal
# --------------------------------------------------------------------------- #

class T11EachEntryPointRefusesAnExistingFolderTheSameWay(_RunIds):
    def test_plan_run_live_view_and_check_now_refuse_alike(self):
        entries = {"plan run": self.plan_run, "live view": self.live_run, "check now": self.check_now_run}
        messages = {}
        for name, entry in entries.items():
            with self.subTest(entry=name):
                run_id = f"run-{TODAY}-{910 + len(messages)}"
                folder = self.occupied(run_id)
                before = tree(folder)
                self.sent.clear()
                with self.assertRaises(op.Refusal) as caught:
                    entry(run_id)
                messages[name] = str(caught.exception).replace(str(folder), "<folder>")
                self.assertEqual(self.sent, [], f"{name}: nothing was sent before the refusal")
                self.assertEqual(tree(folder), before, f"{name}: the folder is byte-identical after")
                self.assert_lock_free()
        self.assertEqual(len(messages), 3)
        self.assertEqual(len(set(messages.values())), 1, messages)
        self.assertEqual(next(iter(messages.values())),
                         "<folder> already exists. A run id is never reused; raise it (P9)")

    def test_a_free_id_is_not_refused_by_any_of_the_three(self):
        for n, entry in enumerate((self.plan_run, self.live_run, self.check_now_run)):
            record = entry(f"run-{TODAY}-{920 + n}")
            self.assertTrue((self.runs / f"run-{TODAY}-{920 + n}" / "events.jsonl").exists())
            self.assertNotEqual(record.get("ended"), "refused")
            self.assert_lock_free()


if __name__ == "__main__":
    unittest.main()
