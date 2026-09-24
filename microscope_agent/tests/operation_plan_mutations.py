"""Card 040's behaviours switched off one at a time; each one's tests must go red.

    python microscope_agent/tests/operation_plan_mutations.py

A test that has never been seen to fail is a test nobody knows tests anything.
Each mutation replaces one behaviour in the loaded modules with a version that
does not have it, runs the tests named for it, and requires every one of them to
fail. A mutation under which a named test still passes is a defect in that test,
and the script exits non-zero.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


def fresh():
    for name in [n for n in sys.modules if n.startswith(("_op_under_test", "_mic_orchestrator",
                                                          "_serial_under_test", "_dev_",
                                                          "_mic_operator_for_gate", "t040"))]:
        del sys.modules[name]
    spec = importlib.util.spec_from_file_location("t040", HERE / "test_operation_plan.py")
    t = importlib.util.module_from_spec(spec)
    sys.modules["t040"] = t
    spec.loader.exec_module(t)
    return t


def m_points_unchecked(t):
    t.op.check_operation_points = lambda *a, **k: []


def m_wrong_phase(t):
    t.op._sine_point = lambda move, i: float(move["centre_um"])


def m_no_stop(t):
    t.orch.from_operation_move = lambda c: False


def m_no_blind_exception(t):
    t.orch.BLIND_BY_PERSONS_EXCEPTION = ()


def m_blind_for_any(t):
    t.orch.BLIND_BY_PERSONS_EXCEPTION = ("laser_combiner", "optical_tweezers", "dmd")


def m_z_exempt(t):
    t.orch.OPERATION_EXEMPT_AXES = ("x", "y", "z")


def m_operation_not_required(t):
    real = t.orch.operation_exemptions

    def any_plan(plan, commands):
        return real(dict(plan or {}, operation=(plan or {}).get("operation")
                         or {"device": "piezo_stage",
                             "moves": [{"id": c.from_field[16:-1], "axis": "x"}
                                       for c in commands]}), commands)
    t.orch.operation_exemptions = any_plan


def m_allow_list_skipped_in_operation_plans(t):
    def skip(self, plan, commands):
        self.check_software_motion([c for c in commands if not t.orch.from_operation_move(c)])
    t.orch.Orchestrator.check_software_motion_for = skip


def m_no_approval_needed(t):
    t.op.authorise = lambda plan, approvals=None: t.op.Authorisation(True, ["mutated"])


MUTATIONS = [
    ("derived points not checked against the envelope", m_points_unchecked,
     ["Derivation.test_a_point_outside_the_envelope_refuses_and_names_the_disagreement",
      "Derivation.test_a_missing_limit_refuses"]),
    ("sine not derived from its index and start", m_wrong_phase,
     ["Derivation.test_sine_points_from_the_integer_index"]),
    ("no stop on a read-back outside tolerance", m_no_stop,
     ["ReadBack.test_outside_tolerance_stops_before_the_next_move"]),
    ("the person's named exception removed", m_no_blind_exception,
     ["Router.test_tweezers_reach_their_wrapper_not_the_manual_sheet"]),
    ("the exception widened to another blind channel", m_blind_for_any,
     ["Router.test_any_other_blind_channel_still_goes_to_the_manual_sheet"]),
    ("piezo Z exempted", m_z_exempt,
     ["Exemption.test_piezo_z_operation_move_is_refused"]),
    ("exemption without `operation` in the plan", m_operation_not_required,
     ["Exemption.test_piezo_x_from_a_plan_without_operation_is_refused"]),
    ("allow-list skipped for anything from operation.moves", m_allow_list_skipped_in_operation_plans,
     ["Exemption.test_a_micromanager_command_inside_an_operation_plan_meets_the_allow_list"]),
    ("exemption granted with no approval", m_no_approval_needed,
     ["Exemption.test_a_hand_built_piezo_command_with_no_approved_plan_is_refused"]),
]


def main() -> int:
    t = fresh()
    base = unittest.TextTestRunner(verbosity=0).run(unittest.defaultTestLoader.loadTestsFromModule(t))
    if not base.wasSuccessful():
        print("the unmutated tests do not all pass; mutation results would mean nothing")
        return 1
    bad = 0
    for label, mutate, names in MUTATIONS:
        t = fresh()
        mutate(t)
        red, green = [], []
        for name in names:
            result = unittest.TestResult()
            unittest.defaultTestLoader.loadTestsFromName(name, t).run(result)
            (green if result.wasSuccessful() else red).append(name.split(".")[-1])
        print(f"mutation {label!r}: watched failing {red}"
              + (f"; STILL PASSING {green}" if green else ""))
        bad += bool(green)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
