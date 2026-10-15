"""Synthetic fluorescent sample geometries.

Everything is represented as a cloud of point emitters -- positions in um plus a
relative brightness -- because that is literally what a fluorescent sample is,
and because it lets one renderer handle every shape without special cases.

Coordinates: ``x, y`` lie in the sample plane (origin at the field centre),
``z`` is height above the inner coverglass surface, increasing away from the
objective.  ``z`` therefore doubles as the aberration-inducing depth.

The generators fall into four families:

* **spheres** -- solid and shell, with a size series; the calibration workhorse
* **non-spherical** -- ellipsoids, rods, cubes/octahedra via superellipsoids,
  and randomly lumpy particles built from spherical-harmonic perturbations
* **aggregates** -- raspberry clusters and diffusion-limited fractal aggregates
* **networks** -- worm-like-chain filament meshes, strut networks on a Voronoi
  skeleton, and porous/spinodal textures

Each generator returns :class:`Emitters` and records the parameters it used, so
a dataset can be sliced by geometry afterwards ("how does accuracy depend on
particle size?").
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

Array = np.ndarray


# ---------------------------------------------------------------------------
# container
# ---------------------------------------------------------------------------

@dataclass
class Emitters:
    """A cloud of point fluorophores."""

    xyz: Array                       # (N, 3) float64, um
    weight: Array                    # (N,) float64, relative brightness
    kind: str = "unknown"
    meta: Dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.xyz = np.atleast_2d(np.asarray(self.xyz, dtype=np.float64))
        if self.xyz.size == 0:
            self.xyz = self.xyz.reshape(0, 3)
        if self.xyz.shape[1] != 3:
            raise ValueError(f"xyz must be (N, 3), got {self.xyz.shape}")
        self.weight = np.asarray(self.weight, dtype=np.float64).ravel()
        if self.weight.size == 1 and self.xyz.shape[0] != 1:
            self.weight = np.full(self.xyz.shape[0], float(self.weight[0]))
        if self.weight.size != self.xyz.shape[0]:
            raise ValueError("weight and xyz lengths disagree")

    def __len__(self) -> int:
        return int(self.xyz.shape[0])

    @property
    def x(self) -> Array: return self.xyz[:, 0]
    @property
    def y(self) -> Array: return self.xyz[:, 1]
    @property
    def z(self) -> Array: return self.xyz[:, 2]

    @property
    def total_weight(self) -> float:
        return float(self.weight.sum())

    def bounds(self) -> Array:
        if len(self) == 0:
            return np.zeros((2, 3))
        return np.stack([self.xyz.min(0), self.xyz.max(0)])

    def centroid(self) -> Array:
        if len(self) == 0:
            return np.zeros(3)
        w = self.weight / max(self.weight.sum(), 1e-30)
        return (self.xyz * w[:, None]).sum(0)

    # -- transforms --------------------------------------------------------
    def translate(self, dxyz: Sequence[float]) -> "Emitters":
        return Emitters(self.xyz + np.asarray(dxyz, float), self.weight, self.kind, dict(self.meta))

    def rotate(self, R: Array) -> "Emitters":
        return Emitters(self.xyz @ np.asarray(R, float).T, self.weight, self.kind, dict(self.meta))

    def scale_weight(self, s: float) -> "Emitters":
        return Emitters(self.xyz, self.weight * float(s), self.kind, dict(self.meta))

    def clip_to(self, half_x: float, half_y: float,
                z_range: Optional[Tuple[float, float]] = None) -> "Emitters":
        """Drop emitters outside the rendered volume."""
        m = (np.abs(self.xyz[:, 0]) <= half_x) & (np.abs(self.xyz[:, 1]) <= half_y)
        if z_range is not None:
            m &= (self.xyz[:, 2] >= z_range[0]) & (self.xyz[:, 2] <= z_range[1])
        return Emitters(self.xyz[m], self.weight[m], self.kind, dict(self.meta))

    @staticmethod
    def concat(parts: Sequence["Emitters"], kind: str = "scene") -> "Emitters":
        parts = [p for p in parts if len(p)]
        if not parts:
            return Emitters(np.zeros((0, 3)), np.zeros(0), kind)
        return Emitters(
            np.concatenate([p.xyz for p in parts]),
            np.concatenate([p.weight for p in parts]),
            kind,
            {"parts": [p.meta | {"kind": p.kind} for p in parts]},
        )


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def random_rotation(rng: np.random.Generator) -> Array:
    """Uniform random rotation matrix (QR of a Gaussian matrix, sign-fixed)."""
    q, r = np.linalg.qr(rng.normal(size=(3, 3)))
    return q * np.sign(np.diag(r))


def _rejection_sample(
    inside: Callable[[Array], Array],
    half_extent: Sequence[float],
    n: int,
    rng: np.random.Generator,
    max_batches: int = 200,
) -> Array:
    """Uniformly fill an implicit volume by rejection inside a bounding box."""
    half = np.asarray(half_extent, float)
    out: List[Array] = []
    got = 0
    batch = max(int(n * 2), 256)
    for _ in range(max_batches):
        p = rng.uniform(-1.0, 1.0, size=(batch, 3)) * half
        keep = p[inside(p)]
        if keep.size:
            out.append(keep)
            got += keep.shape[0]
        if got >= n:
            break
    if not out:
        return np.zeros((0, 3))
    return np.concatenate(out)[:n]


def _fibonacci_sphere(n: int) -> Array:
    """Near-uniform points on the unit sphere (for surface labelling)."""
    i = np.arange(n) + 0.5
    phi = np.arccos(1.0 - 2.0 * i / n)
    theta = np.pi * (1.0 + 5.0 ** 0.5) * i
    return np.stack([np.cos(theta) * np.sin(phi), np.sin(theta) * np.sin(phi), np.cos(phi)], -1)


#: Hard ceiling on emitters generated by a single primitive.  Hitting it means
#: the requested labelling density was not honoured, so it is reported rather
#: than applied silently -- see :func:`dino_autofocus.synth.sim.scene.cap_emitters` for the
#: brightness-preserving way to bound cost.
MAX_EMITTERS_PER_PRIMITIVE = 400_000


def _count_from_density(volume_um3: float, density: float, rng: np.random.Generator,
                        n_min: int = 8, n_max: int = MAX_EMITTERS_PER_PRIMITIVE) -> int:
    """Poisson-distributed fluorophore count for a given labelling density."""
    lam = max(volume_um3 * density, 0.0)
    n = int(rng.poisson(lam))
    if n > n_max:
        import warnings
        warnings.warn(
            f"labelling density {density:g} /um^3 over {volume_um3:g} um^3 wants "
            f"{n} emitters; capping at {n_max}. The realised density is lower "
            f"than requested -- lower `density` or shrink the object to stay exact.",
            RuntimeWarning, stacklevel=3,
        )
    return int(np.clip(n, n_min, n_max))


# ---------------------------------------------------------------------------
# family 1: spheres (the size series)
# ---------------------------------------------------------------------------

def solid_sphere(rng: np.random.Generator, radius: float = 0.5,
                 density: float = 3000.0, **_) -> Emitters:
    """Uniformly labelled solid sphere -- a fluorescent bead."""
    vol = 4.0 / 3.0 * np.pi * radius ** 3
    n = _count_from_density(vol, density, rng)
    p = _rejection_sample(lambda q: (q ** 2).sum(-1) <= radius ** 2, [radius] * 3, n, rng)
    return Emitters(p, np.ones(len(p)), "solid_sphere",
                    {"radius": radius, "density": density, "n": len(p)})


def hollow_shell(rng: np.random.Generator, radius: float = 1.0,
                 thickness: float = 0.05, density: float = 3000.0, **_) -> Emitters:
    """Thin fluorescent shell -- a membrane-labelled vesicle or cell."""
    thickness = min(thickness, radius * 0.9)
    r_in = radius - thickness
    vol = 4.0 / 3.0 * np.pi * (radius ** 3 - r_in ** 3)
    n = _count_from_density(vol, density, rng)
    u = rng.uniform(r_in ** 3, radius ** 3, size=n) ** (1.0 / 3.0)
    p = _fibonacci_sphere(n)[rng.permutation(n)] * u[:, None]
    return Emitters(p, np.ones(n), "hollow_shell",
                    {"radius": radius, "thickness": thickness, "n": n})


def sphere_size_series(rng: np.random.Generator, radii: Sequence[float] = (0.1, 0.25, 0.5, 1.0, 2.0),
                       spacing: float = 6.0, density: float = 3000.0,
                       shell: bool = False, **_) -> Emitters:
    """One sphere of each radius, laid out in a row -- a direct size sweep."""
    parts = []
    xs = (np.arange(len(radii)) - (len(radii) - 1) / 2.0) * spacing
    for x, r in zip(xs, radii):
        o = hollow_shell(rng, radius=r, density=density) if shell \
            else solid_sphere(rng, radius=r, density=density)
        parts.append(o.translate([x, 0.0, 0.0]))
    out = Emitters.concat(parts, "sphere_size_series")
    out.meta = {"radii": list(radii), "spacing": spacing, "shell": shell}
    return out


# ---------------------------------------------------------------------------
# family 2: non-spherical particles
# ---------------------------------------------------------------------------

def ellipsoid(rng: np.random.Generator, semi_axes: Sequence[float] = (1.2, 0.6, 0.4),
              density: float = 3000.0, orient: bool = True, **_) -> Emitters:
    """Uniformly labelled ellipsoid -- oblate/prolate anisotropy in one knob."""
    a = np.asarray(semi_axes, float)
    vol = 4.0 / 3.0 * np.pi * float(np.prod(a))
    n = _count_from_density(vol, density, rng)
    p = _rejection_sample(lambda q: ((q / a) ** 2).sum(-1) <= 1.0, a, n, rng)
    e = Emitters(p, np.ones(len(p)), "ellipsoid",
                 {"semi_axes": a.tolist(), "aspect": float(a.max() / a.min()), "n": len(p)})
    return e.rotate(random_rotation(rng)) if orient else e


def superellipsoid(rng: np.random.Generator, semi_axes: Sequence[float] = (0.8, 0.8, 0.8),
                   e1: float = 0.3, e2: float = 0.3, density: float = 3000.0,
                   orient: bool = True, **_) -> Emitters:
    """Superellipsoid family: e -> 1 is an ellipsoid, e -> 0 a cube, e > 2 an octahedron.

    A single continuous knob that spans sphere / cube / octahedron / rounded
    rod, which is convenient for asking how *faceting* affects focus metrics.
    """
    a = np.asarray(semi_axes, float)

    def inside(q: Array) -> Array:
        u = np.abs(q / a)
        with np.errstate(over="ignore", invalid="ignore"):
            f = (u[:, 0] ** (2.0 / e2) + u[:, 1] ** (2.0 / e2)) ** (e2 / e1) + u[:, 2] ** (2.0 / e1)
        return np.nan_to_num(f, nan=np.inf) <= 1.0

    n_target = _count_from_density(8.0 * float(np.prod(a)), density, rng)
    p = _rejection_sample(inside, a, n_target, rng)
    e = Emitters(p, np.ones(len(p)), "superellipsoid",
                 {"semi_axes": a.tolist(), "e1": e1, "e2": e2, "n": len(p)})
    return e.rotate(random_rotation(rng)) if orient else e


def rod(rng: np.random.Generator, length: float = 3.0, radius: float = 0.25,
        density: float = 3000.0, orient: bool = True, **_) -> Emitters:
    """Capsule (spherocylinder) -- nanorod, bacterium, fibre segment."""
    half = max(length / 2.0 - radius, 0.0)

    def inside(q: Array) -> Array:
        zc = np.clip(q[:, 2], -half, half)
        return (q[:, 0] ** 2 + q[:, 1] ** 2 + (q[:, 2] - zc) ** 2) <= radius ** 2

    vol = np.pi * radius ** 2 * (2 * half) + 4.0 / 3.0 * np.pi * radius ** 3
    n = _count_from_density(vol, density, rng)
    p = _rejection_sample(inside, [radius, radius, half + radius], n, rng)
    e = Emitters(p, np.ones(len(p)), "rod",
                 {"length": length, "radius": radius,
                  "aspect": float(length / max(2 * radius, 1e-9)), "n": len(p)})
    return e.rotate(random_rotation(rng)) if orient else e


def lumpy_particle(rng: np.random.Generator, radius: float = 1.0, roughness: float = 0.25,
                   n_modes: int = 6, density: float = 3000.0, surface: bool = False,
                   **_) -> Emitters:
    """Irregular particle: a sphere whose radius is perturbed by random angular modes.

    This is the "realistically non-spherical" case -- no symmetry for a network
    to latch onto, unlike an ellipsoid or a cube.
    """
    dirs = rng.normal(size=(n_modes, 3))
    dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
    amps = rng.normal(scale=roughness, size=n_modes)
    orders = rng.integers(1, 4, size=n_modes)

    def r_of(u: Array) -> Array:                      # u: unit vectors (N, 3)
        r = np.ones(u.shape[0])
        for d, a, k in zip(dirs, amps, orders):
            r += a * np.cos(k * np.arccos(np.clip(u @ d, -1, 1)))
        return radius * np.clip(r, 0.15, 3.0)

    r_max = radius * (1.0 + 3.0 * abs(roughness) + 0.1)
    if surface:
        n = _count_from_density(4 * np.pi * radius ** 2 * 0.06, density, rng)
        u = _fibonacci_sphere(n)[rng.permutation(n)]
        jitter = rng.uniform(0.94, 1.0, size=n)
        p = u * (r_of(u) * jitter)[:, None]
    else:
        def inside(q: Array) -> Array:
            nrm = np.linalg.norm(q, axis=1)
            safe = np.maximum(nrm, 1e-12)
            return nrm <= r_of(q / safe[:, None])
        n = _count_from_density(4.0 / 3.0 * np.pi * radius ** 3, density, rng)
        p = _rejection_sample(inside, [r_max] * 3, n, rng)
    return Emitters(p, np.ones(len(p)), "lumpy_particle",
                    {"radius": radius, "roughness": roughness, "n_modes": n_modes,
                     "surface": surface, "n": len(p)})


# ---------------------------------------------------------------------------
# family 3: aggregates
# ---------------------------------------------------------------------------

def raspberry_cluster(rng: np.random.Generator, n_sub: int = 12, r_sub: float = 0.35,
                      r_core: float = 0.9, density: float = 3000.0, **_) -> Emitters:
    """Sub-particles decorating a core -- the classic 'raspberry' colloid."""
    u = _fibonacci_sphere(max(n_sub, 1))[rng.permutation(max(n_sub, 1))]
    u = u @ random_rotation(rng).T
    parts = [solid_sphere(rng, radius=r_sub, density=density).translate(c * r_core) for c in u]
    out = Emitters.concat(parts, "raspberry_cluster")
    out.meta = {"n_sub": n_sub, "r_sub": r_sub, "r_core": r_core, "n": len(out)}
    return out


def fractal_aggregate(rng: np.random.Generator, n_sub: int = 30, r_sub: float = 0.25,
                      density: float = 3000.0, sticking: float = 1.0,
                      wander: float = 0.0, mode: str = "ballistic", **_) -> Emitters:
    """Aggregate of spheres, in two morphologies that bracket what colloids do.

    ``mode="ballistic"``
        Each new monomer approaches from a random direction and sticks where it
        first touches the cluster.  Compact; measured d_f ~ 2.6-2.8, dropping
        slightly as ``wander`` randomises the approach path.
    ``mode="chain"``
        Self-avoiding chain of contacting monomers, branching occasionally.
        Open and stringy, the regime real soot / protein / nanoparticle
        aggregates occupy: measured d_f settles near 1.9-2.0 for n_sub >= 80.
        Below that the estimator is biased high (2.3-2.4 at n_sub = 20) because
        N ~ (Rg/r)^d_f neglects the prefactor at small monomer counts -- read
        the reported number, not the asymptote, for small clusters.

    The dimension is *measured* from the monomer centres via N ~ (Rg/r)^d_f and
    stored in ``meta["fractal_dimension"]`` rather than assumed, so a dataset
    can be filtered on what was actually generated.
    """
    if mode == "chain":
        return _chain_aggregate(rng, n_sub, r_sub, density, branch=0.15)
    if mode != "ballistic":
        raise ValueError(f"mode must be 'ballistic' or 'chain', got {mode!r}")
    contact = 2.0 * r_sub * sticking
    step = 0.35 * r_sub
    centres = [np.zeros(3)]
    for _ in range(max(n_sub - 1, 0)):
        c = np.asarray(centres)
        d = rng.normal(size=3)
        d /= np.linalg.norm(d)
        far = float(np.linalg.norm(c, axis=1).max()) + 4.0 * r_sub
        q = d * far
        hit = None
        for _ in range(int(4.0 * far / step) + 2):
            if np.any(np.linalg.norm(c - q, axis=1) <= contact):
                hit = q
                break
            drift = -q / max(np.linalg.norm(q), 1e-12)          # towards the cluster
            if wander > 0.0:
                jitter = rng.normal(size=3)
                jitter /= np.linalg.norm(jitter)
                drift = drift + wander * jitter
                drift /= max(np.linalg.norm(drift), 1e-12)
            q = q + drift * step
            if np.linalg.norm(q) > 3.0 * far:                   # wandered off, restart
                q = rng.normal(size=3)
                q *= far / max(np.linalg.norm(q), 1e-12)
        centres.append(hit if hit is not None else d * contact)

    c = np.asarray(centres)
    rg = float(np.sqrt(((c - c.mean(0)) ** 2).sum(1).mean()))
    # mass-fractal dimension from N ~ (Rg / r_sub)^df
    df = float(np.log(max(len(c), 2)) / np.log(max(rg / r_sub, 1.0 + 1e-6))) if rg > r_sub else float("nan")

    parts = [solid_sphere(rng, radius=r_sub, density=density).translate(p_) for p_ in c]
    out = Emitters.concat(parts, "fractal_aggregate")
    out.meta = {"n_sub": n_sub, "r_sub": r_sub, "wander": wander, "mode": "ballistic",
                "radius_gyration": rg, "fractal_dimension": df, "n": len(out)}
    return out


def _chain_aggregate(rng: np.random.Generator, n_sub: int, r_sub: float,
                     density: float, branch: float = 0.15) -> Emitters:
    """Open, stringy aggregate: a self-avoiding chain of touching monomers."""
    centres = [np.zeros(3)]
    tips = [0]
    contact = 2.0 * r_sub
    for _ in range(max(n_sub - 1, 0)):
        anchor = int(rng.choice(tips)) if (rng.random() < branch and len(tips) > 1) else tips[-1]
        base = centres[anchor]
        c = np.asarray(centres)
        placed = None
        for _ in range(40):                        # rejection: no overlap with the chain
            d = rng.normal(size=3)
            d /= np.linalg.norm(d)
            cand = base + d * contact
            if np.min(np.linalg.norm(c - cand, axis=1)) >= contact * 0.98:
                placed = cand
                break
        if placed is None:                          # this tip is buried, retire it
            if len(tips) > 1:
                tips.remove(anchor)
            continue
        centres.append(placed)
        tips.append(len(centres) - 1)
        if len(tips) > 6:
            tips.pop(0)

    c = np.asarray(centres)
    rg = float(np.sqrt(((c - c.mean(0)) ** 2).sum(1).mean()))
    df = float(np.log(max(len(c), 2)) / np.log(max(rg / r_sub, 1.0 + 1e-6))) if rg > r_sub else float("nan")
    parts = [solid_sphere(rng, radius=r_sub, density=density).translate(p_) for p_ in c]
    out = Emitters.concat(parts, "fractal_aggregate")
    out.meta = {"n_sub": len(c), "r_sub": r_sub, "mode": "chain", "branch": branch,
                "radius_gyration": rg, "fractal_dimension": df, "n": len(out)}
    return out


# ---------------------------------------------------------------------------
# family 4: networks
# ---------------------------------------------------------------------------

def _sample_segment(a: Array, b: Array, radius: float, lin_density: float,
                    rng: np.random.Generator) -> Array:
    """Fill one cylindrical strut with emitters."""
    L = float(np.linalg.norm(b - a))
    n = max(int(rng.poisson(max(L * lin_density, 0.0))), 1)
    t = rng.uniform(0.0, 1.0, size=(n, 1))
    axis = (b - a) / max(L, 1e-12)
    # two vectors spanning the cross-section
    tmp = np.array([1.0, 0.0, 0.0]) if abs(axis[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = np.cross(axis, tmp); u /= np.linalg.norm(u)
    v = np.cross(axis, u)
    rr = radius * np.sqrt(rng.uniform(0.0, 1.0, size=n))
    ang = rng.uniform(0.0, 2 * np.pi, size=n)
    return a + t * (b - a) + (rr * np.cos(ang))[:, None] * u + (rr * np.sin(ang))[:, None] * v


def worm_like_chains(rng: np.random.Generator, n_chains: int = 25, length: float = 18.0,
                     persistence: float = 5.0, radius: float = 0.04,
                     extent: Sequence[float] = (20.0, 20.0, 1.5),
                     lin_density: float = 600.0, step: float = 0.2,
                     confine_z: bool = True, **_) -> Emitters:
    """Semi-flexible filaments -- microtubules / actin / collagen fibres.

    The tangent direction performs a random walk on the sphere with correlation
    length ``persistence``, which is the worm-like-chain model.

    A free 3D walk of contour length ``length`` would diffuse far outside the
    thin slab such a sample actually occupies, so with ``confine_z`` the walk
    feels a restoring push back into ``+-extent[2]``.  The in-plane walk is left
    unconstrained and the chain is clipped to the field later.
    """
    ext = np.asarray(extent, float)
    parts = []
    n_steps = max(int(length / step), 2)
    sigma = np.sqrt(2.0 * step / max(persistence, 1e-6))
    half_z = max(float(ext[2]), 1e-6)
    for _ in range(n_chains):
        pos = rng.uniform(-1, 1, size=3) * ext
        d = rng.normal(size=3); d /= np.linalg.norm(d)
        d[2] *= 0.25                                   # filaments lie mostly in-plane
        d /= np.linalg.norm(d)
        pts = [pos.copy()]
        for _ in range(n_steps):
            d = d + rng.normal(scale=sigma, size=3) * np.array([1.0, 1.0, 0.3])
            if confine_z:
                # Ornstein-Uhlenbeck style pull back towards the slab centre
                d[2] -= 1.5 * np.clip(pos[2] / half_z, -3.0, 3.0) * sigma * 4.0
            d /= np.linalg.norm(d)
            pos = pos + d * step
            pts.append(pos.copy())
        pts = np.asarray(pts)
        for a, b in zip(pts[:-1], pts[1:]):
            parts.append(Emitters(_sample_segment(a, b, radius, lin_density, rng), 1.0, "seg"))
    out = Emitters.concat(parts, "worm_like_chains")
    out.meta = {"n_chains": n_chains, "length": length, "persistence": persistence,
                "radius": radius, "n": len(out)}
    return out


def strut_network(rng: np.random.Generator, n_nodes: int = 60, k_neighbours: int = 3,
                  radius: float = 0.08, extent: Sequence[float] = (18.0, 18.0, 2.0),
                  lin_density: float = 500.0, **_) -> Emitters:
    """Open network of straight struts between random nodes (k-nearest graph).

    A reasonable stand-in for hydrogel meshes, foams and vascular casts.
    """
    ext = np.asarray(extent, float)
    nodes = rng.uniform(-1, 1, size=(n_nodes, 3)) * ext
    d2 = ((nodes[:, None, :] - nodes[None, :, :]) ** 2).sum(-1)
    np.fill_diagonal(d2, np.inf)
    edges = set()
    for i in range(n_nodes):
        for j in np.argsort(d2[i])[:k_neighbours]:
            edges.add((min(i, int(j)), max(i, int(j))))
    parts = [Emitters(_sample_segment(nodes[i], nodes[j], radius, lin_density, rng), 1.0, "seg")
             for i, j in edges]
    out = Emitters.concat(parts, "strut_network")
    out.meta = {"n_nodes": n_nodes, "n_edges": len(edges), "k_neighbours": k_neighbours,
                "radius": radius, "n": len(out)}
    return out


def spinodal_texture(rng: np.random.Generator, extent: Sequence[float] = (18.0, 18.0, 1.5),
                     correlation: float = 1.2, fill: float = 0.35,
                     density: float = 400.0, grid: int = 96, **_) -> Emitters:
    """Bicontinuous porous texture from a band-passed Gaussian random field.

    Gives a connected, isotropic network with no straight edges -- the hardest
    case for gradient-based sharpness metrics.
    """
    ext = np.asarray(extent, float)
    nz = max(int(grid * ext[2] / ext[0]), 4)
    field = rng.normal(size=(grid, grid, nz))
    fx = np.fft.fftfreq(grid, d=2 * ext[0] / grid)
    fz = np.fft.fftfreq(nz, d=2 * ext[2] / nz)
    FX, FY, FZ = np.meshgrid(fx, fx, fz, indexing="ij")
    f = np.sqrt(FX ** 2 + FY ** 2 + FZ ** 2)
    f0 = 1.0 / max(correlation, 1e-6)
    filt = np.exp(-((f - f0) ** 2) / (2 * (0.35 * f0) ** 2))
    field = np.real(np.fft.ifftn(np.fft.fftn(field) * filt))
    thr = np.quantile(field, 1.0 - fill)
    idx = np.argwhere(field > thr).astype(np.float64)
    if idx.size == 0:
        return Emitters(np.zeros((0, 3)), np.zeros(0), "spinodal_texture", {})
    cell = np.array([2 * ext[0] / grid, 2 * ext[1] / grid, 2 * ext[2] / nz])
    n_keep = _count_from_density(float(np.prod(2 * ext)) * fill, density, rng)
    pick = rng.choice(len(idx), size=min(n_keep, len(idx) * 4), replace=n_keep > len(idx))
    p = (idx[pick] - np.array([grid, grid, nz]) / 2.0) * cell
    p += rng.uniform(-0.5, 0.5, size=p.shape) * cell
    return Emitters(p, np.ones(len(p)), "spinodal_texture",
                    {"correlation": correlation, "fill": fill, "n": len(p)})


# ---------------------------------------------------------------------------
# reference / calibration targets
# ---------------------------------------------------------------------------

def point_emitters(rng: np.random.Generator, n: int = 40,
                   extent: Sequence[float] = (18.0, 18.0, 0.1),
                   brightness_spread: float = 0.4, **_) -> Emitters:
    """Isolated sub-diffraction beads -- the cleanest possible focus target.

    ``extent[2]`` is deliberately non-zero: an emitter exactly on the glass sits
    on the supercritical-angle singularity of the vectorial pupil, which is a
    numerically awkward (and rarely intended) special case.
    """
    ext = np.asarray(extent, float)
    p = rng.uniform(-1, 1, size=(n, 3)) * ext
    w = np.exp(rng.normal(scale=brightness_spread, size=n))
    return Emitters(p, w, "point_emitters", {"n": n})


def thin_sheet(rng: np.random.Generator, extent: Sequence[float] = (18.0, 18.0),
               tilt: float = 0.0, thickness: float = 0.2, density: float = 120.0,
               correlation: float = 1.0, clumping: float = 0.6, **_) -> Emitters:
    """Textured quasi-2D layer, optionally tilted -- an adherent cell monolayer.

    A tilt makes the whole field impossible to bring into focus at once, which
    is exactly the situation where a scalar "focus score" is ill-defined.
    """
    ext = np.asarray(extent, float)
    n = _count_from_density(float(4 * ext[0] * ext[1] * max(thickness, 0.05)), density, rng)

    # Clump the emitters so the layer has structure rather than white noise.
    # Each emitter belongs either to a Gaussian blob or to a uniform background;
    # blob centres are drawn over a margin-extended area and the result is
    # wrapped back into the extent.  Blending an emitter's uniform position
    # *towards* a uniform centre -- the obvious shortcut -- sums two uniforms
    # into a triangular distribution and silently piles the sample up in the
    # middle of the field, which then reads as vignetting in the render.
    frac_clumped = float(np.clip(clumping, 0.0, 1.0))
    n_clump = int(round(n * frac_clumped))
    n_flat = n - n_clump

    parts = []
    if n_flat:
        parts.append(rng.uniform(-1, 1, size=(n_flat, 2)) * ext)
    if n_clump:
        n_blob = max(int(n_clump / 60), 1)
        centres = rng.uniform(-1, 1, size=(n_blob, 2)) * ext
        which = rng.integers(0, n_blob, size=n_clump)
        pos = centres[which] + rng.normal(scale=correlation, size=(n_clump, 2))
        # periodic wrap keeps the marginal density uniform at the borders
        pos = (pos + ext) % (2 * ext) - ext
        parts.append(pos)
    xy = np.concatenate(parts) if parts else np.zeros((0, 2))

    z = rng.normal(scale=thickness / 2.355, size=len(xy)) + np.tan(np.deg2rad(tilt)) * xy[:, 0]
    return Emitters(np.column_stack([xy, z]), np.ones(len(xy)), "thin_sheet",
                    {"tilt_deg": tilt, "thickness": thickness, "clumping": frac_clumped,
                     "correlation": correlation, "n": len(xy)})


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------

GENERATORS: Dict[str, Callable[..., Emitters]] = {
    # spheres
    "solid_sphere": solid_sphere,
    "hollow_shell": hollow_shell,
    "sphere_size_series": sphere_size_series,
    # non-spherical
    "ellipsoid": ellipsoid,
    "superellipsoid": superellipsoid,
    "rod": rod,
    "lumpy_particle": lumpy_particle,
    # aggregates
    "raspberry_cluster": raspberry_cluster,
    "fractal_aggregate": fractal_aggregate,
    # networks
    "worm_like_chains": worm_like_chains,
    "strut_network": strut_network,
    "spinodal_texture": spinodal_texture,
    # references
    "point_emitters": point_emitters,
    "thin_sheet": thin_sheet,
}

FAMILIES: Dict[str, Tuple[str, ...]] = {
    "spheres": ("solid_sphere", "hollow_shell", "sphere_size_series"),
    "nonspherical": ("ellipsoid", "superellipsoid", "rod", "lumpy_particle"),
    "aggregates": ("raspberry_cluster", "fractal_aggregate"),
    "networks": ("worm_like_chains", "strut_network", "spinodal_texture"),
    "reference": ("point_emitters", "thin_sheet"),
}


def build(name: str, rng: np.random.Generator, **params) -> Emitters:
    """Build one object by registry name."""
    try:
        gen = GENERATORS[name]
    except KeyError:
        raise KeyError(f"unknown geometry {name!r}; available: {sorted(GENERATORS)}") from None
    return gen(rng, **params)


def family_of(name: str) -> str:
    for fam, names in FAMILIES.items():
        if name in names:
            return fam
    return "other"
