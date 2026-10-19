"""Card 038's run: five minutes of continuous green, one frame a second.

A preparatory run like card 033's, and it reuses that run's session: the same
allow-list, configuration, AutoShutter first, stand read-back and full
before-light checks, the master-off dark test included. `session_033.py` is
imported, not edited -- it is the record of what ran as run-20260924-001 and
-002.

What differs from 033, and why:

- PACED SNAPS, NOT A SEQUENCE. The sequence call cannot pace one frame a
  second (interval_ms is ignored and the frame period equals the exposure). So
  frame `i` is scheduled at `t0 + i * PERIOD_S` from the integer `i`, never from
  an accumulated sum, and taken with snapImage. Each frame's actual monotonic
  time is logged, and a late frame is recorded as late, not re-timed.
- SNAPS CARRY NO ImageNumber. The frame count is the loop index plus the
  timestamps, and the log says so.
- THE LIGHT STAYS ON for the whole 300 s (card 038), matching run -002's dose.
  Frame 0 is the lit check: if it is not brighter than dark, the run stops and
  does NOT turn the light up (033 section 4 step 5).
- NO SEPARATE LIT FRAME AND NO SATURATION STEP. Card 038 does not ask for
  either, and a lit check before the series would bleach the fresh field
  before its first frame.
- THE APPROVED LIST IS WRITTEN FIRST, to microscope_agent/runs/<run_id>/
  commands.json (LF), before the approve_light gate, and the log names it from
  the start. The log beside the frames and the one in runs/ are the same
  bytes; nothing is added afterwards.
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
import time                                                      # noqa: E402
from datetime import datetime, timezone                          # noqa: E402
from pathlib import Path                                         # noqa: E402

AGENT = Path(__file__).resolve().parent.parent
REPO = AGENT.parent

_spec = importlib.util.spec_from_file_location("_session_033", AGENT / "src" / "session_033.py")
s033 = importlib.util.module_from_spec(_spec)
sys.modules["_session_033"] = s033
_spec.loader.exec_module(s033)                                   # type: ignore[union-attr]
orch, mm, C = s033.orch, s033.mm, s033.C
LIGHT, CAMERA, LINE, LINE_I = s033.LIGHT, s033.CAMERA, s033.LINE, s033.LINE_I
Stop = s033.Stop

FIRST_INTENSITY = 100            # per-mille, as run -002
EXPOSURE_MS = 100.0
PERIOD_S = 1                     # one frame a second (the person's word)
SERIES_FRAMES = 300              # five minutes

NO_PLAN_BECAUSE = (
    "No plan fits this run, so none is named (card 038, as card 033 section 6). The only "
    "pre-measurement plan, plan-mic-20260920-001, is written for the 100x oil objective with "
    "software-driven turret and focus steps, and its axis ranges were computed for that "
    "configuration; a revision citing them for this 20x, hand-moved run would launder them. "
    "Card 034's plan for the 20x question cites this run as an acquisition.")
NOT_DISPATCHED = (
    "This run did NOT come through the plan dispatcher (operator.run). Card 038 carries card "
    "033 section 3b's route to this run: the device registry has no Micro-Manager labels, so "
    "Aura and Kinetix_red raise GapError at preflight, and derive_commands never produces "
    "params.settings, so micromanager.apply() would verify nothing. The script is "
    "microscope_agent/src/session_038.py, committed before the run.")
NO_IMAGE_NUMBER = (
    "Frames here are single snaps, and snaps carry no ImageNumber. The frame count is the "
    "integer loop index; each frame's scheduled time (t0 + i x 1 s, from the integer), its "
    "actual monotonic time and any camera timestamp the driver returns are logged beside it.")

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
    C("shutdown-line-off", LIGHT, LINE, 0),
    C("s4.8-dark-sequence", CAMERA, None, None, action="acquire_series"),
    C("s4.5-line-on", LIGHT, LINE, 1),
    C("s038-light-on", LIGHT, "State", 1),
    C("s038-paced-series", CAMERA, None, None, action="snap_image"),
    C("shutdown-master-off", LIGHT, "State", 0),
    C("shutdown-intensity-0", LIGHT, LINE_I, 0),
]


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Session038(s033.Session):

    def __init__(self, run_id: str) -> None:
        super().__init__(run_id)
        self.runs_dir = AGENT / "runs" / run_id
        self.commands_path = self.runs_dir / "commands.json"
        self.approved: dict | None = None

    def write_commands(self) -> None:
        """The list the person is shown, written before the gate that approves it."""
        listed = [{"from": c.from_field, "device": c.channel, "action": c.action,
                   "settings": (c.params or {}).get("settings")} for c in COMMANDS]
        self.runs_dir.mkdir(parents=True, exist_ok=False)
        self.commands_path.write_bytes((json.dumps(listed, indent=2) + "\n").encode("utf-8"))
        self.approved = {"path": f"microscope_agent/runs/{self.run_id}/commands.json",
                         "sha256": _sha(self.commands_path),
                         "approved_by": "not yet: the approve_light gate had not been answered"}
        self.rec(event="command_list", commands=listed, written_to=self.approved["path"],
                 sha256=self.approved["sha256"])

    def preload(self) -> None:
        holders = s033._processes(("Tweez300", "ImageJ", "java.exe", "javaw.exe", "nis_", "NIS-"))
        self.rec(event="process_check", holders_found=holders,
                 note="tweezers GUI, Micro-Manager, and NIS (which may drive the piezo's analogue line)")
        self.gate("preload", (
            "The bench is handed to this session. Before anything connects: Micro-Manager closed, "
            "the tweezers program closed, NIS closed, the piezo controller off, the trapping "
            "laser off at its hand control, the LUN-F off at its own power, the Aura chassis on. "
            "The first check sets the green line to FULL with the Aura's master switch OFF, to "
            "prove the switch keeps the sample dark. Proceed?"))
        holders = s033._processes(("Tweez300", "ImageJ", "java.exe", "javaw.exe", "nis_", "NIS-"))
        if holders:
            raise Stop(f"still running after the person's answer: {holders}. If NIS, ask the person")

    def series(self, dark: dict) -> None:
        import numpy as np
        answer = self.gate("approve_light", (
            f"The checked command list ({len(COMMANDS)} commands, all passed the software-motion "
            f"check) is written to {self.approved['path']} (sha256 {self.approved['sha256'][:12]}). "
            f"The light goes on at the next step: Aura green {FIRST_INTENSITY} per-mille (10%), "
            f"continuously for {SERIES_FRAMES * PERIOD_S} s, one {EXPOSURE_MS:g} ms frame per "
            "second, then off. Nothing caps excitation in the safety file; this setting is the "
            "person's. Do you approve?"))
        self.approved["approved_by"] = (
            f"the person at the approve_light gate, before any light: {answer.get('said')!r}")
        self.gate("fresh_field", (
            "Is the area you found fresh -- NOT lit with the green light before (focused by eye "
            "or with the dia lamp only)? Say yes when the stage is there and focused."))

        core = self.core()
        h, w = core.getImageHeight(), core.getImageWidth()
        path = self.frames / "particles_paced.npy"
        stack = np.lib.format.open_memmap(path, mode="w+", dtype=np.uint16,
                                          shape=(SERIES_FRAMES, h, w))
        timing: list[dict] = []
        self.set("s4.4-intensity-first", LIGHT, LINE_I, FIRST_INTENSITY)
        self.set("s4.5-line-on", LIGHT, LINE, 1)
        self.set("s038-light-on", LIGHT, "State", 1)
        try:
            t0 = time.monotonic()
            for i in range(SERIES_FRAMES):
                scheduled = t0 + i * PERIOD_S          # from the integer, never a running sum
                wait = scheduled - time.monotonic()
                if wait > 0:
                    time.sleep(wait)
                started = time.monotonic()
                core.snapImage()
                image = core.getImage()
                stack[i] = image.reshape(h, w)
                timing.append({"i": i, "scheduled_s": i * PERIOD_S,
                               "started_s": round(started - t0, 6),
                               "late_s": round(max(0.0, started - scheduled), 6)})
                if i == 0:
                    lit = float(np.asarray(image, dtype=float).mean())
                    changed = lit - dark["dark_mean_adu"]
                    self.rec(event="step", step="038-first-frame", lit_mean_minus_dark_adu=changed,
                             image_changed=changed > 5 * dark["read_noise_adu"])
                    if not changed > 5 * dark["read_noise_adu"]:
                        raise Stop("frame 0 stayed dark with the Aura on. Not turned up: this may "
                                   "be the light path, not the light. The person decides")
        finally:
            self.set("shutdown-master-off", LIGHT, "State", 0)
            stack.flush()
            del stack
        timing_path = self.frames / "particles_paced_timing.json"
        timing_path.write_text(json.dumps(timing), encoding="utf-8")
        late = [t for t in timing if t["late_s"] > 0.05]
        entry = {"label": "particles_paced", "path": str(path), "sha256": _sha(path),
                 "timing_path": str(timing_path), "timing_sha256": _sha(timing_path),
                 "shape": [len(timing), h, w], "dtype": "uint16"}
        self.frame_files.append(entry)
        self.rec(event="acquire", channel=CAMERA, action="paced_snaps", frames=entry,
                 wanted=SERIES_FRAMES, received=len(timing), period_s=PERIOD_S,
                 frames_late_over_50ms=len(late),
                 worst_late_s=max((t["late_s"] for t in timing), default=0.0),
                 illumination="continuous: Aura State=1 for the whole series",
                 no_image_number=NO_IMAGE_NUMBER, verification="none",
                 verification_note="frames are data", **{"from": "card-038:s038-paced-series"})
        if len(timing) != SERIES_FRAMES:
            raise Stop(f"{len(timing)}/{SERIES_FRAMES} frames")

    def write(self, outcome: str) -> Path:
        record = {
            "artifact": "run_log", "schema_version": "0.1", "run_id": self.run_id,
            "plan_id": None, "revision": None,
            "no_plan_because": NO_PLAN_BECAUSE,
            "not_dispatched": NOT_DISPATCHED,
            "approved_commands": self.approved,
            "approval": {"id": None, "kind": None},
            "stop_criteria": [],
            **self.o.log_header(),
            "events": self.o.log,
            "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        record["events"].append({"t_mono": self.o.clock.offset(), "time_base": "software",
                                 "event": "run_end", "outcome": outcome,
                                 "frames": self.frame_files})
        data = (json.dumps(record, indent=2, default=str) + "\n").encode("utf-8")
        self.frames.mkdir(parents=True, exist_ok=True)
        beside = self.frames / "log.json"
        if beside.exists():
            raise Stop(f"{beside} exists; runs are never overwritten (P9)")
        beside.write_bytes(data)
        (self.runs_dir / "log.json").write_bytes(data)            # the same bytes (card 038)
        return beside


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--run-id", required=True)
    p.add_argument("--check-list-only", action="store_true")
    args = p.parse_args(argv)

    s = Session038(args.run_id)
    s.rec(event="not_dispatched", note=NOT_DISPATCHED)
    missed = mm.named_refusals_hold()
    if missed:
        raise Stop(f"named devices the allow-list would not refuse: {missed}")
    s.o.check_software_motion(COMMANDS)
    if args.check_list_only:
        print(f"command list: {len(COMMANDS)} commands passed the software-motion check")
        return 0
    s.write_commands()
    outcome = "incomplete"
    try:
        s.preload()
        s.load()
        dark = s.checks()
        s.series(dark)
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
    return 0 if outcome == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
