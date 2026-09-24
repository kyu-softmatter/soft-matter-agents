"""Card 033's run: one real acquisition, the person moving the microscope by hand.

NOT THE PLAN DISPATCHER, and the run log says so in words (card 033 3b). Two
gaps make the dispatcher unable to carry this run honestly: the device
registry has no Micro-Manager labels, so `Aura` and `Kinetix_red` raise
GapError at preflight; and `derive_commands` never produces `params.settings`,
so `micromanager.apply()` would verify nothing. Going through it would look
like a checked run and not be one. This route is for card 033's run only.

The six conditions 3b sets, and where each is held:

  1. every command is built FIRST, as a list, and passes
     `Orchestrator.check_software_motion` before the first goes out -- COMMANDS
     below, checked in `main()` before the load
  2. only GuardedCore touches the instrument; `loadSystemConfiguration` is the
     one named exception and runs once -- `micromanager.load_configuration`
  3. everything is logged through the orchestrator's `record()`
  4. the log says it did not come through the dispatcher, and why -- NOT_DISPATCHED
  5. the person approves the checked list and the first-frame intensity before
     the light goes on -- gate `approve_light`
  6. this file is committed with the run

GATES. Where the person has to act or decide, the script prints `GATE <name>`
and waits for `<frames>/<run_id>/gates/<name>.json`, written from the chat
with the person's own words in it. It never proceeds on a timer: a manual step
closed by a timeout is a step nobody performed (2.1 rule 5). Any answer other
than `yes` stops the run, on the safe side.

SHUTDOWN, on finish and on any failure: Aura `State=0` first and read
back, then the line off. Shutters before power.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]

import argparse                                                  # noqa: E402
import hashlib                                                   # noqa: E402
import importlib.util                                            # noqa: E402
import json                                                      # noqa: E402
import subprocess                                                # noqa: E402
import time                                                      # noqa: E402
from datetime import datetime, timezone                          # noqa: E402
from pathlib import Path                                         # noqa: E402

AGENT = Path(__file__).resolve().parent.parent
REPO = AGENT.parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)                              # type: ignore[union-attr]
    return module


orch = _load("_orchestrator_033", AGENT / "src" / "orchestrator.py")
mm = _load("_micromanager_033", AGENT / "src" / "devices" / "micromanager.py")

CONFIG = Path(r"C:\agentic_microscope\config\micromanager\single_cam_red_noDMD_nocom10.cfg")
CONFIG_SHA256 = "8184073e31e1a7a63731932a20a622131d4dba04cf839bc9e651bf9abcd53120"
FRAMES_ROOT = Path(r"D:\soft-matter-agents-frames")

LIGHT, CAMERA = "Aura", "Kinetix_red"   # the Aura III, by the person's word (033 at 18e5456)
#: The prior project's reading of the line name, downgraded (033 rulings): it
#: is confirmed off the device after the load and the run stops if the device
#: does not report it. The list below has to be built before the load, so it
#: names the line it expects and the device then has to agree.
LINE = "GREEN"
LINE_I = f"{LINE}_Intensity"
DECLARED_OBJECTIVE = "3-Plan Apo LmbdD0.8 20x"

# The plan's numbers, as the person set them for the pre-measurement (card 016,
# plan-mic-20260920-001): 100 ms exposure, 100 per-mille first frame, 600 frames.
EXPOSURE_MS = 100.0
FIRST_INTENSITY = 100                 # per-mille: the person's 10%, not 10
SERIES_FRAMES = 600
DARK_SEQUENCE_FRAMES = 20

NOT_DISPATCHED = (
    "This run did NOT come through the plan dispatcher (operator.run). Card 033 section 3b "
    "OK'd a session script for this card's run only, because (1) the device registry "
    "carries no Micro-Manager labels, so Aura and Kinetix_red raise GapError at "
    "preflight, and (2) derive_commands never produces params.settings, so "
    "micromanager.apply() would verify nothing. The script is "
    "microscope_agent/src/session_033.py, committed with this run.")


def C(step: str, device: str, prop: str | None, value, action: str = "set_property"):
    params = {"settings": {device: {prop: value}}} if prop is not None else {}
    return orch.Command(channel=device, action=action, params=params,
                        from_field=f"card-033:{step}")


#: EVERY command this script issues, in order, built before anything is sent.
COMMANDS = [
    C("s2-autoshutter", "Core", "AutoShutter", 0),
    C("s5-binning", CAMERA, "Binning", "1x1"),
    C("s4.9-exposure", CAMERA, None, None, action="set_exposure"),
    C("s4.3-dark-master", LIGHT, "State", 0),
    C("s4.3-dark-line-off", LIGHT, LINE, 0),
    C("s4.3-dark-intensity-0", LIGHT, LINE_I, 0),
    C("s4.3-dark-frame-a", CAMERA, None, None, action="snap_image"),
    C("s4.3-line-max-master-off", LIGHT, LINE, 1),
    C("s4.4-intensity-max", LIGHT, LINE_I, 1000),
    C("s4.3-dark-frame-b", CAMERA, None, None, action="snap_image"),
    C("s4.4-intensity-first", LIGHT, LINE_I, FIRST_INTENSITY),
    C("s4.8-dark-sequence", CAMERA, None, None, action="acquire_series"),
    C("s4.5-line-on", LIGHT, LINE, 1),
    C("s4.5-light-on", LIGHT, "State", 1),
    C("s4.6-lit-frame", CAMERA, None, None, action="snap_image"),
    C("s4.5-light-off", LIGHT, "State", 0),
    C("s4.7-saturation-exposure", CAMERA, None, None, action="set_exposure"),
    C("s4.7-saturation-frame", CAMERA, None, None, action="snap_image"),
    C("s5-series-light-on", LIGHT, "State", 1),
    C("s5-series", CAMERA, None, None, action="acquire_series"),
    C("shutdown-master-off", LIGHT, "State", 0),
    C("shutdown-line-off", LIGHT, LINE, 0),
    C("shutdown-intensity-0", LIGHT, LINE_I, 0),
]


class Stop(RuntimeError):
    """The run stops here, on the safe side, and says why."""


class Session:
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.o = orch.Orchestrator(backend="micromanager")
        self.frames = FRAMES_ROOT / run_id
        self.gates = self.frames / "gates"
        self.frame_files: list[dict] = []
        self.loaded = False

    # -- logging and gates -------------------------------------------------- #

    def rec(self, **fields) -> dict:
        event = self.o.record(**fields)
        print(json.dumps(event, default=str)[:600], flush=True)
        return event

    def gate(self, name: str, question: str) -> dict:
        """Wait for the person's answer. Anything but yes stops the run."""
        self.gates.mkdir(parents=True, exist_ok=True)
        path = self.gates / f"{name}.json"
        self.rec(event="gate_open", gate=name, question=question)
        print(f"GATE {name}: {question}", flush=True)
        while not path.exists():
            time.sleep(1.0)
        time.sleep(0.2)
        answer = json.loads(path.read_text(encoding="utf-8"))
        self.rec(event="gate_answered", gate=name, answer=answer.get("answer"),
                 by=answer.get("by"), said=answer.get("said"), relayed_by=answer.get("relayed_by"))
        if str(answer.get("answer", "")).lower() != "yes":
            raise Stop(f"gate {name}: the person answered {answer.get('answer')!r}")
        return answer

    # -- instrument primitives, all through GuardedCore ---------------------- #

    def core(self):
        return mm._core()

    def set(self, step: str, device: str, prop: str, value) -> dict:
        got = mm.set_and_read(device, prop, value)
        self.rec(event="apply", channel=device, action="set_property",
                 params={f"{device}.{prop}": {"value": value, "from": f"card-033:{step}"}},
                 read=got["read"], verification="readback" if got["verified"] else "none",
                 verification_note=("queried after the write and matched" if got["verified"]
                                    else f"read back {got['read']!r}, not {value!r}"),
                 **{"from": f"card-033:{step}"})
        if not got["verified"]:
            raise Stop(f"{device}.{prop} read back {got['read']!r} after {value!r} was written")
        return got

    def save(self, label: str, image, meta: dict | None = None) -> dict:
        import numpy as np
        self.frames.mkdir(parents=True, exist_ok=True)
        path = self.frames / f"{label}.npy"
        np.save(path, image)
        entry = {"label": label, "path": str(path), "sha256": _sha(path),
                 "shape": list(image.shape), "dtype": str(image.dtype), **(meta or {})}
        self.frame_files.append(entry)
        return entry

    def snap(self, step: str, label: str):
        import numpy as np
        image, meta = mm.snap()
        saved = self.save(label, image, meta)
        stats = _stats(image)
        self.rec(event="acquire", channel=CAMERA, action="snap", frame=saved, stats=stats,
                 verification="none", verification_note="a frame is data, not a setting",
                 **{"from": f"card-033:{step}"})
        return np.asarray(image), stats

    # -- the run ------------------------------------------------------------ #

    def preload(self) -> None:
        running = _processes(("Tweez300", "ImageJ", "java.exe", "javaw.exe"))
        self.rec(event="process_check", holders_found=running,
                 note="PVCAM gives a camera to one process; the tweezers GUI opens a Kinetix body")
        self.gate("preload", (
            "Before anything connects: the Micro-Manager program is closed, the tweezers "
            "program (all Tweez300 processes) is closed, the trapping laser is off at its hand "
            "control, and the LUN-F laser combiner is off at its own power. Also know this: the "
            "first check sets the green line to FULL intensity with the light engine's master "
            "switch OFF, to prove the master switch keeps it dark. If that switch did not gate, "
            "that field would be lit and bleached. Proceed?"))
        running = _processes(("Tweez300", "ImageJ", "java.exe", "javaw.exe"))
        if running:
            raise Stop(f"still running after the person's answer: {running}")

    def load(self) -> None:
        digest = _sha(CONFIG)
        if digest != CONFIG_SHA256:
            raise Stop(f"{CONFIG} hashes {digest}, not the {CONFIG_SHA256} card 033 describes; "
                       "re-read it before loading")
        self.rec(event="decision", topic="startup_preset",
                 decision=("the person accepts the configuration's Startup preset "
                           "LappMainBranch1 State=1 moving at load: 'accept it, load the file as "
                           "chosen'"), recorded_in="card 033 at 02d269b, relayed by "
                           "manager-microscope-20260924-1")
        self.rec(event="decision", topic="micro_manager_install",
                 decision=("load against pymmcore-plus's own Micro-Manager copy; confirmed by the "
                           "person to this seat in chat, 2026-09-24"))
        info = mm.load_configuration(str(CONFIG))
        self.loaded = True
        self.rec(event="configuration_loaded", **info,
                 note="loadSystemConfiguration is the one unguarded call (033 3b condition 2)")
        self.rec(event="note", topic="pixel_size_in_frame_metadata",
                 pixel_size_um_reported=_safe(self.core().getPixelSizeUm),
                 note=("frame metadata carries a pixel size stamped from the loaded "
                       "configuration's PixelSize block. It is NOT a source: any pixel size "
                       "comes from the store's pixel_size_20x_zoom_1x through the librarian "
                       "(card 033 section 5, 3ef97a4)"))
        self.rec(event="apply", channel="LappMainBranch1", action="load_time_startup_preset",
                 params={"LappMainBranch1.State": {
                     "value": 1, "from": f"{CONFIG.name}:ConfigGroup,System,Startup"}},
                 **{"from": f"{CONFIG.name}:ConfigGroup,System,Startup"},
                 verification="none", verification_note="read back in the next event")
        core = self.core()
        lapp = core.getProperty("LappMainBranch1", "State")
        self.rec(event="read", channel="LappMainBranch1", property="State", read=lapp,
                 matches_startup_preset=str(lapp) == "1")
        if not info["autoshutter"]["verified"]:
            raise Stop(f"AutoShutter did not read back 0: {info['autoshutter']}")
        self.rec(event="apply", channel="Core", action="set_property",
                 params={"Core.AutoShutter": {"value": 0, "from": "card-033:s2-autoshutter"}},
                 verification="readback", verification_note="getAutoShutter False and property 0",
                 **{"from": "card-033:s2-autoshutter"})

    def checks(self) -> dict:
        import numpy as np
        core = self.core()
        loaded = set(core.getLoadedDevices())
        missing = sorted({LIGHT, CAMERA} - loaded)
        self.rec(event="step", step="4.1", loaded=sorted(loaded), missing=missing)
        if missing:
            raise Stop(f"the loaded configuration has no {missing}; a gap, not a retry")

        # What the person set by hand, read -- reading is not motion.
        stand = {}
        for dev in ("Nosepiece", "IntermediateMagnification", "LightPath", "FilterTurret1",
                    "FilterTurret2", "LappMainBranch1", "CondenserTurret"):
            try:
                stand[dev] = {"state": core.getState(dev), "label": core.getStateLabel(dev)}
            except Exception as exc:                                  # noqa: BLE001
                stand[dev] = {"error": str(exc)}
        self.rec(event="stand_read", stand=stand, declared_objective=DECLARED_OBJECTIVE,
                 note="the person declared the 20x; this is the read-back of that declaration")
        if stand.get("Nosepiece", {}).get("label") != DECLARED_OBJECTIVE:
            raise Stop(f"declared {DECLARED_OBJECTIVE!r}, the nosepiece reads {stand.get('Nosepiece')}")

        names = list(core.getDevicePropertyNames(LIGHT))
        self.rec(event="light_engine_properties", names=names)
        if LINE not in names or LINE_I not in names:
            raise Stop(f"the light engine reports no {LINE}/{LINE_I}; it reports {names}. "
                       "Which line is green comes from the device -- ask the person")
        upper = core.getPropertyUpperLimit(LIGHT, LINE_I) if core.hasPropertyLimits(LIGHT, LINE_I) else None
        self.rec(event="step", step="4.4", property=LINE_I, has_limits=upper is not None,
                 upper_limit=upper, expected=1000)
        if upper is not None and float(upper) != 1000.0:
            raise Stop(f"{LINE_I} upper limit is {upper}, not 1000; per-mille is not confirmed")

        cam_props = {p: _safe(core.getProperty, CAMERA, p) for p in core.getDevicePropertyNames(CAMERA)}
        self.rec(event="camera_properties", properties=cam_props)
        self.set("s5-binning", CAMERA, "Binning", "1x1")
        exp = mm.set_exposure(EXPOSURE_MS)
        self.rec(event="apply", channel=CAMERA, action="set_exposure",
                 params={"exposure": {"value": EXPOSURE_MS, "unit": "ms",
                                      "from": "card-033:s4.9-exposure"}},
                 read=exp["read_ms"], verification="readback" if exp["verified"] else "none",
                 **{"from": "card-033:s4.9-exposure"})
        if not exp["verified"]:
            raise Stop(f"exposure read back {exp['read_ms']} ms after {EXPOSURE_MS}")

        # 4.3 -- dark is dark, with the Lapp mirror in the state the run uses.
        self.set("s4.3-dark-master", LIGHT, "State", 0)
        self.set("s4.3-dark-line-off", LIGHT, LINE, 0)
        self.set("s4.3-dark-intensity-0", LIGHT, LINE_I, 0)
        a1, sa1 = self.snap("s4.3-dark-frame-a", "dark_a1")
        a2, sa2 = self.snap("s4.3-dark-frame-a", "dark_a2")
        self.set("s4.3-line-max-master-off", LIGHT, LINE, 1)
        self.set("s4.4-intensity-max", LIGHT, LINE_I, 1000)
        b, sb = self.snap("s4.3-dark-frame-b", "dark_b_line_max_master_off")
        self.set("s4.4-intensity-first", LIGHT, LINE_I, FIRST_INTENSITY)
        read_noise = float(np.std(a2.astype(float) - a1.astype(float)) / np.sqrt(2))
        d_mean = float(sb["mean"] - sa1["mean"])
        d_p999 = float(sb["p99.9"] - sa1["p99.9"])
        dark_ok = abs(d_mean) < read_noise and abs(d_p999) < 3 * read_noise
        self.rec(event="step", step="4.3", read_noise_adu=read_noise, delta_mean_adu=d_mean,
                 delta_p999_adu=d_p999, criterion="|dmean| < read noise and |dp99.9| < 3 x read noise",
                 dark_matches=dark_ok, lapp_state=core.getProperty("LappMainBranch1", "State"))
        if not dark_ok:
            raise Stop("the frame with the line at full and the master switch off is not dark")
        self.set("shutdown-line-off", LIGHT, LINE, 0)

        # 4.8 -- ImageNumber has no gaps, dark.
        seq = self.sequence("s4.8-dark-sequence", "dark_sequence", DARK_SEQUENCE_FRAMES)
        if seq["gaps"] or seq["received"] != DARK_SEQUENCE_FRAMES:
            raise Stop(f"dark sequence: {seq['received']}/{DARK_SEQUENCE_FRAMES}, gaps {seq['gaps']}")
        return {"read_noise_adu": read_noise, "dark_mean_adu": sa1["mean"]}

    def sequence(self, step: str, label: str, n: int) -> dict:
        import numpy as np
        core = self.core()
        h, w = core.getImageHeight(), core.getImageWidth()
        depth = core.getBytesPerPixel()
        dtype = np.uint16 if depth == 2 else np.uint8
        self.frames.mkdir(parents=True, exist_ok=True)
        path = self.frames / f"{label}.npy"
        stack = np.lib.format.open_memmap(path, mode="w+", dtype=dtype, shape=(int(n), h, w))
        metas: list[dict] = []

        def sink(i, image, meta):
            stack[i] = image.reshape(h, w)
            metas.append(meta)

        core.setCircularBufferMemoryFootprint(int(min(64000, 2 * n * h * w * depth / 1e6 + 500)))
        out = mm.sequence(n, sink)
        stack.flush()
        del stack
        meta_path = self.frames / f"{label}_metadata.json"
        meta_path.write_text(json.dumps(metas), encoding="utf-8")
        entry = {"label": label, "path": str(path), "sha256": _sha(path),
                 "metadata_path": str(meta_path), "metadata_sha256": _sha(meta_path),
                 "shape": [int(n), h, w], "dtype": str(np.dtype(dtype))}
        self.frame_files.append(entry)
        self.rec(event="acquire", channel=CAMERA, action="acquire_series", frames=entry,
                 wanted=out["wanted"], received=out["received"], gaps=out["gaps"],
                 overflowed=out["overflowed"], image_numbers_first_last=(
                     out["image_numbers"][:1] + out["image_numbers"][-1:]),
                 verification="none", verification_note="frames are data; ImageNumber is the check",
                 **{"from": f"card-033:{step}"})
        return out

    def light(self, dark: dict) -> None:
        self.gate("approve_light", (
            f"The checked command list is in the log ({len(COMMANDS)} commands, all passed the "
            f"software-motion check). The light goes on now: green line at {FIRST_INTENSITY} "
            f"per-mille (10%), exposure {EXPOSURE_MS:g} ms, one frame, then off. Nothing caps "
            "excitation intensity in the safety file; this low start is the card's instruction, "
            "not an enforced limit. Do you approve?"))
        self.set("s4.4-intensity-first", LIGHT, LINE_I, FIRST_INTENSITY)
        self.set("s4.5-line-on", LIGHT, LINE, 1)
        self.set("s4.5-light-on", LIGHT, "State", 1)
        _, lit = self.snap("s4.6-lit-frame", "lit_first")
        self.set("s4.5-light-off", LIGHT, "State", 0)
        changed = lit["mean"] - dark["dark_mean_adu"]
        core = self.core()
        image_changed = changed > 5 * dark["read_noise_adu"]
        self.rec(event="step", step="4.6", lit_mean_minus_dark_adu=changed,
                 image_changed=image_changed,
                 serial=_serial(core), note=("which body: compare this serial with the store's "
                                             "camera_bodies_are_told_apart_by_serial"))
        if not image_changed:
            # 033 section 4 step 5: DO NOT TURN IT UP. Which branch the Aura
            # comes in on is unknown and the Lapp mirror set at load decides
            # which branch reaches the sample, so darkness here may be the
            # path, not the light. Chasing a signal with intensity is how full
            # power reaches a sample. A dark result is a finding; ask the person.
            raise Stop("the frame stayed dark with the Aura on at low intensity. Not turned up: "
                       "this may be the light path (Lapp branch), not the light. Recorded; "
                       "the person decides")

    def saturation(self) -> None:
        answer = self.gate("saturate", (
            "Bit depth needs one saturated frame WITHOUT the green excitation. Please raise the "
            "dia lamp at the stand by hand (bright, on an empty or out-of-focus area), then say "
            "yes. Say no to skip and bit depth is recorded as unmeasured."))
        exposure = float(answer.get("exposure_ms", 500.0))
        exp = mm.set_exposure(exposure)
        self.rec(event="apply", channel=CAMERA, action="set_exposure",
                 params={"exposure": {"value": exposure, "unit": "ms",
                                      "from": "card-033:s4.7-saturation-exposure"}},
                 read=exp["read_ms"], verification="readback" if exp["verified"] else "none",
                 **{"from": "card-033:s4.7-saturation-exposure"})
        _, st = self.snap("s4.7-saturation-frame", "saturated")
        top = int(st["max"])
        self.rec(event="step", step="4.7", max_adu=top, bits=top.bit_length(),
                 pixel_type=_safe(self.core().getProperty, CAMERA, "PixelType"),
                 saturated_fraction=st["frac_at_max"],
                 note="bit depth from the saturated frame's maximum, not from PixelType")
        exp = mm.set_exposure(EXPOSURE_MS)
        if not exp["verified"]:
            raise Stop("exposure did not return to the planned value")
        self.gate("dia_lamp_down", "Please turn the dia lamp back off at the stand, then say yes.")

    def series(self) -> None:
        self.gate("fresh_field", (
            "Move to a FRESH field of particles by hand and focus by eye, without the green "
            f"light. Say yes when ready: the green line then goes on at {FIRST_INTENSITY} "
            f"per-mille for {SERIES_FRAMES} frames at {EXPOSURE_MS:g} ms "
            f"({SERIES_FRAMES * EXPOSURE_MS / 1000:g} s), then off."))
        self.set("s4.4-intensity-first", LIGHT, LINE_I, FIRST_INTENSITY)
        self.set("s4.5-line-on", LIGHT, LINE, 1)
        self.set("s5-series-light-on", LIGHT, "State", 1)
        try:
            out = self.sequence("s5-series", "particles_series", SERIES_FRAMES)
        finally:
            self.set("shutdown-master-off", LIGHT, "State", 0)
        if out["gaps"] or out["received"] != SERIES_FRAMES:
            raise Stop(f"series: {out['received']}/{SERIES_FRAMES}, gaps {out['gaps']}")

    def shutdown(self, reason: str) -> None:
        """State=0 first, read back, then the line off. Shutters before power (2.1)."""
        if not self.loaded:
            return
        for step, prop, value in (("shutdown-master-off", "State", 0),
                                  ("shutdown-line-off", LINE, 0),
                                  ("shutdown-intensity-0", LINE_I, 0)):
            try:
                self.set(step, LIGHT, prop, value)
            except Exception as exc:                                  # noqa: BLE001
                self.rec(event="shutdown_failed", step=step, error=str(exc))
        self.rec(event="shutdown", reason=reason)

    def write(self, outcome: str) -> Path:
        record = {
            "artifact": "run_log", "schema_version": "0.1", "run_id": self.run_id,
            # NOT A VALID RUN LOG, deliberately (card 033 section 6). The schema
            # requires plan_id as a string and no plan fits this run; a
            # made-up id would be a record claiming a plan that did not exist.
            # So the log is in the run-log shape with plan_id null, says why
            # in words, and lives beside the frames -- outside the tree --
            # until architecture answers the schema question.
            "plan_id": None, "revision": None,
            "no_plan_because": NO_PLAN_BECAUSE,
            "not_dispatched": NOT_DISPATCHED,
            "approval": {"id": None, "kind": None},
            "stop_criteria": [],
            **self.o.log_header(),
            "events": self.o.log,
            "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        record["events"].append({"t_mono": self.o.clock.offset(), "time_base": "software",
                                 "event": "run_end", "outcome": outcome,
                                 "not_dispatched": NOT_DISPATCHED, "frames": self.frame_files})
        self.frames.mkdir(parents=True, exist_ok=True)
        path = self.frames / "log.json"
        if path.exists():
            raise Stop(f"{path} exists; runs are never overwritten (P9)")
        path.write_text(json.dumps(record, indent=2, default=str) + "\n", encoding="utf-8")
        return path


NO_PLAN_BECAUSE = (
    "No plan fits this run, so none is named (card 033 section 6). The only pre-measurement "
    "plan, plan-mic-20260920-001, is written for the 100x oil objective with software-driven "
    "turret and focus steps, and its axis ranges were computed for that configuration; a new "
    "revision citing 100x ranges for this 20x, hand-moved run would be laundering. A new "
    "question for the 20x bare-particle pre-measurement will cite this run as its acquisition. "
    "run_log.schema.json requires plan_id as a string; that is raised to architecture, and "
    "until it is answered this log lives beside the frames, outside the repository.")


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def _stats(image) -> dict:
    import numpy as np
    a = np.asarray(image)
    top = int(a.max())
    return {"mean": float(a.mean()), "std": float(a.std()), "min": int(a.min()), "max": top,
            "p99.9": float(np.percentile(a, 99.9)), "frac_at_max": float((a == top).mean())}


def _safe(fn, *args):
    try:
        return fn(*args)
    except Exception as exc:                                          # noqa: BLE001
        return f"<unreadable: {exc}>"


def _serial(core) -> dict:
    out = {}
    for prop in core.getDevicePropertyNames(CAMERA):
        if "serial" in prop.lower() or prop.lower() in {"cameraname", "chipname", "camera"}:
            out[prop] = _safe(core.getProperty, CAMERA, prop)
    return out


def _processes(needles) -> list[str]:
    try:
        text = subprocess.run(["tasklist"], capture_output=True, text=True, timeout=30).stdout
    except Exception as exc:                                          # noqa: BLE001
        return [f"<tasklist failed: {exc}>"]
    return sorted({line.split()[0] for line in text.splitlines()
                   if line and any(n.lower() in line.lower() for n in needles)})


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--run-id", required=True)
    p.add_argument("--checks-only", action="store_true",
                   help="stop after the before-light checks, with the light never on")
    p.add_argument("--check-list-only", action="store_true",
                   help="check the command list and exit; opens no device")
    args = p.parse_args(argv)

    s = Session(args.run_id)
    s.rec(event="not_dispatched", note=NOT_DISPATCHED)
    s.rec(event="command_list", commands=[
        {"from": c.from_field, "device": c.channel, "action": c.action,
         "settings": (c.params or {}).get("settings")} for c in COMMANDS])
    missed = mm.named_refusals_hold()
    if missed:
        raise Stop(f"named devices the allow-list would not refuse: {missed}")
    s.o.check_software_motion(COMMANDS)          # condition 1: the whole list, first
    if args.check_list_only:
        print(f"command list: {len(COMMANDS)} commands passed the software-motion check")
        return 0
    outcome = "incomplete"
    try:
        s.preload()
        s.load()
        dark = s.checks()
        if args.checks_only:
            outcome = "checks_passed"
        else:
            s.light(dark)
            s.saturation()
            s.series()
            outcome = "complete"
    except Stop as exc:
        outcome = f"stopped: {exc}"
        s.rec(event="stopped", reason=str(exc))
    except Exception as exc:                                          # noqa: BLE001
        outcome = f"failed: {type(exc).__name__}: {exc}"
        s.rec(event="failed", error=outcome)
    finally:
        s.shutdown(outcome)
        log = s.write(outcome)
        print(f"RUN END {outcome}; log {log} sha256 {_sha(log)}", flush=True)
    return 0 if outcome in ("complete", "checks_passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
