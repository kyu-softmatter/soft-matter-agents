"""Guards refuse what the 2026-09-30 rules forbid, using the in-memory FakeBackend."""

import pytest

from dino_autofocus.engine.guards import (
    FREE_WD_UM,
    OBJECTIVE_LIMITS,
    RETURN_Z_UM,
    SAMPLE_Z_WINDOW_UM,
    UNKNOWN_OBJECTIVE,
    FocusAxis,
    GuardError,
    SweepPlan,
    XYAxis,
    XYBox,
    approach_ceiling_um,
    bench_ascent_refusal,
    best_z_um,
    limits_for,
    registry_key,
    rotate_nosepiece,
    step_out_target,
)
from dino_autofocus.engine.records import model_value

OIL = "6-Plan Apo LmbdD0.13 100x Oil"


def axis(fake, objective="4x", **kw):
    return FocusAxis(fake, objective, allow_motion=True, sleep=lambda s: None, **kw)


def test_registry_keys():
    assert registry_key("1-Plan Apo LmbdD20 4x") == "4x"
    assert registry_key(OIL) == "100x-Oil"
    assert registry_key("4-Plan Apo 40x WI") == "40x-WI"


def test_plans_ascend_inside_the_window_and_under_the_100x_ceiling(fake):
    p = axis(fake).plan(2810, 30, 10)
    assert p.z_um == [2800, 2810, 2820, 2830, 2840]  # clipped at the window floor
    p = axis(fake, OIL).plan(2985, 80, 2)
    assert p.ceiling_um == pytest.approx(2985 + 0.4 * 130) and p.z_um[-1] <= p.ceiling_um
    assert p.z_um == sorted(p.z_um)
    with pytest.raises(GuardError, match="working distance"):
        axis(fake, "2x").plan(3000, 10, 1)  # not in the lens table
    with pytest.raises(GuardError):
        axis(fake).plan(3400, 50, 5)


def test_moves_outside_the_window_or_too_far_up_are_refused(fake):
    a = axis(fake)
    with pytest.raises(GuardError, match="window"):
        a.move_to(3201)
    with pytest.raises(GuardError, match="move up"):
        a.move_to(2950)
    assert a.move_to(2950, allow_ascent_um=50) == 2950
    assert a.move_to(2850) == 2850  # down is always allowed
    with pytest.raises(GuardError, match="only descends"):
        a.park_at(2900)
    assert a.park_at(0) == 0


def test_readback_mismatch_stops(fake):
    fake.z_readback_offset_um = -1.0  # 3037 commanded, 3036 read
    fake.z = 3036.0
    with pytest.raises(GuardError, match="read 3036"):
        axis(fake).move_to(3037, allow_ascent_um=2)


def test_no_motion_without_permission_and_dry_run_sends_nothing(fake):
    with pytest.raises(GuardError, match="allow_motion"):
        FocusAxis(fake, "4x").move_to(2850)
    a = FocusAxis(fake, "4x", dry_run=True)
    a.sweep(a.plan(2900, 20, 10), grab=fake.snap)
    assert fake.z == 2900 and not any(c[0] == "move_z" for c in fake.calls)
    assert a.motions and not any(m["sent"] for m in a.motions)


def test_a_model_number_cannot_drive_motion(fake):
    with pytest.raises(GuardError, match="model output"):
        axis(fake).move_to(model_value(2850.0, "dino head"))


def test_sweep_finds_an_interior_peak_from_the_readback(fake):
    a = axis(fake)
    score = lambda f: {"sharp": -abs(f.z_um - 2913.0), "sat": 0.0}  # noqa: E731
    coarse = a.sweep(a.plan(2900, 30, 10), fake.snap, score=score)
    assert coarse.peak_interior and coarse.peak_z_um == 2910
    fine = a.sweep(a.plan(coarse.peak_z_um, 4, 1), fake.snap, score=score)
    assert best_z_um(coarse, fine) == (2913, "fine peak inside its span")
    assert [c[1] for c in fake.calls if c[0] == "move_z"][:4] == [2870, 2880, 2890, 2900]


def test_a_peak_on_the_top_plane_is_not_climbed(fake):
    a = axis(fake, OIL)
    res = a.sweep(a.plan(2985, 20, 5), fake.snap, score=lambda f: f.z_um)
    assert res.at_top and not res.peak_interior
    z, why = best_z_um(res, None)
    assert z is None and "operator" in why
    assert fake.z == 3005  # stopped at the plan's top


def test_approach_keeps_the_bench_procedure(fake):
    fake.z = 0.0
    a = axis(fake)  # 4x: its free WD covers the window above 2800
    with pytest.raises(GuardError, match="below the sample window"):
        a.sweep(a.plan(2900, 10, 5), fake.snap, score=lambda f: 0.0)
    assert a.approach(2840) == 2840
    moves = [c[1] for c in fake.calls if c[0] == "move_z"]
    assert moves == [2800, 2810, 2820, 2830, 2840]  # one move to 2800, then 10 um steps
    assert a.motions[-1]["basis"]["approach_step_um"] == (
        "OBJECTIVE_LIMITS[4x].approach_step_um, unmeasured provisional")
    with pytest.raises(GuardError, match="larger than"):
        a.approach(2900, step_um=700)


def test_the_clearance_check_runs_at_every_step(fake):
    fake.z = 0.0
    seen = []

    def clearance(z):
        seen.append(z)
        return z < 2825

    with pytest.raises(GuardError, match="clearance check stopped the approach at 2830"):
        axis(fake).approach(2900, clearance=clearance)
    assert seen == [2800, 2810, 2820, 2830] and fake.z == 2830


def test_xy_long_moves_follow_the_objective_table(fake):
    box = XYBox.around((8026.0, 571.6), 3572)
    xy = XYAxis(fake, box, allow_motion=True)
    with pytest.raises(GuardError, match="outside the box"):
        xy.goto(20000, 0)
    assert xy.goto(9683.7, -1086.0) == (9683.7, -1086.0)  # 4x: one tile at sample Z
    assert xy.motions[-1]["basis"]["long_move_um"] == (
        "OBJECTIVE_LIMITS[4x].long_xy_um, unmeasured provisional")
    fake.state = 5  # 100x Oil read back from the nosepiece
    assert xy.goto(9783.7, -1086.0)  # 100 um, under one 100x field
    with pytest.raises(GuardError, match=r"over 156 um \(100x-Oil\) needs Z retracted"):
        xy.goto(10683.7, -1086.0)
    fake.z = 0.0
    assert xy.goto(10683.7, -1086.0) == (10683.7, -1086.0)
    assert "caller" not in str(xy.motions)


@pytest.mark.parametrize("why", ["unreadable", "not in the table"])
def test_unknown_objective_means_retract_before_any_move(fake, why):
    if why == "unreadable":
        def broken():
            raise OSError("Nosepiece not answering")
        fake.nosepiece = broken
    else:
        fake.nosepiece = lambda: "7-Plan Fluor 2x"
    xy = XYAxis(fake, XYBox(-1e5, 1e5, -1e5, 1e5), allow_motion=True)
    with pytest.raises(GuardError, match="strictest"):
        xy.goto(8030.0, 571.6)  # even 4 um
    fake.z = 0.0
    assert xy.goto(8030.0, 571.6) == (8030.0, 571.6)
    assert xy.motions[-1]["basis"]["long_move_um"].startswith("OBJECTIVE_LIMITS[strictest")


def test_xy_readback_mismatch_stops(fake):
    xy = XYAxis(fake, XYBox(-1e5, 1e5, -1e5, 1e5), allow_motion=True)
    fake.move_xy = lambda x, y, *, token, timeout_s=None: (x + 20.0, y)  # hand on the joystick
    with pytest.raises(GuardError, match="XY commanded"):
        xy.goto(8100.0, 571.6)


def test_nosepiece_turns_only_retracted_with_pfs_out_of_range(fake):
    a = axis(fake)
    with pytest.raises(GuardError, match="not retracted"):
        rotate_nosepiece(fake, a, 5)
    a.park_at(0)
    fake.pfs_in_range = "In Range"
    with pytest.raises(GuardError, match="refusing to rotate"):
        rotate_nosepiece(fake, a, 5)
    fake.pfs_in_range, fake.pfs_enabled = "Out of Range", True
    assert rotate_nosepiece(fake, a, 5) == OIL and not fake.pfs_enabled


def test_a_hand_built_plan_cannot_pass_the_ceiling(fake):
    a = axis(fake, OIL)
    bad = SweepPlan("100x-Oil", 2985, 200, 20, 3200, [2985 + 20 * i for i in range(11)])
    with pytest.raises(GuardError, match="leaves"):
        a.sweep(bad, fake.snap, score=lambda f: 0.0)
    assert not any(c[0] == "move_z" for c in fake.calls)
    jump = SweepPlan("100x-Oil", 2985, 20, 2, 3037, [2970.0, 2980.0])
    with pytest.raises(GuardError, match="steps of at most"):
        a.sweep(jump, fake.snap, score=lambda f: 0.0)
    with pytest.raises(GuardError, match="plan is for"):
        axis(fake).sweep(a.plan(2985, 10, 2), fake.snap, score=lambda f: 0.0)


def test_approach_stops_when_the_stage_stalls(fake):
    fake.z = 0.0
    a = axis(fake)
    with pytest.raises(GuardError, match="exceed the readback tolerance"):
        a.approach(2900, step_um=0.1)
    fake.move_z = lambda z_um, *, token: fake.z  # stage does not move
    with pytest.raises(GuardError):
        a.approach(2900)
    assert len(a.motions) == 1
    fake.z = 2800.0  # already in the window: the first table step must rise
    with pytest.raises(GuardError):
        a.approach(2900)


def test_pfs_is_not_touched_without_allow_motion(fake):
    fake.z, fake.pfs_enabled = 0.0, True
    with pytest.raises(GuardError, match="allow_motion"):
        rotate_nosepiece(fake, FocusAxis(fake, "4x"), 5)
    with pytest.raises(GuardError, match="allow_motion"):
        FocusAxis(fake, "4x").require_pfs_quiet()
    assert fake.pfs_enabled


def test_relative_xy_moves_go_through_the_absolute_guard(fake):
    xy = XYAxis(fake, XYBox.around((8026.0, 571.6), 3572), allow_motion=True)
    assert xy.goto_rel(200.0, 0.0) == (8226.0, 571.6)  # an edge_trace step
    assert xy.motions[-1]["target_um"] == [8226.0, 571.6]
    with pytest.raises(GuardError, match="outside the box"):
        xy.goto_rel(5000.0, 0.0)
    fake.state = 5  # 100x Oil: 200 um is over its 156 um row
    with pytest.raises(GuardError, match="needs Z retracted"):
        xy.goto_rel(200.0, 0.0)
    assert not any(c[0] == "move_xy_rel" for c in fake.calls)


@pytest.mark.parametrize("flagged", ["bench=True", "no bench field, unknown kind"])
def test_approach_on_a_bench_needs_a_clearance_check(fake, flagged):
    from types import SimpleNamespace

    real_info = fake.info

    def bench_info():
        info = real_info()
        if flagged == "bench=True":
            info.bench = True  # a bench-flagged FakeBackend (T-033)
            return info
        return SimpleNamespace(kind="something-new")  # a backend from before T-033
    fake.info = bench_info
    fake.z = 0.0
    a = axis(fake)
    with pytest.raises(GuardError, match="needs a clearance check"):
        a.approach(2800)
    assert not any(c[0] == "move_z" for c in fake.calls)
    assert a.approach(2800, clearance=lambda z: True) == 2800  # 4x up to 2800 (T-029d)


def test_the_step_out_is_plus_y_and_stays_inside_the_stage_travel(fake):
    x, y, basis = step_out_target(fake, 8026.0, 571.6)  # fake Y travel -35..35 mm
    assert (x, y) == (8026.0, 15571.6)
    assert basis["basis"]["escape_dy_um"] == "unmeasured provisional"
    with pytest.raises(GuardError, match="outside the stage Y travel"):
        step_out_target(fake, 8026.0, 25000.0)
    real_info = fake.info

    def no_limits():
        info = real_info()
        info.stage_limits.y_um = None
        return info
    fake.info = no_limits
    with pytest.raises(GuardError, match="no stage Y limit"):
        step_out_target(fake, 8026.0, 571.6)


LENS_LABELS = {  # nosepiece labels: bench (mm_demo_core), mock world, FakeBackend
    "1-Plan Apo LmbdD20 4x": "4x",
    "2-Plan Apo LmbdD 10x": "10x",
    "2-Plan Apo 10x": "10x",
    "3-Plan Apo LmbdD 20x": "20x",
    "3-Plan Apo 20x": "20x",
    "4-Apo LmbdS 40xC WI": "40x-WI",
    "4-Plan Apo 40x WI": "40x-WI",
    "5-Plan Apo LmbdD 60x Oil": "60x-Oil",
    "5-Plan Apo 60x Oil": "60x-Oil",
    "6-Plan Apo LmbdD0.13 100x Oil": "100x-Oil",
}


@pytest.mark.parametrize("label, key", sorted(LENS_LABELS.items()))
def test_every_known_lens_label_has_a_table_row(label, key):
    assert registry_key(label) == key
    assert limits_for(label)[1] == key  # not the strictest row


def test_config_lens_names_map_to_table_rows():
    from pathlib import Path

    yaml = pytest.importorskip("yaml")  # the synth extra

    root = Path(__file__).resolve().parents[2] / "configs"
    names = [yaml.safe_load(p.read_text(encoding="utf-8"))["system"]["name"]
             for p in sorted(root.glob("ti2_*.yaml"))]
    assert len(names) == 6
    keys = {registry_key(n) for n in names}
    assert keys == {"4x", "10x", "20x", "40x-WI", "60x-Oil", "100x-Oil"}


@pytest.mark.parametrize("bench, refused", [(True, True), (False, False)])
def test_the_bench_flag_decides_when_present(fake, bench, refused):
    real_info = fake.info

    def flagged():
        info = real_info()
        info.kind = "mock"
        info.bench = bench  # T-033 field; set by hand until it lands
        return info
    fake.info = flagged
    fake.z = 0.0
    a = axis(fake)
    if refused:
        with pytest.raises(GuardError, match="needs a clearance check"):
            a.approach(2810)
    else:
        assert a.approach(2810) == 2810



def _climbs_above_2800(key):
    wd = FREE_WD_UM.get(key)
    return wd is not None and wd >= SAMPLE_Z_WINDOW_UM[1] - RETURN_Z_UM


@pytest.mark.parametrize("key", sorted(OBJECTIVE_LIMITS) + ["2x", None])
def test_approach_ceiling_per_lens(fake, key):
    """Above 2800 only a lens whose free WD covers the window may climb (4x, 10x, 20x);
    every other lens, an unlisted key (2x) and an unreadable objective (None) are refused
    there, not clamped."""
    fake.z = 0.0
    a = FocusAxis(fake, key, allow_motion=True, sleep=lambda s: None)
    assert a.approach(2800) == 2800  # every lens may come back to the window floor
    if _climbs_above_2800(key):
        assert key in ("4x", "10x", "20x")
        assert a.approach(2850) == 2850
    else:
        with pytest.raises(GuardError, match="is above 2800 um"):
            a.approach(2850)
        assert fake.z == 2800  # refused before any move: no clamp


def test_catalog_working_distances_set_the_sweep_ceiling(fake):
    """2026-10-02 catalog values: the sweep ceiling is centre + 0.4 x free WD."""
    assert axis(fake, "40x-WI").plan(2900, 10, 5).ceiling_um == pytest.approx(2900 + 0.4 * 170)
    assert axis(fake, "60x-Oil").plan(2900, 10, 5).ceiling_um == pytest.approx(2900 + 0.4 * 150)


def test_100x_oil_approach_to_3200_is_refused_not_clamped(fake):
    fake.z = 0.0
    a = axis(fake, OIL)
    with pytest.raises(GuardError, match="100x-Oil.*130 um"):
        a.approach(3200)
    assert not any(c[0] == "move_z" for c in fake.calls)


@pytest.mark.parametrize("how", ["read error", "no label"])
def test_an_unreadable_objective_caps_the_approach_at_2800(fake, how):
    if how == "read error":
        def broken():
            raise OSError("Nosepiece not answering")
        fake.nosepiece = broken
    else:
        fake.nosepiece = lambda: ""
    fake.z = 0.0
    a = FocusAxis.from_backend(fake, allow_motion=True, sleep=lambda s: None)
    assert a.key == UNKNOWN_OBJECTIVE
    with pytest.raises(GuardError, match="unknown objective"):
        a.approach(2900)
    assert not any(c[0] == "move_z" for c in fake.calls)
    assert a.approach(2800) == 2800
    with pytest.raises(GuardError, match="working distance"):
        a.plan(2900, 10, 5)  # no sweep plan for an unknown lens either



def test_an_unreadable_info_counts_as_the_bench(fake):
    def broken():
        raise OSError("core not answering")
    fake.info = broken
    fake.z = 0.0
    with pytest.raises(GuardError, match="needs a clearance check"):
        axis(fake).approach(2810)



# -- T-029d: no bench approach until measured -------------------------------------------
def _bench(fake):
    real = fake.info

    def info():
        i = real()
        i.bench = True
        return i
    fake.info = info
    return fake


def test_bench_unlocked_keeps_the_per_lens_ceiling(fake):
    """Partial unlock: on the bench only a lens whose free WD covers the window may go above
    2800 (4x, 10x, 20x); 40x-WI, 60x-Oil, 100x-Oil and an unreadable lens stay at 2800 for
    every upward move. Off the bench nothing changes."""
    off = fake.info()
    assert bench_ascent_refusal(off, "100x-Oil", 3200.0) is None
    info = _bench(fake).info()
    for key in ("4x", "10x", "20x"):
        assert bench_ascent_refusal(info, key, 3200.0) is None
    for key in ("40x-WI", "60x-Oil", "100x-Oil", None):
        assert bench_ascent_refusal(info, key, 2800.0) is None
        assert "partial unlock" in bench_ascent_refusal(info, key, 2800.5)
    assert [approach_ceiling_um(k) for k in ("4x", "10x", "20x")] == [3200.0] * 3
    assert [approach_ceiling_um(k) for k in ("40x-WI", "60x-Oil", "100x-Oil", None)] == [2800.0] * 4


@pytest.mark.parametrize("how", ["sweep", "move_to"])
def test_bench_unlocked_100x_cannot_sweep_or_move_above_2800(fake, how):
    """The hole the T-029d lock used to cover: a sweep's first move climbs to its start in one
    jump with no clearance check. Partial unlock refuses it before anything goes up."""
    _bench(fake)
    fake.state, fake.z = 5, 2800.0
    a = FocusAxis(fake, OIL, allow_motion=True, sleep=lambda s: None)
    before = len([c for c in fake.calls if c[0] == "move_z"])
    with pytest.raises(GuardError, match="partial unlock"):
        if how == "sweep":
            a.sweep(a.plan(2985, 20, 5), fake.snap, score=lambda f: 0.0)
        else:
            a.move_to(2850, allow_ascent_um=60)
    assert [c for c in fake.calls if c[0] == "move_z"][before:] == [] and fake.z == 2800.0


def test_bench_unlocked_100x_fine_steps_under_the_tolerance_cannot_add_up(fake):
    """0.2 um steps are under the 0.25 um readback tolerance; above 2800 each is still checked."""
    _bench(fake)
    fake.state, fake.z = 5, 2800.0
    a = FocusAxis(fake, OIL, allow_motion=True, sleep=lambda s: None)
    with pytest.raises(GuardError, match="partial unlock"):
        a.sweep(a.plan(2800, 10, 0.2), fake.snap, score=lambda f: 0.0)
    assert fake.z <= 2800.0


def test_bench_unlocked_4x_climbs_above_2800(fake):
    _bench(fake)
    fake.state, fake.z = 0, 2800.0
    assert axis(fake).approach(2850, clearance=lambda z: True) == 2850


@pytest.fixture
def approach_locked(monkeypatch):
    """The T-029d lock as it shipped until 2026-10-02, so its refusals stay tested."""
    from dino_autofocus.engine import guards
    monkeypatch.setattr(guards, "BENCH_APPROACH", "UNMEASURED")


def test_bench_approach_unlocked_by_the_user_and_read_in_one_place():
    """Unlocked by the user on 2026-10-02; still one module-level line, one reader."""
    import ast
    from pathlib import Path

    from dino_autofocus.engine import guards

    assert guards.BENCH_APPROACH == "MEASURED"
    assert guards.bench_approach_state() == "MEASURED"
    root = Path(__file__).resolve().parents[2]
    hits = [p for d in ("src", "scripts") for p in (root / d).rglob("*.py")
            if "BENCH_APPROACH" in p.read_text(encoding="utf-8") and p.name != "guards.py"]
    assert hits == []
    path = root / "src/dino_autofocus/engine/guards.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    stores = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == "BENCH_APPROACH"
              and isinstance(n.ctx, ast.Store)]
    assert len(stores) == 1 and stores[0].col_offset == 0
    readers = {f.name for f in ast.walk(tree) if isinstance(f, ast.FunctionDef)
               for n in ast.walk(f) if isinstance(n, ast.Name) and n.id == "BENCH_APPROACH"}
    assert readers == {"bench_approach_state"}
    assert not any(isinstance(n, ast.Global) for n in ast.walk(tree))
    fn = next(f for f in ast.walk(tree) if isinstance(f, ast.FunctionDef)
              and f.name == "bench_approach_state")
    src = ast.get_source_segment(path.read_text(encoding="utf-8"), fn)
    assert "environ" not in src and "getenv" not in src and "settings" not in src


def test_environment_and_config_do_not_change_it():
    """A fresh interpreter with every plausible variable set reads the source line only."""
    import os
    import subprocess
    import sys

    env = {**os.environ, "BENCH_APPROACH": "UNMEASURED", "DINO_BENCH_APPROACH": "UNMEASURED",
           "DINO_AUTOFOCUS_BENCH_APPROACH": "UNMEASURED"}
    code = ("from dino_autofocus.engine import guards; "
            "assert guards.BENCH_APPROACH == 'MEASURED'; "
            "assert guards.bench_approach_state() == 'MEASURED'")
    subprocess.run([sys.executable, "-c", code], check=True, env=env)


@pytest.mark.parametrize("state, how", [
    (0, "4x above 2800 (approach)"), (0, "4x above 2800 (move_to)"),
    (0, "4x sweep above 2800"), (5, "100x Oil up to 2800"), (5, "100x Oil sweep"),
    (2, "20x up to 2800"), ("unreadable", "unreadable lens up to 2800")])
def test_bench_upward_moves_are_refused_before_any_move(fake, approach_locked, state, how):
    _bench(fake)
    if state == "unreadable":
        def broken():
            raise OSError("Nosepiece not answering")
        fake.nosepiece = broken
    else:
        fake.state = state
    key = {0: "4x", 5: OIL, 2: "3-Plan Apo 20x"}.get(state)
    if "sweep" in how:
        fake.z = 2850.0
    else:
        fake.z = 0.0 if "up to 2800" in how else 2800.0
    a = FocusAxis(fake, key, allow_motion=True, sleep=lambda s: None)
    calls = {
        "4x above 2800 (approach)": lambda: a.approach(2810, clearance=lambda z: True),
        "4x above 2800 (move_to)": lambda: a.move_to(2810, allow_ascent_um=20),
        "4x sweep above 2800": lambda: a.sweep(a.plan(2900, 20, 10), fake.snap,
                                               score=lambda f: 0.0),
        "100x Oil up to 2800": lambda: a.approach(2800, clearance=lambda z: True),
        "100x Oil sweep": lambda: a.sweep(a.plan(2985, 20, 5), fake.snap, score=lambda f: 0.0),
        "20x up to 2800": lambda: a.approach(2800, clearance=lambda z: True),
        "unreadable lens up to 2800": lambda: a.approach(2800, clearance=lambda z: True),
    }
    before = [c for c in fake.calls if c[0] == "move_z"]
    with pytest.raises(GuardError, match="T-029d"):
        calls[how]()
    moved = [c for c in fake.calls if c[0] == "move_z"][len(before):]
    if "sweep" in how:  # the sweep may first descend to its start; nothing goes up
        assert all(c[1] <= 2850.0 for c in moved)
    else:
        assert moved == []
    assert fake.z <= 2850.0


def test_bench_still_allows_the_4x_up_to_2800_and_every_downward_move(fake):
    _bench(fake).z = 0.0
    a = axis(fake)  # 4x
    assert a.approach(2800, clearance=lambda z: True) == 2800
    fake.state = 5  # 100x Oil in place: down moves and retract stay allowed
    oil = FocusAxis(fake, OIL, allow_motion=True, sleep=lambda s: None)
    assert oil.park_at(1000.0) == 1000.0
    assert oil.park_at(0.0) == 0.0  # the full retract (FocusAxis.retract() comes with T-039)


def test_mock_and_demo_kinds_are_not_affected(fake):
    fake.z = 0.0  # FakeBackend is simulated (bench False): the T-029d lock does not apply
    oil = axis(fake, OIL)
    assert oil.approach(2800) == 2800
    a = axis(fake)
    assert a.approach(2850) == 2850
