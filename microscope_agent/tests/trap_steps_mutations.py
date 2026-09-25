"""Card 049's trap-step behaviours switched off one at a time; each one's tests must go red.

    python microscope_agent/tests/trap_steps_mutations.py

A test that has never been seen to fail is a test nobody knows tests anything.
Each mutation replaces one behaviour in the freshly loaded modules with a
version that lacks it, runs the tests named for it, and requires every one of
them to fail. A mutation under which a named test still passes is a defect in
that test, and the script exits non-zero.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


def fresh():
    for name in [n for n in sys.modules if n.startswith(("_op_traps_under_test", "_mic_orchestrator",
                                                          "_dev_", "_mic_operator_for_gate", "t049"))]:
        del sys.modules[name]
    spec = importlib.util.spec_from_file_location("t049", HERE / "test_trap_steps.py")
    t = importlib.util.module_from_spec(spec)
    sys.modules["t049"] = t
    spec.loader.exec_module(t)
    return t


def _patched_check(t, **off):
    """check_trap_steps with one of its limits read from a wider envelope."""
    real = t.op.check_trap_steps

    def check(plan, commands, safety, objective):
        if off.get("objective"):
            objective = (plan.get("trap_steps") or {}).get("objective") or "100x"
            safety = {"targets": [{"limits": {**{k.replace("60x", objective): v for k, v in
                                                 safety["targets"][0]["limits"].items()}}}]}
        if off.get("range"):
            lims = dict(safety["targets"][0]["limits"])
            for k in list(lims):
                if k.startswith("tweezers_trap_position_"):
                    lims[k] = {**lims[k], "value": -1e9 if k.endswith("_min") else 1e9}
            safety = {"targets": [{"limits": lims}]}
        if off.get("step"):
            lims = dict(safety["targets"][0]["limits"])
            if "tweezers_trap_step_max" in lims:
                lims["tweezers_trap_step_max"] = {**lims["tweezers_trap_step_max"], "value": 1e9}
            safety = {"targets": [{"limits": lims}]}
        if off.get("strength"):
            lims = dict(safety["targets"][0]["limits"])
            if "tweezers_trap_strength_max" in lims:
                lims["tweezers_trap_strength_max"] = {**lims["tweezers_trap_strength_max"], "value": 1e9}
            safety = {"targets": [{"limits": lims}]}
        return real(plan, commands, safety, objective)
    return check


def m_range_unchecked(t):
    t.op.check_trap_steps = _patched_check(t, range=True)


def m_objective_ignored(t):
    t.op.check_trap_steps = _patched_check(t, objective=True)


def m_step_unchecked(t):
    t.op.check_trap_steps = _patched_check(t, step=True)


def m_strength_unchecked(t):
    t.op.check_trap_steps = _patched_check(t, strength=True)


def m_no_approval_needed(t):
    class Yes:
        permitted, reasons, approval_id, kind = True, [], "forged", "plan_approval"
    t.op.authorise = lambda plan, approvals=None: Yes()


def m_derivation_not_compared(t):
    real = t.orch.Orchestrator._trap_gate

    def gate(self, plan, commands, candidates):
        decision = t.op.authorise(plan)
        return dict(candidates) if decision.permitted else {}
    t.orch.Orchestrator._trap_gate = gate
    del real


def m_hold_ignored(t):
    real = t.op._run_trap_steps

    def run(o, plan, commands, ask_person):
        return real(o, plan, commands, lambda s: "yes")
    t.op._run_trap_steps = run


def m_rejection_not_stopping(t):
    def run(o, plan, commands, ask_person):
        out = []
        by_field = {c.from_field: c for c in commands}
        for step in plan["trap_steps"]["steps"]:
            if step["kind"] == "hold_for_person":
                if (ask_person(step["statement"]) or "").lower() != "yes":
                    break
                continue
            out.extend(o.dispatch([by_field[f"trap_steps.steps[{step['id']}]"]], plan=plan))
        return out
    t.op._run_trap_steps = run


def m_one_batch(t):
    def run(o, plan, commands, ask_person):
        return o.dispatch(commands, plan=plan)
    t.op._run_trap_steps = run


def m_relative_positions(t):
    real = t.op.derive_trap_steps

    def derive(plan):
        out = real(plan)
        for c in out:
            c.params["commands"] = [["TRAP_POSITION_REL", *l[1:]] if l[0] == "TRAP_POSITION" else l
                                    for l in c.params["commands"]]
        return out
    t.op.derive_trap_steps = derive


MUTATIONS = [
    (m_range_unchecked, ["Envelope.test_position_outside_refuses"]),
    (m_objective_ignored, ["Envelope.test_limit_for_another_objective_refuses"]),
    (m_step_unchecked, ["Envelope.test_step_larger_than_the_limit_refuses"]),
    (m_strength_unchecked, ["Envelope.test_strength_above_the_limit_refuses"]),
    (m_no_approval_needed, ["Exemption.test_without_approval_the_allow_list_refuses_the_tweezers",
                            "Exemption.test_the_run_refuses_an_unapproved_trap_plan"]),
    (m_derivation_not_compared, ["Exemption.test_a_hand_built_command_cannot_ride_the_approved_plan"]),
    (m_hold_ignored, ["Run.test_a_hold_without_a_yes_stops_every_later_step"]),
    (m_rejection_not_stopping, ["Run.test_a_rejected_step_stops_the_plan"]),
    (m_one_batch, ["Run.test_steps_go_out_in_the_plans_order"]),
    (m_relative_positions, ["Derivation.test_positions_are_absolute_never_relative"]),
]


def main() -> int:
    defects = 0
    for mutate, names in MUTATIONS:
        t = fresh()
        mutate(t)
        for name in names:
            cls, meth = name.split(".")
            result = unittest.TestResult()
            getattr(t, cls)(meth).run(result)
            failed = bool(result.failures or result.errors)
            print(f"{'red  ' if failed else 'GREEN'} {mutate.__name__:28s} {name}")
            defects += not failed
    print(f"\n{defects} named test(s) stayed green under their mutation")
    return 1 if defects else 0


if __name__ == "__main__":
    sys.exit(main())
