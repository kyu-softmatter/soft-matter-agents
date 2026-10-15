"""T-029d second layer: objective_change (escape true and false) and focus_100x refuse in
preflight on the bench while BENCH_APPROACH is locked, before anything moves; the mock is
unaffected. The guards layer itself is tested in test_contract_guards.py.

The user unlocked BENCH_APPROACH on 2026-10-02; these tests pin it locked so the refusal
path stays covered, and the last test checks the unlocked state."""

from __future__ import annotations

import pytest
from test_operations_focus_100x import fake100, run
from test_operations_objective_change import make, start  # noqa: F401 - make is a fixture
from test_operations_scan_4x import make_sample

from dino_autofocus.engine import guards


@pytest.fixture(autouse=True)
def approach_locked(request, monkeypatch):
    if "unlocked" not in request.node.name:
        monkeypatch.setattr(guards, "BENCH_APPROACH", "UNMEASURED")


def bench(backend):
    real = backend.info

    def info():
        i = real()
        i.bench = True
        return i
    backend.info = info
    return backend


@pytest.mark.parametrize("escape", [True, False])
def test_objective_change_to_the_100x_is_refused_on_the_bench(make, escape):  # noqa: F811
    r, sink, be = make()
    bench(be)
    z0 = be.world.z_um
    op_id = r.submit(start(target_state=5, escape=escape))
    failed = sink.wait("preflight_failed", op_id)
    check = next(c for c in failed.data["checks"] if c["name"] == "bench_approach")
    assert not check["ok"] and "T-029d" in check["why"] and "Q13" in check["why"]
    assert be.world.z_um == pytest.approx(z0)  # nothing moved


def test_objective_change_on_the_mock_has_no_bench_refusal(make):  # noqa: F811
    r, sink, be = make()
    op_id = r.submit(start(target_state=5, approach_target_um=3200.0))  # refused for WD only
    failed = sink.wait("preflight_failed", op_id)
    check = next(c for c in failed.data["checks"] if c["name"] == "bench_approach")
    assert check["ok"]


def test_focus_100x_is_refused_on_the_bench(tmp_path):
    b = bench(fake100())
    out, _ = run(b, make_sample(tmp_path))
    assert out["status"] == "preflight_failed"
    assert any("T-029d" in why for why in out["reasons"])
    assert not any(c[0] == "move_z" for c in b.calls)


def test_scan_4x_on_the_bench_stops_before_climbing_and_says_why(tmp_path):
    import json

    from test_operations_scan_4x import FocusFake, make_sample
    from test_operations_scan_4x import run as run_scan

    from dino_autofocus.engine.guards import GuardError

    b = bench(FocusFake())  # 4x in place, Z 2950: the first tile sweep starts below
    s = make_sample(tmp_path)
    with pytest.raises(GuardError, match="T-029d"):
        run_scan(b, s)
    z = [c[1] for c in b.calls if c[0] == "move_z"]
    assert z and all(v <= 2800.0 for v in z)  # down to the sweep start, never up past 2800
    summary = json.loads((s.scans_4x()[-1] / "summary.json").read_text())
    assert summary["status"] == "error" and "T-029d" in summary["error"]
    assert "Q13" in summary["error"] and b.lights == {"DiaLamp": "0", "Aura": "0"}


def test_objective_change_to_the_100x_above_2800_is_refused_when_unlocked(make):  # noqa: F811
    """Partial unlock: on the bench the 100x may not approach above 2800 (its free WD does not
    cover the window); the unit rule is in test_contract_guards.py."""
    r, sink, be = make()
    bench(be)
    z0 = be.world.z_um
    op_id = r.submit(start(target_state=5, approach_target_um=3200.0))
    failed = sink.wait("preflight_failed", op_id)
    check = next(c for c in failed.data["checks"] if c["name"] == "bench_approach")
    assert not check["ok"] and "partial unlock" in check["why"], check
    assert be.world.z_um == pytest.approx(z0)  # nothing moved
