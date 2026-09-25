"""Card 036's refusals for the confocal laser wrapper, against the mock transport.

Nothing here opens a device. Run:

    python -m unittest microscope_agent/tests/test_lunf.py
    python microscope_agent/tests/lunf_mutations.py      # watch each refusal fail

The wiring below is SYNTHETIC: line ids, digital lines, levels, path states
and the entry name are made up for the tests and are not this instrument's.
They must not be read as a record of the combiner's wiring or of which light
path state is eyepiece-free -- both are the store's to hold.
"""

from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

LUNF_PATH = Path(__file__).resolve().parents[1] / "src" / "devices" / "lunf.py"


def load(source: str | None = None, name: str = "lunf_under_test") -> types.ModuleType:
    """The wrapper as a module, from its file or from a (mutated) copy of its text."""
    mod = types.ModuleType(name)
    mod.__file__ = str(LUNF_PATH)
    sys.modules[name] = mod          # dataclasses and friends resolve through sys.modules
    text = LUNF_PATH.read_text(encoding="utf-8") if source is None else source
    exec(compile(text, str(LUNF_PATH), "exec"), mod.__dict__)
    return mod


ROW = {"id": "laser_combiner", "automatable": "partial", "read_back": False,
       "elements": [{"id": "line_select",
                     "lines": {"a": "dl0", "b": "dl1", "c": "dl2"},
                     "open_level": "OPEN", "closed_level": "SHUT"}]}

_ALL = object()


class Gates(unittest.TestCase):
    """Every refusal the card lists. The mutation runner swaps `mod` for a broken copy."""

    mod = None

    @classmethod
    def setUpClass(cls):
        if cls.mod is None:
            cls.mod = load()

    def setUp(self):
        m = self.mod
        self._saved = m.COVERING_LIMIT, m.ENVELOPE_PATH
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        m = self.mod
        m.reset()
        m.COVERING_LIMIT, m.ENVELOPE_PATH = self._saved
        self._tmp.cleanup()

    # -- arranging ------------------------------------------------------------ #

    def approved(self, *sets):
        return [{"from": "test", "device": "laser_combiner", "action": "enable",
                 "settings": {"laser_combiner": {"enable": list(s)}}} for s in sets]

    def arm(self, *, limit=_ALL, kind="physical", ends=(0, 5), drop_end=None, state=7, pinned=None,
            reader=None, transport=None, approved=_ALL, approved_by="test person",
            bench=("test seat", "the bench is yours"), log=None, with_log=True):
        """Every gate satisfied unless a keyword says otherwise."""
        m = self.mod
        m.reset()
        names = ("laser_combiner_command_voltage_min", "laser_combiner_command_voltage_max")
        limits = {n: {"value": v, "unit": "V", "bounds": b, "confirmation": {"kind": kind}}
                  for n, v, b in zip(names, ends, ("min", "max")) if n != drop_end}
        env = {"targets": [{"target": m.BENCH_TARGET, "limits": limits}]}
        m.ENVELOPE_PATH = self.tmp / "safety.json"
        m.ENVELOPE_PATH.write_text(json.dumps(env), encoding="utf-8")
        m.COVERING_LIMIT = names if limit is _ALL else limit
        t = transport or m.MockTransport()
        m.use_transport(t)
        m.bind_light_path(reader or (lambda: {"state": state, "read_back": True}),
                          {7: "synthetic_entry"} if pinned is None else pinned)
        m.bind_approval(self.approved(["a"], ["b"], ["a", "c"]) if approved is _ALL else approved,
                        approved_by)
        m.bind_bench(*bench)
        if with_log:
            sink = log if log is not None else []
            m.bind_log(lambda **f: sink.append(f))
        m.preflight(ROW)
        return t

    def refused(self, params) -> list[str]:
        try:
            self.mod.apply(params)
        except self.mod.LaserRefused as exc:
            return exc.reasons
        return []

    # -- the person's limit ---------------------------------------------------- #

    def test_no_enable_without_limit(self):
        t = self.arm(limit=None)
        self.assertTrue(self.refused({"enable": ["a"]}), "enabled with no covering limit")
        self.assertEqual(t.writes, [])

    def test_no_enable_with_either_end_absent(self):
        for end in ("laser_combiner_command_voltage_min", "laser_combiner_command_voltage_max"):
            with self.subTest(absent=end):
                t = self.arm(drop_end=end)
                self.assertTrue(self.refused({"enable": ["a"]}), f"enabled with {end} absent")
                self.assertEqual(t.writes, [])

    def test_no_enable_on_an_inverted_range(self):
        t = self.arm(ends=(5, 0))
        self.assertTrue(self.refused({"enable": ["a"]}), "enabled on an inverted range")
        self.assertEqual(t.writes, [])

    def test_no_enable_with_unconfirmed_limit(self):
        t = self.arm(kind="carried_over")
        self.assertTrue(self.refused({"enable": ["a"]}), "enabled under a carried_over limit")
        self.assertEqual(t.writes, [])

    def test_the_shipped_module_names_the_persons_voltage_pair(self):
        # the person's answer of 2026-09-24, and nothing else
        # (tearDown restores the loaded value after every test that sets one)
        self.assertEqual(self.mod.COVERING_LIMIT, ("laser_combiner_command_voltage_min",
                                                   "laser_combiner_command_voltage_max"))

    def test_the_real_transport_loads_nothing_until_used(self):
        t = self.mod.NiDaqTransport(library="no_such_library_anywhere")
        self.assertIsNone(t._dll)
        with self.assertRaises(OSError):
            t.lines_free(["x"])

    # -- the light path (2.1 rule 11) ----------------------------------------- #

    def test_no_enable_while_path_reaches_eyepieces(self):
        t = self.arm(state=3)
        self.assertTrue(self.refused({"enable": ["a"]}), "enabled at an unrecorded path state")
        self.assertEqual(t.writes, [])

    def test_no_enable_when_no_mapping_is_recorded(self):
        for pinned in ({}, {7: ""}, {"7": "synthetic_entry"}):
            with self.subTest(pinned=pinned):
                t = self.arm(pinned=pinned)
                self.assertTrue(self.refused({"enable": ["a"]}), f"enabled with {pinned!r}")
                self.assertEqual(t.writes, [])

    def test_no_enable_on_a_label(self):
        # even with the label itself offered as a recorded key
        t = self.arm(reader=lambda: {"state": "Camera", "read_back": True},
                     pinned={7: "synthetic_entry", "Camera": "synthetic_entry"})
        self.assertTrue(self.refused({"enable": ["a"]}), "enabled on a path label")
        self.assertEqual(t.writes, [])

    def test_no_enable_while_path_unreadable(self):
        def broken():
            raise OSError("stand not answering")
        for reader in (broken, lambda: {"state": 7, "read_back": False}, lambda: None):
            with self.subTest(reader=reader):
                t = self.arm(reader=reader)
                self.assertTrue(self.refused({"enable": ["a"]}))
                self.assertEqual(t.writes, [])
        t = self.arm()
        self.mod.bind_light_path(None, {7: "synthetic_entry"})
        self.assertTrue(self.refused({"enable": ["a"]}), "enabled with no path reader bound")
        self.assertEqual(t.writes, [])

    def test_no_enable_on_a_clean_readback_alone(self):
        # the path reads back clear every time; exactly one other gate is missing
        for missing, kw in (("limit", {"limit": None}),
                            ("approved list", {"approved": None}),
                            ("approval of this enable", {"approved": self.approved(["b"])}),
                            ("approver", {"approved_by": " "}),
                            ("bench", {"bench": (None, None)}),
                            ("log", {"with_log": False})):
            with self.subTest(missing=missing):
                t = self.arm(**kw)
                reasons = self.refused({"enable": ["a"]})
                self.assertEqual(len(reasons), 1, reasons)
                self.assertEqual(t.writes, [])

    def test_readback_is_read_and_logged_immediately_before_each_enable(self):
        calls, log = [], []
        self.arm(log=log, reader=lambda: calls.append(1) or {"state": 7, "read_back": True})
        self.mod.apply({"enable": ["a"]})
        self.mod.apply({"enable": ["b"]})
        self.assertEqual(len(calls), 2, "the path was not read at every enable")
        self.assertEqual([e["event"] for e in log],
                         ["light_path_readback", "laser_enable"] * 2)

    def test_every_refusal_reported_at_once(self):
        self.arm(limit=None, state=3, bench=(None, None))
        self.assertEqual(len(self.refused({"enable": ["a"]})), 3)

    # -- what is written, and what is claimed ---------------------------------- #

    def test_power_is_refused(self):
        t = self.arm()
        self.assertTrue(self.refused({"enable": [], "power": {"a": 0.1}}), "power accepted")
        self.assertEqual(t.writes, [])

    def test_enable_writes_closes_first_and_claims_no_readback(self):
        t = self.arm()
        out = self.mod.apply({"enable": ["b"]})
        self.assertEqual([lvl for _, lvl in t.writes], ["SHUT", "SHUT", "OPEN"])
        self.assertEqual(out["verification"], "none")
        self.assertNotIn("verified", out)
        r = self.mod.read()
        self.assertIsNone(r["state"])
        self.assertEqual(r["commanded"]["b"], "open")

    def test_closing_needs_none_of_the_gates(self):
        t = self.arm(limit=None, pinned={}, approved=None, bench=(None, None), with_log=False)
        self.mod.apply({"enable": []})
        self.assertEqual([lvl for _, lvl in t.writes], ["SHUT"] * 3)

    # -- abort ------------------------------------------------------------------ #

    def test_abort_blanks_every_line_first(self):
        t = self.arm()
        self.mod.apply({"enable": ["a", "c"]})
        t.writes.clear()
        out = self.mod.abort()
        self.assertEqual(sorted(t.writes), [("dl0", "SHUT"), ("dl1", "SHUT"), ("dl2", "SHUT")])
        self.assertEqual(out["verification"], "none")
        self.assertEqual([r["written"] for r in out["blanked"]], [True, True, True])
        with self.assertRaises(RuntimeError):
            self.mod.apply({"enable": []})

    def test_a_blind_laser_is_assumed_on_after_any_command(self):
        self.arm()
        self.assertIsNone(self.mod.read()["beam"], "no command yet, nothing to assume")
        self.mod.apply({"enable": []})
        self.assertEqual(self.mod.read()["beam"], "assumed_on", "a blanking command is not a closed beam")
        out = self.mod.abort()
        self.assertEqual(out["beam"], "assumed_on")
        self.assertIsNone(out["barrier"])
        self.assertEqual(self.mod.read()["beam"], "assumed_on")

    def test_abort_reports_a_failed_line_and_blanks_the_rest(self):
        t = self.arm(transport=self.mod.MockTransport(fail_on={"dl1"}))
        out = self.mod.abort()
        self.assertEqual(sorted(t.writes), [("dl0", "SHUT"), ("dl2", "SHUT")])
        self.assertEqual([r["written"] for r in out["blanked"]], [True, False, True])

    # -- the ground ------------------------------------------------------------- #

    def test_held_lines_are_not_ready(self):
        t = self.arm(transport=self.mod.MockTransport(held_by="another program"))
        self.assertIs(self.mod.preflight(ROW)["ready"], False)
        self.assertTrue(self.refused({"enable": []}), "wrote to lines another program holds")
        self.assertEqual(t.writes, [])

    def test_the_registry_row_as_it_stands_is_not_ready(self):
        self.arm()
        rep = self.mod.preflight({"id": "laser_combiner", "elements": [{"id": "line_select"}]})
        self.assertIs(rep["ready"], False)
        self.assertIn("line map", rep["reason"])


if __name__ == "__main__":
    unittest.main()
