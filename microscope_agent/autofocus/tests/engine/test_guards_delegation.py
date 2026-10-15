"""D-01b: guards.py asks the flat focus_step_rules for every comparison it has a rule for, so
the two never disagree. The limits, the backend calls, the records and the bench locks stay
in guards; the rules answer None or the sentence of the refusal, and that sentence is what the
operation sees."""

import inspect
import re
import sys
from pathlib import Path

import pytest

from dino_autofocus.engine import guards
from dino_autofocus.engine.guards import (
    FREE_WD_UM,
    OBJECTIVE_LIMITS,
    RETRACT_Z_UM,
    RETURN_Z_UM,
    SAMPLE_Z_WINDOW_UM,
    STRICTEST,
    XY_TOL_UM,
    Z_TOL_UM,
    FocusAxis,
    GuardError,
    SweepPlan,
    XYAxis,
    XYBox,
    approach_ceiling_um,
    rotate_nosepiece,
)

rules = guards._rules
REPO = Path(__file__).resolve().parents[2]
SRC = Path(guards.__file__).read_text(encoding="utf-8")
WINDOW_TOP = SAMPLE_Z_WINDOW_UM[1]

DELEGATED = {
    "refuse_model_graded", "strictest_for_unknown_lens", "inside_window", "readback_ok",
    "may_move_up", "park_only_descends", "ascending", "plan_inside", "sweep_ceiling",
    "approach_ceiling", "approach_step_allowed", "rise_ok", "retracted",
    "nosepiece_turn_allowed", "inside_box", "xy_readback_ok",
}
NOT_DELEGATED = {
    "approach_steps": "the next approach target comes from the readback, not the nominal",
    "needs_retract_before_xy": "needs the lens kind of D-04; every lens is held to its row",
    "pfs_quiet": "used inside nosepiece_turn_allowed",
    "pfs_out_of_range": "used inside nosepiece_turn_allowed",
}


def axis(fake, objective="4x"):
    return FocusAxis(fake, objective, allow_motion=True, sleep=lambda s: None)


def test_the_rules_are_the_flat_file_loaded_once():
    assert rules is sys.modules["_mic_focus_step_rules"]
    assert Path(rules.__file__).resolve() == (
        REPO / "microscope_agent" / "src" / "focus_step_rules.py").resolve()


def test_every_rule_is_called_from_guards_or_named_as_an_exception():
    public = {name for name, fn in inspect.getmembers(rules, inspect.isfunction)
              if fn.__module__ == rules.__name__ and not name.startswith("_")}
    called = set(re.findall(r"_rules\.(\w+)\(", SRC))
    assert called == DELEGATED
    assert public == DELEGATED | set(NOT_DELEGATED), public ^ (DELEGATED | set(NOT_DELEGATED))


def test_the_strictest_row_and_the_approach_ceiling_come_from_the_rules():
    rows = {k: (r.long_xy_um, r.approach_step_um) for k, r in OBJECTIVE_LIMITS.items()}
    assert (STRICTEST.long_xy_um, STRICTEST.approach_step_um) == \
        rules.strictest_for_unknown_lens(rows)
    for key in [*FREE_WD_UM, "2x", None]:
        assert approach_ceiling_um(key) == rules.approach_ceiling(
            RETURN_Z_UM, WINDOW_TOP, FREE_WD_UM.get(key) if key else None), key


def test_z_refusals_are_the_rules_sentences(fake):
    a = axis(fake)  # the fake reads Z 2900 um
    with pytest.raises(GuardError) as e:
        a.move_to(2700)
    assert str(e.value) == rules.inside_window(2700.0, SAMPLE_Z_WINDOW_UM)
    with pytest.raises(GuardError) as e:
        a.move_to(2950)
    assert str(e.value) == rules.may_move_up(2900.0, 2950.0, 0.0, Z_TOL_UM)
    with pytest.raises(GuardError) as e:
        a.park_at(2950)
    assert str(e.value) == rules.park_only_descends(2900.0, 2950.0, Z_TOL_UM, RETRACT_Z_UM,
                                                    WINDOW_TOP) == "park_at only descends"
    assert a.ceiling_um(2930) == rules.sweep_ceiling(2930.0, WINDOW_TOP, FREE_WD_UM["4x"],
                                                     guards.WD_FRACTION)
    with pytest.raises(GuardError) as e:
        a.approach(2900, step_um=700)
    assert str(e.value) == (f"{rules.approach_step_allowed(700.0, 10.0, Z_TOL_UM, '4x')} "
                            f"({guards.PROVISIONAL})")
    fake.z_readback_offset_um = 1.0  # a hand on the focus knob
    with pytest.raises(GuardError) as e:
        a.move_to(2850)
    assert str(e.value) == rules.readback_ok(2850.0, 2851.0, Z_TOL_UM, "ZDrive")


def test_plan_refusals_are_the_rules_sentences(fake):
    a = axis(fake)
    gap = SweepPlan("4x", 2900.0, 10.0, 5.0, WINDOW_TOP, [2900.0, 2920.0])
    with pytest.raises(GuardError) as e:
        a.sweep(gap, fake.snap)
    assert str(e.value) == rules.ascending([2900.0, 2920.0], 5.0)
    low = SweepPlan("4x", 2900.0, 10.0, 5.0, WINDOW_TOP, [2700.0, 2705.0])
    with pytest.raises(GuardError) as e:
        a.sweep(low, fake.snap)
    assert str(e.value) == rules.plan_inside([2700.0, 2705.0], SAMPLE_Z_WINDOW_UM[0],
                                             a.ceiling_um(2900.0))


def test_xy_refusals_are_the_rules_sentences(fake):
    box = XYBox(-1e5, 1e5, -1e5, 1e5)
    xy = XYAxis(fake, box, allow_motion=True)
    with pytest.raises(GuardError) as e:
        xy.goto(2e5, 0)
    assert str(e.value) == rules.inside_box(2e5, 0.0, (-1e5, 1e5, -1e5, 1e5))
    fake.move_xy = lambda x, y, *, token, timeout_s=None: (x + 20.0, y)
    with pytest.raises(GuardError) as e:
        xy.goto(8100.0, 571.6)
    assert str(e.value) == rules.xy_readback_ok((8100.0, 571.6), (8120.0, 571.6), XY_TOL_UM)


def test_the_nosepiece_turn_is_the_whole_rule_and_an_unknown_pfs_state_refuses(fake):
    a = axis(fake)
    a.park_at(0)
    fake.pfs_in_range = "In Range"
    with pytest.raises(GuardError) as e:
        rotate_nosepiece(fake, a, 5)
    assert str(e.value) == rules.nosepiece_turn_allowed(0.0, guards.RETRACTED_MAX_Z_UM, False,
                                                        "In Range")
    fake.pfs_in_range, fake.pfs_enabled = "Out of Range", None  # the device did not answer
    with pytest.raises(GuardError, match="PFS state unknown"):
        rotate_nosepiece(fake, a, 5)
    fake.pfs_enabled = False
    assert rotate_nosepiece(fake, a, 5).endswith("100x Oil")
