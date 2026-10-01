"""Run when src/bleach_backend.py or src/estimator_bleach.py changes.

    pixi run -e sim python -m src.check_bleach_backend      # from simulation_agent/

Three cases, and the first is the reason this file exists.

1. **Labels follow tags, not rows.** HOOMD sorts its particle arrays, so a
   bead's row changes during a run, and a dark label kept by row lands on
   whichever bead moved into that row. The first scratch run did that: half
   the beads read as permanently dark. `rows_in_tag_order` must return the
   same xy for every bead however the rows are shuffled. **The control is
   part of the check:** the row-index reader that caused the bug must FAIL
   the same assertion. If the control passes, the assertion tests nothing and
   the check exits non-zero.
2. **The same on the engine**, when HOOMD is importable. The sorter is
   forced to run every step and the beads are nearly frozen (a step of
   1e-9 diffusive times). One read comes before the first sort and one
   after: positions read by tag must not move between them, while the rows
   do. The row reader is the control again, and here it
   must see the beads jump. This case is skipped, and the skip is said, when
   the engine is absent.
3. **The mock reproduces the closed form** on a small free run: the mean
   fitted D over curves lies within a factor 2 of Stokes-Einstein (a smoke
   test, not the integrator check, which is the plan's).

Exit 0 when every case holds. Nothing is written anywhere.
"""

from __future__ import annotations

import sys

import numpy as np

from . import bleach_backend


def _row_reader(tag, position, n):
    """The bug, kept as the control: xy by row, ignoring tags."""
    return np.asarray(position)[:n, :2].copy()


def case_tags() -> str:
    rng = np.random.default_rng(11)
    n = 200
    true_xy = rng.uniform(-5, 5, (n, 2))
    pos = np.column_stack([true_xy, np.zeros(n)])
    perm = rng.permutation(n)                  # a sort moved row i to perm[i]
    rows_pos, rows_tag = pos[perm], np.arange(n)[perm]
    got = bleach_backend.rows_in_tag_order(rows_tag, rows_pos, n)
    assert np.array_equal(got, true_xy), "rows_in_tag_order does not return positions in tag order"
    control = _row_reader(rows_tag, rows_pos, n)
    if np.array_equal(control, true_xy):
        raise SystemExit("CONTROL PASSED: the row reader satisfied the assertion, so it tests nothing")
    return "tags: by-tag read is invariant under a row shuffle; the row reader fails it (control)"


def case_engine() -> str:
    try:
        import hoomd                                     # noqa: PLC0415
    except ImportError:
        return "engine: SKIPPED, hoomd not importable in this interpreter"
    n = 4000
    sim = hoomd.Simulation(device=hoomd.device.CPU(), seed=3)
    snap = hoomd.Snapshot()
    snap.configuration.box = [60, 60, 20, 0, 0, 0]
    snap.particles.N = n
    snap.particles.types = ["t"]
    snap.particles.position[:] = np.random.default_rng(3).uniform(-0.5, 0.5, (n, 3)) * [60, 60, 20]
    sim.create_state_from_snapshot(snap)
    br = hoomd.md.methods.Brownian(filter=hoomd.filter.All(), kT=1.0)
    br.gamma["t"] = 1.0
    sim.operations.integrator = hoomd.md.Integrator(dt=1e-9, methods=[br])
    sorters = [t for t in sim.operations.tuners if isinstance(t, hoomd.tune.ParticleSorter)]
    if sorters:
        sorters[0].trigger = hoomd.trigger.Periodic(1)
    else:
        sim.operations.tuners.append(hoomd.tune.ParticleSorter(trigger=hoomd.trigger.Periodic(1)))

    def read(reader):
        with sim.state.cpu_local_snapshot as s:
            return reader(s.particles.tag, s.particles.position, n)

    # The first read comes BEFORE any sort: the rows are still in the
    # snapshot's random order. A sort orders by position, so frozen beads
    # re-sort into the same order every time after the first -- reading after
    # it would compare one sorted order with itself and test nothing (the
    # control caught exactly that on the first try).
    a_tag, a_row = read(bleach_backend.rows_in_tag_order), read(_row_reader)
    sim.run(5)
    b_tag, b_row = read(bleach_backend.rows_in_tag_order), read(_row_reader)
    by_tag = float(np.abs(b_tag - a_tag).max())
    by_row = float(np.abs(b_row - a_row).max())
    assert by_tag < 1e-3, f"read by tag, frozen beads moved {by_tag:g} sigma between reads"
    if by_row < 1e-3:
        raise SystemExit("CONTROL PASSED: the engine never reordered rows, so case 2 tested nothing; "
                         "the sorter was not forced")
    return (f"engine: frozen beads read by tag move {by_tag:.1e} sigma; read by row they jump "
            f"{by_row:.1f} sigma (control), HOOMD {hoomd.version.version}")


def case_mock() -> str:
    b = bleach_backend.BleachMockBackend(seed=5)
    um = 1e-6
    w = 3.0
    params = {
        "temperature": 293.0, "viscosity": 1e-3, "bead_diameter": 100e-9,
        "bleach_radius": w * um, "box_length": 10 * w * um, "chamber_depth": 10 * um,
        "n_particles": 3183, "integration_timestep": 0.005, "frame_interval": 0.1,
        "bleach_duration": 0.05, "bleach_rate": 40.0, "max_recovery_time": 6.0,
        "pre_bleach_frames": 5, "record_length": 4 * 7.0, "curve_period": 7.0,
    }
    b.apply(params)
    b._worker.join()
    assert b.state == bleach_backend.COMPLETE, f"mock ended {b.state}: {b.failure}"
    s = b.observables(params)["summary"]
    expect = 1.380649e-23 * 293.0 / (3 * np.pi * 1e-3 * 100e-9)
    ratio = s["D_mean"] / expect
    assert 0.5 < ratio < 2.0, f"mock mean D is {ratio:.2f} of Stokes-Einstein over {s['n_reported']} curves"
    return f"mock: {s['n_reported']}/{s['n_curves']} curves reported, mean D / Stokes-Einstein = {ratio:.2f}"


if __name__ == "__main__":
    for fn in (case_tags, case_engine, case_mock):
        print(fn())
    sys.exit(0)
