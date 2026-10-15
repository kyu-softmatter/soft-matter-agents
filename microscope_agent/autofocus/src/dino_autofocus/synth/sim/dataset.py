"""Dataset generation and loading.

One *scene* is one field of view: a sample, an optical system with its own
aberrations, an illumination field and a camera.  From each scene a focal series
is rendered and every plane becomes one training record.

Cost structure, and what it forced
----------------------------------
Rendering dominates everything else, so the label and the training planes share
renders.  A coarse stack over the full scan range supplies the training images;
a short fine scan around its peak pins the label down to a small fraction of a
depth of field.  Rendering an independent high-resolution scan per scene just
to place the label would roughly triple the cost for no gain.

Records are grouped by scene and shards never split a scene, because planes
from one scene are strongly correlated: the sample, the aberrations and the
illumination field are all shared.  Splitting train/validation by *record*
instead of by *scene* leaks the sample into the validation set and reports an
accuracy the model does not have.
"""
from __future__ import annotations

import json
import os
import time
import warnings
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..features import edge as E
from ..features import radial as RD
from ..optics.psf import PSFEngine
from . import geometry as G
from . import metrics as M
from .camera import Sensor, auto_exposure
from .render import FocalShift, Renderer
from .scene import RandomisationConfig, Scene, draw_scene, draw_system

#: Conditioning scalars handed to the network.  Known at acquisition time on
#: any real microscope, so providing them is not cheating -- withholding them
#: would force the model to infer the imaging scale from the sample itself.
COND_NAMES = ("na", "wavelength_um", "pixel_size_um", "dof_um", "log10_signal")
N_COND = len(COND_NAMES)

DESCRIPTOR_NAMES = (
    # edge spread function
    "width_10_90", "edge_centre", "lsf_peak", "lsf_fwhm", "lsf_rms_width",
    "lsf_skew", "overshoot_bright", "overshoot_dark", "overshoot_ratio",
    "asymmetry", "mtf_f50", "mtf_f20", "mtf_f10", "mtf_area",
    # cumulative (integrated) edge profile -- noise-robust, see features.radial
    "leak_total", "leak_0.5", "fill_deficit", "leak_fill_ratio", "p_curvature",
)
N_DESCRIPTORS = len(DESCRIPTOR_NAMES)

#: Encircled-energy descriptors, recorded separately because they come from
#: detected spots rather than boundaries and therefore cover the opposite
#: regime: objects smaller than the PSF, where no edge profile exists.
RADIAL_NAMES = ("r50", "r80", "r90", "e_at_0.1R", "e_at_0.2R", "e_at_0.35R",
                "r80_over_r50")
N_RADIAL = len(RADIAL_NAMES)

#: Channels of the 1-D profile tensor the edge model consumes, in order.
PROFILE_CHANNELS = ("esf", "lsf", "esf_spread", "esf_cumulative")
N_PROFILE_CHANNELS = len(PROFILE_CHANNELS)


def n_scalar_features(esf_samples: int = 65, ee_radii: int = 32) -> int:
    """Length of the scalar feature vector fed alongside the 1-D profiles.

    Layout: edge descriptors, encircled-energy descriptors, the encircled-energy
    curve itself, then the two validity flags.  The flags are included on
    purpose -- a zeroed feature block and a genuinely flat one are not the same
    thing, and without the flag the model cannot tell them apart.
    """
    return N_DESCRIPTORS + N_RADIAL + ee_radii + 2


@dataclass
class DatasetConfig:
    #: FFT threads per scene.  Generation parallelises over *scenes*, so letting
    #: each scene's FFTs also spawn threads oversubscribes the machine: measured
    #: at 3.6 s/scene wall clock with 9 processes x multithreaded FFT, against
    #: 1.3 s/scene with the FFTs pinned to one thread each.
    fft_workers: int = 1
    psf_cache_size: int = 16            # bounded; see PSFEngine.cache_size
    #: "cpu", or a torch device ("cuda") for the PSF and convolution work; see
    #: PSFEngine.  The label search, camera and features stay on the CPU.
    device: str = "cpu"
    gpu_dtype: str = "complex128"
    fov_px: int = 224
    oversampling: Optional[int] = None
    pad: int = 2
    n_planes: int = 17                  # training planes per scene
    #: Put the middle plane exactly on the label (dz = 0) instead of jittering it,
    #: so every stack holds one in-focus frame.  Off by default: it adds a spike
    #: at dz = 0 to the label distribution.  The other planes stay jittered.
    focus_plane: bool = False
    scan_span_dof: float = 14.0         # half-range of the emitted scan, in DoF
    global_step_dof: float = 1.5        # coarse-scan spacing for the global search
    #: Half-width of the label search window, in DoF, *added* to the span the
    #: sample's own depth spread implies.  Scanning the entire wrap-free domain
    #: is safe but wasteful: once the focal-shift model includes its constant
    #: term (see FocalShift) the predicted centre is accurate to ~0.2 DoF, and
    #: the `edge_peak` gate fired on 0 of 18 scenes -- i.e. the window was far
    #: wider than needed.  The gate stays as the safety net, so narrowing this
    #: trades compute for a detectable, not a silent, failure.
    search_margin_dof: float = 7.0
    ambiguity_ratio: float = 0.5        # 2nd peak this close to the 1st is ambiguous
    ambiguity_separation_dof: float = 2.0
    #: Minimum prominence of the focus peak, in robust standard deviations of
    #: the focus curve itself.  A scene whose curve is flat has no focus to
    #: find: `argmax_parabolic` then returns a value tied to wherever the scan
    #: window happened to sit, so relabelling the same scene from a window
    #: shifted by 4.9 DoF moved the label by exactly 4.9 DoF.  Requiring real
    #: prominence is what separates "focus is here" from "there is no focus".
    min_peak_prominence: float = 4.0
    refine_planes: int = 9              # planes per label-refinement pass
    refine_passes: int = 2              # successive narrowing passes
    max_label_residual_dof: float = 0.6 # above this the label is marked unusable
    keep_dim_probability: float = 0.15  # fraction of signal-free scenes retained
    label_metric: str = "brenner"
    depth_bin: float = 0.5
    esf_samples: int = 65
    esf_half_width_dof: float = 2.5     # profile half-length, in DoF
    ee_radii: int = 32                  # encircled-energy sample count
    ee_max_radius_dof: float = 4.0
    min_snr: float = 3.0                # below this a frame is marked invalid
    max_saturated: float = 0.2
    randomisation: RandomisationConfig = field(default_factory=RandomisationConfig)

    def to_dict(self) -> Dict:
        d = asdict(self)
        return d


# ---------------------------------------------------------------------------
# one scene
# ---------------------------------------------------------------------------

def render_scene(seed: int, cfg: DatasetConfig,
                 system_name: Optional[str] = None) -> Optional[Dict[str, np.ndarray]]:
    """Draw and render one scene.  Returns per-plane arrays, or None on failure."""
    rng = np.random.default_rng(seed)
    shape = (cfg.fov_px, cfg.fov_px)

    # A provisional draw is needed only to learn the raster geometry before the
    # sample can be scattered over it.  It uses its own generator seeded the
    # same way, so `draw_scene` below still sees an untouched `rng` and the
    # scene it produces is reproducible from `seed` alone.
    probe_sys, _ = draw_system(np.random.default_rng(seed), cfg.randomisation, system_name)
    probe = PSFEngine(probe_sys, fov_px=cfg.fov_px, oversampling=cfg.oversampling,
                      pad=cfg.pad, workers=cfg.fft_workers,
                      cache_size=cfg.psf_cache_size)
    grid_um, fov_um = probe.n_grid * probe.dx, cfg.fov_px * probe_sys.pixel_size_sample

    scene: Scene = draw_scene(rng, cfg.randomisation, cfg.fov_px, grid_um, fov_um,
                              shape, system_name)
    sysm = scene.system
    dof = sysm.depth_of_field

    eng = PSFEngine(sysm, fov_px=cfg.fov_px, oversampling=cfg.oversampling,
                    pad=cfg.pad, aberration=scene.aberration, workers=cfg.fft_workers,
                    cache_size=cfg.psf_cache_size, device=cfg.device,
                    gpu_dtype=cfg.gpu_dtype)
    rend = Renderer(eng, depth_bin=cfg.depth_bin,
                    focal_shift=FocalShift(eng, depth_max=20.0, mode="analytic"),
                    illumination_field=scene.illumination_field)

    # Two different ranges, for two different jobs.  `search` covers the whole
    # wrap-free domain so the label's global argmax does not depend on where the
    # window was placed; `span` is the narrower window of planes actually
    # emitted as training data, centred on the label once it is known.
    span_cap = rend.max_safe_defocus
    span = min(cfg.scan_span_dof * dof, span_cap)
    em = scene.emitters

    if scene.is_empty or len(em) == 0:
        best = float("nan")
        stage = np.linspace(-span, span, cfg.n_planes)
        flux = np.zeros((cfg.n_planes,) + shape)
        rival_ratio = rival_gap = prominence = 0.0
        ambiguous = edge_peak = False
    else:
        splats = rend._splat(em)
        if not splats:
            return None

        def score_at(z: float) -> float:
            return M.focus_score(rend.render_flux(em, float(z), splats=splats),
                                 cfg.label_metric)

        # ---- phase 1: global coarse scan -----------------------------------
        # A local bracket walk is not good enough.  Focus curves on real samples
        # have several local maxima -- from structure at different depths, and
        # from shot noise reading as sharpness on dim defocused frames -- so a
        # walk converges to whichever peak it started nearest.  Measured by
        # labelling the same scene from two different starting points, 4 of 14
        # scenes landed on peaks 16-19 DoF apart, while the 10 that agreed
        # agreed to 0.007 DoF.  So the coarse search has to be global.  It is
        # also cheaper: a walk cost up to 65 renders, this costs about 21.
        centre = float(rend.shift(float(np.median(em.z))))
        # The sample's own depth spread maps to a spread in best focus through
        # the focal-shift slope; everything beyond that plus a margin is window
        # the scan does not need.
        depth_spread = float(np.ptp(rend.shift(em.z))) if len(em) > 1 else 0.0
        search = min(span_cap, 0.5 * depth_spread + cfg.search_margin_dof * dof)
        n_global = int(np.ceil(2.0 * search / (cfg.global_step_dof * dof))) + 1
        n_global = int(np.clip(n_global, 9, 81))
        zs = centre + np.linspace(-search, search, n_global)
        sc = np.array([score_at(float(z)) for z in zs])
        j = int(sc.argmax())
        coarse = M.argmax_parabolic(zs, sc)

        # Does the curve actually have a peak?  Measure the winner's height
        # against the curve's own robust spread rather than against its range,
        # which any monotone drift would satisfy.
        med = float(np.median(sc))
        mad = float(np.median(np.abs(sc - med)))
        spread = 1.4826 * mad if mad > 0 else float(np.std(sc))
        prominence = float((sc[j] - med) / spread) if spread > 1e-30 else 0.0

        # how contested is the winner?  A second peak of comparable height, far
        # from the first, means this scene has no single best-focus plane; that
        # is a property of the sample, not an error, so it is recorded.
        interior = np.arange(1, n_global - 1)
        local = interior[(sc[1:-1] >= sc[:-2]) & (sc[1:-1] >= sc[2:])]
        rival_ratio, rival_gap = 0.0, 0.0
        rivals = [k for k in local
                  if abs(zs[k] - zs[j]) >= cfg.ambiguity_separation_dof * dof]
        # A peak on the window edge means the true maximum lies outside the
        # wrap-free domain, so no label on this raster can be trusted.
        edge_peak = (j == 0) or (j == n_global - 1)
        if rivals:
            k = max(rivals, key=lambda i: sc[i])
            denom = sc[j] - sc.min()
            rival_ratio = float((sc[k] - sc.min()) / denom) if denom > 0 else 0.0
            rival_gap = float(abs(zs[k] - zs[j]) / dof)
        ambiguous = bool(rival_ratio >= cfg.ambiguity_ratio or edge_peak
                         or prominence < cfg.min_peak_prominence)

        # ---- phase 2: refine the label -------------------------------------
        # Narrow successively from the global peak's own neighbours.  A single
        # fixed refinement window is not enough: if it is narrower than the
        # coarse step it can sit entirely on one flank, and the parabolic fit
        # then returns that window's edge.
        lo, hi = float(zs[max(j - 1, 0)]), float(zs[min(j + 1, n_global - 1)])
        best = coarse
        for _ in range(max(cfg.refine_passes, 1)):
            zf = np.linspace(lo, hi, cfg.refine_planes)
            sf = np.array([score_at(float(z)) for z in zf])
            jf = int(sf.argmax())
            best = M.argmax_parabolic(zf, sf)
            lo, hi = float(zf[max(jf - 1, 0)]), float(zf[min(jf + 1, len(zf) - 1)])
            if hi - lo < 1e-3:
                break

        # ---- phase 3: emit training planes, straddling focus ---------------
        # Positions are jittered off the lattice on purpose: a fixed grid of
        # defocus values lets a model exploit the discretisation instead of
        # reading the blur, and it makes the reported error look better than it is.
        edges = np.linspace(-span, span, cfg.n_planes + 1)
        offs = rng.uniform(edges[:-1], edges[1:])
        if cfg.focus_plane:
            # drawn first and overwritten, so the other planes match a run without it
            offs[cfg.n_planes // 2] = 0.0
        stage = best + offs
        flux = np.stack([rend.render_flux(em, float(z), splats=splats) for z in stage])

        # a dim scene costs as much to render as a bright one and teaches only
        # the validity head; keep a few, drop the rest
        peak_flux = float(flux.max())
        if peak_flux <= 0 and rng.random() > cfg.keep_dim_probability:
            return None

    # ---- camera ----
    cam = sysm.camera
    ref = flux[int(np.argmax(flux.max(axis=(1, 2))))] if flux.max() > 0 else flux[0]
    exposure = auto_exposure(ref, cam, target_fill=scene.exposure_fill,
                             max_exposure=sysm.illumination.exposure * 20)
    sensor = Sensor(cam, shape, rng)
    bg = sysm.illumination.background

    adu = np.empty((len(stage),) + shape, dtype=np.uint16)
    snr = np.empty(len(stage)); sat = np.empty(len(stage))
    for k, f in enumerate(flux):
        bleached = f * (1.0 - scene.bleach_per_frame) ** k
        adu[k] = sensor.expose(bleached, exposure, background=bg)
        snr[k] = sensor.snr(bleached, exposure, background=bg)
        sat[k] = float(np.mean(adu[k] >= cam.adu_max - 0.5))

    dz = stage - best if np.isfinite(best) else np.full(len(stage), np.nan)
    dz_dof = dz / dof

    # Independent check of the label against the emitted planes: fit the focus
    # peak on this stack and see how far it sits from dz = 0.  The residual is
    # stored rather than asserted away, so a training run can filter on label
    # quality and a bad scene is visible instead of merely wrong.
    label_residual = 0.0
    if np.isfinite(best) and flux.max() > 0:
        order = np.argsort(stage)
        curve_chk = M.focus_curve(flux[order], cfg.label_metric)
        label_residual = float(
            (M.argmax_parabolic(stage[order], curve_chk) - best) / dof)

    valid = (np.isfinite(dz) & (snr >= cfg.min_snr) & (sat <= cfg.max_saturated)
             & (np.abs(dz_dof) <= cfg.scan_span_dof)
             & (abs(label_residual) <= cfg.max_label_residual_dof)
             & (not ambiguous))

    # normalised sharpness from the noiseless render: 1 at best focus
    if flux.max() > 0:
        sc = M.focus_curve(flux, cfg.label_metric)
        sharp = (sc - sc.min()) / max(sc.max() - sc.min(), 1e-30)
    else:
        sharp = np.zeros(len(stage))

    # ---- conditioning + edge features ----
    signal = np.maximum(flux.reshape(len(stage), -1).mean(axis=1) * exposure * cam.qe, 1e-6)
    cond = np.stack([
        np.full(len(stage), sysm.objective.na),
        np.full(len(stage), sysm.illumination.wavelength),
        np.full(len(stage), sysm.pixel_size_sample),
        np.full(len(stage), dof),
        np.log10(signal),
    ], axis=1).astype(np.float32)

    esf = np.zeros((len(stage), cfg.esf_samples), np.float32)
    lsf = np.zeros_like(esf); espread = np.zeros_like(esf)
    cumul = np.zeros_like(esf)
    e_valid = np.zeros(len(stage), bool)
    desc = np.zeros((len(stage), N_DESCRIPTORS), np.float32)
    ee = np.zeros((len(stage), cfg.ee_radii), np.float32)
    ee_valid = np.zeros(len(stage), bool)
    ee_desc = np.zeros((len(stage), N_RADIAL), np.float32)
    hw = cfg.esf_half_width_dof * max(dof, 1e-6)
    ee_max_r = cfg.ee_max_radius_dof * max(dof, 1e-6)
    for k in range(len(stage)):
        frame = adu[k].astype(np.float64)
        prof = E.extract(frame, sysm.pixel_size_sample,
                         half_width=hw, n_samples=cfg.esf_samples)
        if prof.valid:
            e_valid[k] = True
            esf[k], lsf[k], espread[k] = prof.esf, prof.lsf, prof.esf_std
            p_cum, cum_desc = RD.cumulative_edge_profile(prof.offsets, prof.esf)
            cumul[k] = p_cum
            merged = dict(prof.descriptors) | cum_desc
            desc[k] = [np.nan_to_num(merged.get(n, 0.0), nan=0.0,
                                     posinf=0.0, neginf=0.0) for n in DESCRIPTOR_NAMES]
        # encircled energy covers the sub-diffraction case the edge method cannot
        radial = RD.encircled_energy(frame, sysm.pixel_size_sample,
                                     max_radius=ee_max_r, n_radii=cfg.ee_radii)
        if radial.valid:
            ee_valid[k] = True
            ee[k] = radial.energy
            ee_desc[k] = [np.nan_to_num(radial.descriptors.get(n, 0.0), nan=0.0,
                                        posinf=0.0, neginf=0.0) for n in RADIAL_NAMES]

    p = scene.params
    return {
        "image": adu,
        "dz_um": dz.astype(np.float32),
        "dz_dof": dz_dof.astype(np.float32),
        "stage_um": stage.astype(np.float32),
        "best_stage_um": np.full(len(stage), best, np.float32),
        "valid": valid,
        "sharpness": sharp.astype(np.float32),
        "snr": snr.astype(np.float32),
        "saturated": sat.astype(np.float32),
        "cond": cond,
        "esf": esf, "lsf": lsf, "esf_spread": espread, "esf_cumulative": cumul,
        "edge_valid": e_valid, "descriptors": desc,
        "encircled": ee, "encircled_valid": ee_valid, "radial_descriptors": ee_desc,
        "rival_peak_ratio": np.full(len(stage), rival_ratio, np.float32),
        "rival_peak_gap_dof": np.full(len(stage), rival_gap, np.float32),
        "ambiguous": np.full(len(stage), ambiguous, bool),
        "edge_peak": np.full(len(stage), edge_peak, bool),
        "peak_prominence": np.full(len(stage), prominence, np.float32),
        "label_residual_dof": np.full(len(stage), label_residual, np.float32),
        "scene_id": np.full(len(stage), seed, np.int64),
        "geometry": np.array([p["geometry"]] * len(stage)),
        "family": np.array([G.family_of(p["geometry"])] * len(stage)),
        "system": np.array([p["system"]] * len(stage)),
        "dof_um": np.full(len(stage), dof, np.float32),
        "_scene_params": p,
    }


# ---------------------------------------------------------------------------
# sharding
# ---------------------------------------------------------------------------

_WORKER: Dict[str, object] = {}


def _init_worker(cfg: DatasetConfig, system_name: Optional[str]) -> None:
    _WORKER["cfg"] = cfg
    _WORKER["system"] = system_name
    warnings.filterwarnings("ignore", category=RuntimeWarning)


def _run_scene(seed: int):
    cfg = _WORKER["cfg"]; system_name = _WORKER["system"]
    try:
        return render_scene(seed, cfg, system_name)
    except Exception as exc:                      # a bad draw must not kill the run
        return {"_error": f"{type(exc).__name__}: {exc}", "_seed": seed}


def generate(
    out_dir: str | Path,
    n_scenes: int,
    cfg: Optional[DatasetConfig] = None,
    seed0: int = 0,
    shard_size: int = 32,
    workers: Optional[int] = None,
    system_name: Optional[str] = None,
    progress: bool = True,
    resume: bool = True,
) -> Dict:
    """Generate a sharded dataset.  Shards never split a scene.

    With ``resume`` and no ``manifest.json`` yet, shards already in ``out_dir``
    (from an interrupted run) are kept: their scenes are skipped and new shards
    are numbered after them.  An unreadable shard -- one cut off mid-write by an
    older version that wrote in place -- is deleted and its scenes redone.
    Scenes the gates dropped are not recorded, so they are drawn again.
    """
    cfg = cfg or DatasetConfig()
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    workers = workers if workers is not None else max(os.cpu_count() - 1, 1)
    seeds = list(range(seed0, seed0 + n_scenes))

    t0 = time.time()
    results: List[Dict] = []
    errors: List[str] = []
    shard, n_records, n_shards = [], 0, 0

    if resume and not (out / "manifest.json").exists():
        done: set = set()
        for p in out.glob("tmp_shard_*.npz"):
            p.unlink()
        for p in sorted(out.glob("shard_*.npz")):
            try:
                with np.load(p, allow_pickle=True) as z:
                    done.update(int(s) for s in np.unique(z["scene_id"]))
                    n_records += len(z["dz_um"])
                n_shards = max(n_shards, int(p.stem.split("_")[1]) + 1)
            except Exception:
                p.unlink()
        if done:
            seeds = [s for s in seeds if s not in done]
            if progress:
                print(f"resuming: {len(done)} scenes in {n_shards} shards kept, "
                      f"{len(seeds)} to go", flush=True)

    def flush() -> None:
        nonlocal shard, n_shards, n_records
        if not shard:
            return
        keys = [k for k in shard[0] if not k.startswith("_")]
        payload = {k: np.concatenate([s[k] for s in shard]) for k in keys}
        payload["scene_params"] = np.array(
            [json.dumps(s["_scene_params"]) for s in shard], dtype=object)
        path = out / f"shard_{n_shards:05d}.npz"
        tmp = out / f"tmp_{path.name}"            # outside the shard_*.npz glob
        np.savez_compressed(tmp, **payload)
        os.replace(tmp, path)                     # a kill never leaves half a shard
        n_records += len(payload["dz_um"]); n_shards += 1
        shard = []

    if workers > 1:
        import multiprocessing as mp
        ctx = mp.get_context("spawn")
        with ctx.Pool(workers, initializer=_init_worker, initargs=(cfg, system_name)) as pool:
            for i, r in enumerate(pool.imap_unordered(_run_scene, seeds, chunksize=1)):
                if r is None:
                    continue
                if "_error" in r:
                    errors.append(f"seed {r['_seed']}: {r['_error']}")
                    continue
                shard.append(r)
                if len(shard) >= shard_size:
                    flush()
                if progress and (i + 1) % 10 == 0:
                    el = time.time() - t0
                    print(f"  {i + 1}/{n_scenes} scenes  {el:6.1f}s  "
                          f"{el / (i + 1):5.2f}s/scene  {len(errors)} errors", flush=True)
    else:
        _init_worker(cfg, system_name)
        for i, s in enumerate(seeds):
            r = _run_scene(s)
            if r is None:
                continue
            if "_error" in r:
                errors.append(f"seed {r['_seed']}: {r['_error']}")
                continue
            shard.append(r)
            if len(shard) >= shard_size:
                flush()
            if progress and (i + 1) % 5 == 0:
                el = time.time() - t0
                print(f"  {i + 1}/{n_scenes} scenes  {el:6.1f}s  {el / (i + 1):5.2f}s/scene",
                      flush=True)
    flush()

    manifest = {
        "n_scenes_requested": n_scenes, "n_shards": n_shards, "n_records": n_records,
        "seed0": seed0, "config": cfg.to_dict(), "errors": errors,
        "cond_names": list(COND_NAMES), "descriptor_names": list(DESCRIPTOR_NAMES),
        "radial_names": list(RADIAL_NAMES),
        "elapsed_s": time.time() - t0,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    if progress:
        print(f"wrote {n_records} records in {n_shards} shards to {out} "
              f"({manifest['elapsed_s']:.1f}s, {len(errors)} scene errors)")
    return manifest


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------

class ShardedArrays:
    """Lazily concatenated view over npz shards, with scene-aware splitting."""

    def __init__(self, root: str | Path, keys: Optional[Sequence[str]] = None) -> None:
        self.root = Path(root)
        self.paths = sorted(self.root.glob("shard_*.npz"))
        if not self.paths:
            raise FileNotFoundError(f"no shards in {self.root}")
        self.manifest = json.loads((self.root / "manifest.json").read_text())
        self._data: Dict[str, np.ndarray] = {}
        self._keys = keys
        self._load()

    def _load(self) -> None:
        buckets: Dict[str, List[np.ndarray]] = {}
        for p in self.paths:
            with np.load(p, allow_pickle=True) as z:
                names = self._keys or [k for k in z.files if k != "scene_params"]
                for k in names:
                    buckets.setdefault(k, []).append(z[k])
        self._data = {k: np.concatenate(v) for k, v in buckets.items()}

    def __getitem__(self, k: str) -> np.ndarray:
        return self._data[k]

    def __contains__(self, k: str) -> bool:
        return k in self._data

    @property
    def keys(self) -> List[str]:
        return sorted(self._data)

    def __len__(self) -> int:
        return len(next(iter(self._data.values())))

    def scene_split(self, fractions: Sequence[float] = (0.8, 0.1, 0.1),
                    seed: int = 0) -> List[np.ndarray]:
        """Split record indices by *scene*, never by record.

        Planes from one scene share the sample, the aberration state and the
        illumination field, so a record-level split would put near-duplicates on
        both sides and inflate validation accuracy.
        """
        sid = self._data["scene_id"]
        uniq = np.unique(sid)
        rng = np.random.default_rng(seed)
        rng.shuffle(uniq)
        cuts = np.cumsum(np.asarray(fractions, float) / np.sum(fractions))[:-1]
        groups = np.split(uniq, (cuts * len(uniq)).astype(int))
        return [np.flatnonzero(np.isin(sid, g)) for g in groups]

    def family_split(self, held_out: Sequence[str]) -> Tuple[np.ndarray, np.ndarray]:
        """Split by geometry family -- the cross-geometry generalisation test.

        Training on one family and testing on another is the experiment that
        distinguishes a model that learned the optics from one that memorised
        the synthetic sample statistics.
        """
        fam = self._data["family"].astype(str)
        held = np.isin(fam, list(held_out))
        return np.flatnonzero(~held), np.flatnonzero(held)

    def summary(self) -> str:
        lines = [f"{len(self)} records from {len(np.unique(self._data['scene_id']))} scenes"]
        for k in ("geometry", "family", "system"):
            if k in self._data:
                v, c = np.unique(self._data[k].astype(str), return_counts=True)
                lines.append(f"  {k}: " + ", ".join(f"{a}={b}" for a, b in zip(v, c)))
        if "valid" in self._data:
            lines.append(f"  valid: {int(self._data['valid'].sum())} "
                         f"({100 * self._data['valid'].mean():.1f}%)")
        if "edge_valid" in self._data:
            lines.append(f"  edge profile found: {int(self._data['edge_valid'].sum())} "
                         f"({100 * self._data['edge_valid'].mean():.1f}%)")
        if "encircled_valid" in self._data:
            lines.append(f"  encircled energy found: {int(self._data['encircled_valid'].sum())} "
                         f"({100 * self._data['encircled_valid'].mean():.1f}%)")
        for k in ("ambiguous", "edge_peak"):
            if k in self._data:
                lines.append(f"  {k}: {int(self._data[k].sum())} "
                             f"({100 * self._data[k].mean():.1f}%)")
        if "dz_dof" in self._data:
            d = self._data["dz_dof"][self._data.get("valid", np.ones(len(self), bool))]
            if d.size:
                lines.append(f"  |dz| range: {np.nanmin(np.abs(d)):.2f} - "
                             f"{np.nanmax(np.abs(d)):.2f} DoF")
        return "\n".join(lines)
