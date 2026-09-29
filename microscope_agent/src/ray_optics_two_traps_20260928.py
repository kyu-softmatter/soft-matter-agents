"""Two optical traps on one 5 um bead in ray optics, with the push along the beam (card 050).

    python src/ray_optics_two_traps_20260928.py              # Friday's settings and the draft walk
    python src/ray_optics_two_traps_20260928.py --remedies   # what removes or blocks the push

Touches no device and reads no frame. Written after the person asked, on
2026-09-28, whether the trapping force and stiffness had been computed along z
too, since that force rises sharply when a trap holds a bead at its periphery.
Nothing here had: Friday's stiffness came from the image plane, the simulation
is two-dimensional, and src/diagnose_double_well_20260928.py is one-dimensional.

Each ray of a focused beam is traced to the bead's surface and given Ashkin's
single-ray force (Biophys. J. 61, 569, 1992): a push along the ray and a pull
across it, with every internal reflection summed. Forces are efficiencies,
Q = F c / (n1 P), per unit power entering the objective.

Every result is an estimate on these assumptions, none measured here:
  - ray optics, for a bead whose radius is about three wavelengths in water
  - an aberration-free focus: the spherical aberration of focusing through oil
    into water is IGNORED, so the grip along the beam comes out stronger than a
    real trap's -- which is why this model holds the bead where, the person
    says, a real trap kicks it out
  - the back aperture filled uniformly, NA 1.45 (objective_mrd71970); rays whose
    NA exceeds water's index are lost at the glass
  - relative index 1.572 / 1.333 (polystyrene_refractive_index_1052nm, bulk;
    water_refractive_index_589_26nm_293k -- the store holds no value at 1064 nm);
    circular polarisation, the s and p forces averaged
  - two traps add as independent beams; the push and the pull both scale with
    power, so only the ratio of the two traps' powers enters
"""

from __future__ import annotations

import os
import sys

# The four lines every script in src/ carries: src/ holds operator.py, which
# shadows the standard module for anything imported after it (operator.py's header).
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]

import numpy as np                                               # noqa: E402

N1, N2, NA = 1.333, 1.572, 1.45
NREL = N2 / N1
A_UM = 2.5                                   # bead radius, tracer_diameter_measured / 2

# The ray bundle. Uniform back aperture: weight ~ NA dNA, which in water is
# ~ sin(t) cos(t) dt; the rays between water's index and 1.45 never enter it.
_nt, _nphi = 240, 144
_edges = np.linspace(0.0, min(NA, N1), _nt + 1)
_na = 0.5 * (_edges[1:] + _edges[:-1])
_th = np.arcsin(np.clip(_na / N1, 0, 1 - 1e-12))
_phi = (np.arange(_nphi) + 0.5) * 2 * np.pi / _nphi
_TH, _PH = np.meshgrid(_th, _phi, indexing="ij")
LOST = (NA ** 2 - N1 ** 2) / NA ** 2
_W = np.repeat((_na * np.diff(_edges))[:, None], _nphi, axis=1)
_W = (_W / _W.sum() * (1 - LOST)).reshape(-1)
_U = np.stack([np.sin(_TH) * np.cos(_PH), np.sin(_TH) * np.sin(_PH), np.cos(_TH)], axis=-1).reshape(-1, 3)


def _q(R, th, r):
    T = 1 - R
    den = 1 + R ** 2 + 2 * R * np.cos(2 * r)
    qs = 1 + R * np.cos(2 * th) - T ** 2 * (np.cos(2 * th - 2 * r) + R * np.cos(2 * th)) / den
    qg = R * np.sin(2 * th) - T ** 2 * (np.sin(2 * th - 2 * r) + R * np.sin(2 * th)) / den
    return qs, qg


def force(focus, nrel: float | None = None) -> np.ndarray:
    """Q on a sphere of unit radius at the origin, from one beam focused at `focus`."""
    n = NREL if nrel is None else nrel
    s = np.asarray(focus, dtype=float)
    su = _U @ s
    disc = su ** 2 - s @ s + 1.0
    hit = disc > 0
    u = _U[hit]
    p = s + (-su[hit] - np.sqrt(disc[hit]))[:, None] * u      # where each ray enters
    ci = np.clip(-(u * p).sum(1), 0, 1)
    si = np.sqrt(1 - ci ** 2)
    cr = np.sqrt(np.clip(1 - (si / n) ** 2, 0, 1))
    th, r = np.arcsin(si), np.arcsin(si / n)
    rs = ((ci - n * cr) / (ci + n * cr)) ** 2
    rp = ((cr - n * ci) / (cr + n * ci)) ** 2
    qs_s, qg_s = _q(rs, th, r)
    qs_p, qg_p = _q(rp, th, r)
    qs, qg = 0.5 * (qs_s + qs_p), 0.5 * (qg_s + qg_p)
    across = p - (p * u).sum(1)[:, None] * u                 # from the centre toward the ray
    norm = np.linalg.norm(across, axis=1)
    eg = np.where(norm[:, None] > 1e-12, across / np.maximum(norm, 1e-12)[:, None], 0.0)
    return ((qs[:, None] * u - qg[:, None] * eg) * _W[hit][:, None]).sum(0)


def on_bead(centre, foci, powers, nrel: float | None = None, opposed: bool = False) -> np.ndarray:
    """Total Q on a bead centred at `centre`. `opposed` adds, for every trap, a second beam
    running the other way through the same focus -- a dual-beam trap -- by mirroring in z."""
    c = np.asarray(centre, float)
    total = np.zeros(3)
    for f, pw in zip(foci, powers):
        s = np.asarray(f, float) - c
        total = total + pw * force(s, nrel)
        if opposed:
            qm = force(np.array([s[0], s[1], -s[2]]), nrel)
            total = total + pw * np.array([qm[0], qm[1], -qm[2]])
    return total


def relax(c, foci, powers, iters=400, eta=1.0, ceiling: float | None = None):
    """Overdamped settling in the plane of the traps and the beam, no noise. `ceiling` is the
    highest the bead's centre can go: a glass above it that the push presses the bead against."""
    c = np.array(c, float)
    for _ in range(iters):
        q = on_bead(c, foci, powers)
        c = c + eta * np.array([q[0], 0.0, q[2]])
        pressed = ceiling is not None and c[2] >= ceiling
        if pressed:
            c[2] = ceiling
        if abs(c[2]) > 2.5:
            return c, "lost"
        if abs(q[0]) + (0.0 if pressed and q[2] > 0 else abs(q[2])) < 1e-5:
            return c, "held"
    return c, "held?"


def height_on_axis(nrel: float | None = None, opposed: bool = False) -> float:
    zs = np.linspace(-1.2, 1.2, 481)
    qz = np.array([on_bead((0, 0, z), [(0, 0, 0)], [1], nrel, opposed)[2] for z in zs])
    return float(next(zs[k] for k in range(len(zs) - 1) if qz[k] > 0 and qz[k + 1] <= 0))


def main() -> int:
    z0 = height_on_axis()
    zs = np.linspace(z0, 1.5, 200)
    pull_back = min(on_bead((0, 0, z), [(0, 0, 0)], [1])[2] for z in zs)
    print(f"lost at the glass: {LOST:.3f} of the power")
    print(f"one trap: the bead's centre settles {z0:.2f} a ({z0 * A_UM:.2f} um) above the focus; "
          f"the largest pull back along the beam is Qz {pull_back:.3f}")

    print("\none trap, the bead moved sideways at that height (x in bead radii):")
    print("   x/a    Qx (across)   Qz (along the beam)")
    for x in np.arange(0.0, 1.61, 0.1):
        q = on_bead((x, 0, z0), [(0, 0, 0)], [1])
        print(f"  {x:4.1f}   {q[0]:7.3f}      {q[2]:7.3f}")

    start = (0.0, 0.0, z0)
    trap_1 = (0.0, 0.0, 0.0)

    print("\nFriday's settings, trap_2 raised from 0 in steps of 0.1 with the bead in trap_1:")
    for d_um, target in ((2.0, 1.0), (5.0, 1.0), (2.5, 0.5)):
        c, state = np.array(start), "held"
        for p in np.arange(0.1, target + 1e-9, 0.1):
            c, state = relax(c, [trap_1, (d_um / A_UM, 0, 0)], [1.0, p])
            if state == "lost":
                break
        print(f"  trap_2 at {d_um:.1f} um to power {target:.1f}: {state}; bead {c[0] * A_UM:.2f} um toward "
              f"trap_2, {c[2] * A_UM:.2f} um above the focus")

    print("\nthe draft walk: trap_2 at power 1 walked in from 6 to 1.5 um in 0.25 um steps, and out again:")
    c, state = np.array(start), "held"
    for d_um in list(np.arange(6.0, 1.49, -0.25)) + list(np.arange(1.75, 6.01, 0.25)):
        c, state = relax(c, [trap_1, (d_um / A_UM, 0, 0)], [1.0, 1.0])
        print(f"  trap_2 at {d_um:4.2f} um: {state:<5} bead {c[0] * A_UM:4.2f} um toward trap_2 "
              f"({c[0] * A_UM / d_um:.2f} of the separation), {c[2] * A_UM:.2f} um above the focus")
        if state == "lost":
            break
    return 0


def remedies() -> int:
    """What removes the push, or blocks it, in the same model. Estimates on the same assumptions."""
    print("1. a bead of lower relative index, same size (polystyrene in water is 1.179):")
    print("   n_rel   pull back   push at the periphery   push / pull back")
    for n in (1.05, 1.08, 1.10, 1.12, 1.15, NREL):
        z0 = height_on_axis(n)
        zs = np.linspace(z0, 1.5, 200)
        pull = -min(on_bead((0, 0, z), [(0, 0, 0)], [1], n)[2] for z in zs)
        push = max(on_bead((x, 0, z0), [(0, 0, 0)], [1], n)[2] for x in np.arange(0.0, 1.61, 0.05))
        print(f"   {n:5.3f}     {pull:6.3f}          {push:6.3f}              {push / pull:5.2f}")

    print("\n2. a second beam running the other way through each focus (a dual-beam trap), polystyrene:")
    z0 = height_on_axis(opposed=True)
    for x in (0.0, 0.5, 0.9, 1.0, 1.2):
        q = on_bead((x, 0, z0), [(0, 0, 0)], [1], opposed=True)
        print(f"   focus {x:.1f} radii off centre: across {q[0]:7.3f}, along the beam {q[2]:7.3f}")

    z0 = height_on_axis()
    print(f"\n3. the chamber's upper glass where the free bead's centre sits, {z0 * A_UM:.2f} um above the "
          f"focus; trap_2 at power 1 walked in and out:")
    c, state = np.array([0.0, 0.0, z0]), "held"
    for d_um in list(np.arange(6.0, 1.49, -0.25)) + list(np.arange(1.75, 6.01, 0.25)):
        c, state = relax(c, [(0, 0, 0), (d_um / A_UM, 0, 0)], [1.0, 1.0], ceiling=z0)
        print(f"   trap_2 at {d_um:4.2f} um: {state:<5} bead {c[0] * A_UM:4.2f} um toward trap_2, "
              f"{c[2] * A_UM:.2f} um above the focus")
        if state == "lost":
            break
    unit = N1 * 1e-3 * A_UM * 1e-6 / 2.998e8 / (1.380649e-23 * 293)
    print(f"   the landscape along the line at that height (one unit of U is {unit:.0f} k_B*T per mW per trap):")
    frac = np.linspace(-0.3, 1.3, 161)
    for d_um in (3.5, 3.75, 4.0, 4.25, 4.5, 4.75, 5.0):
        d = d_um / A_UM
        xs = frac * d
        qx = np.array([on_bead((x, 0, z0), [(0, 0, 0), (d, 0, 0)], [1.0, 1.0])[0] for x in xs])
        U = -np.concatenate([[0], np.cumsum(0.5 * (qx[1:] + qx[:-1]) * np.diff(xs))])
        mins = [i for i in range(1, len(U) - 1) if U[i] < U[i - 1] and U[i] <= U[i + 1]]
        maxs = [i for i in range(1, len(U) - 1) if U[i] > U[i - 1] and U[i] >= U[i + 1]]
        line = f"   d {d_um:.2f} um: {len(mins)} well(s), at " + ", ".join(f"{xs[i] * A_UM:.2f}" for i in mins) + " um"
        inner = [i for i in maxs if mins and xs[mins[0]] < xs[i] < xs[mins[-1]]]
        if len(mins) >= 2 and inner:
            b = max(U[i] for i in inner) - U[mins[0]]
            line += f"; barrier out of trap_1's well {b * unit:.0f} k_B*T per mW per trap"
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(remedies() if "--remedies" in sys.argv[1:] else main())
