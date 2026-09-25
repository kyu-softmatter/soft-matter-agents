"""Card 036 phase B step 3: one confocal line, 561 nm, on the level set by hand.

    python src/session_036_laser.py prepare --run-id run-20260924-NNN
    python src/session_036_laser.py run --run-id run-20260924-NNN \
        --approved-by "<the person's words>" --sha256 <hash prepare printed>

A preparatory run on the route the person chose on 2026-09-24: the vendor
program (NIS) opens the fiber shutter and sets the level, then it is
force-killed so the blanking lines are free. What that costs is known and
the person was told: the fiber shutter stays open with nothing owning it
until NIS is restarted and closed normally, and the kill may stop the disk.

ORDER, and each step's reason:

  gate preload   the person, in NIS: 561 level low (0-5 V), fiber shutter open,
                 red filter multi, disk seen spinning, light path L100, lamp off
  gate kill      the person says yes to the force-kill, now
  kill           taskkill /F on nis_ar.exe, and confirm it is gone
  CLOSE ALL      the FIRST write after the kill: every line written closed,
                 because NIS may have left one open and nothing else can close it
  load           the derived configuration of run-20260924-008's shape: no DAQ
                 devices, no startup preset, so loading moves nothing
  read           light path, confocal unit, filters, nosepiece, light engines;
                 the run stops if the red filter is not multi, a light engine is
                 on, the lamp is on, or the path is not a recorded eyepiece-free
                 state
  gate light     the person is told the line goes on now, and says yes
  dark frame     every line closed
  ENABLE 561     through lunf.apply: the person's voltage pair, the approved
                 list naming this exact enable, the bench, the log, and the light
                 path read back at that moment, logged immediately before
  lit frame
  CLOSE ALL
  after frame    must be dark again
  texture        (lit - dark) off-centre spectral peak over median, on a central
                 crop: a stopped disk shows as a grid. Reported as a number with
                 the prior project's two regimes beside it, not as a verdict

On ANY failure or stop, every line is written closed first, then the log.
The line map and polarity come from the store entry
lunf_line_map_and_blanking_polarity (E3), cited in the log; the eyepiece-free
states from run-20260924-008's recorded mapping, cited by event.
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

AGENT = Path(_HERE).parent
REPO = AGENT.parent
FRAMES_ROOT = Path(r"D:\soft-matter-agents-frames")
SEAT = "microscope-20260924-3"
LINE = "561"
CAMERA = "Kinetix_red"
EXPOSURE_MS = 100.0
LINE_MAP_ENTRY = "lunf_line_map_and_blanking_polarity"
MAPPING_RUN = "run-20260924-008"
RED_FILTER_MULTI = 0          # CSUW1-Filter_Red state 0, labelled "multi" in run-20260924-008
PRIOR_REGIMES = {"no_signal": 129, "stopped_disk_grid": [25978, 210347]}

NO_PLAN_BECAUSE = (
    "The first software control of a confocal laser line on this instrument: one line, 561 nm, "
    "at a level the person set by hand, with a dark frame, a lit frame and a dark frame after, "
    "to show the line opens, closes and reaches the camera. No plan governs it; card 036 phase "
    "B step 3 orders exactly this, after the eyepiece mapping of run-20260924-008.")
NOT_DISPATCHED = (
    "This run did NOT come through the plan dispatcher, which cannot reach laser_combiner: the "
    "registry's driver field names no module and read_back false channels route to manual.py, "
    "both raised and unanswered. It is src/session_036_laser.py, committed before the run. The "
    "laser is written only through devices/lunf.py's apply and abort, whose gates are the "
    "chokepoint; the camera and every read go through micromanager.py's GuardedCore.")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)                              # type: ignore[union-attr]
    return module


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _nis_pids() -> list[int]:
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq nis_ar.exe", "/NH"],
                         capture_output=True, text=True).stdout
    pids = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].lower() == "nis_ar.exe":
            try:
                pids.append(int(parts[1]))
            except ValueError:
                pass
    return pids


def line_row() -> dict:
    """The channel row lunf.py reads, built from the store entry and cited."""
    entry = json.loads((REPO / "librarian_agent" / "kb" / "entries" /
                        f"{LINE_MAP_ENTRY}.json").read_text(encoding="utf-8"))
    claim = entry["claim"]
    lines = {"405": "Dev1/port0/line2", "488": "Dev1/port0/line4",
             "561": "Dev1/port0/line6", "640": "Dev1/port0/line8"}
    # The map is the entry's claim written out, not a second source: refuse
    # if the claim no longer says it.
    for nm, dl in lines.items():
        if f"{nm}" not in claim or dl.rsplit("/", 1)[1] not in claim:
            raise RuntimeError(f"{LINE_MAP_ENTRY} no longer states {nm} on {dl}; re-read it")
    if "active-high" not in claim.lower():
        raise RuntimeError(f"{LINE_MAP_ENTRY} no longer states active-high blanking")
    return {"id": "laser_combiner", "automatable": "partial", "read_back": False,
            "elements": [{"id": "line_select", "lines": lines, "open_level": 1,
                          "closed_level": 0, "from": f"kb:{LINE_MAP_ENTRY} ({entry['grade']})"}]}


def eyepiece_free() -> dict[int, str]:
    """States run-20260924-008 recorded as not reaching the eyepieces, cited by event."""
    log = json.loads((AGENT / "runs" / MAPPING_RUN / "log.json").read_text(encoding="utf-8"))
    free = {}
    for i, e in enumerate(log["events"]):
        if e.get("event") == "eyepiece_mapping" and e.get("eyepieces") == "no":
            free[int(e["state"])] = f"{MAPPING_RUN} events[{i}] ({e.get('label')})"
    return free


def commands(cfg: Path) -> list[dict]:
    c = lambda frm, dev, action, settings=None, note=None: {          # noqa: E731
        "from": f"card-036:{frm}", "device": dev, "action": action, "settings": settings,
        **({"note": note} if note else {})}
    return [
        c("b3-nis-present", None, "process_check", note="NIS must be running before the handoff"),
        c("b3-gate-preload", None, "gate"),
        c("b3-gate-kill", None, "gate"),
        c("b3-kill", "nis_ar.exe", "taskkill_force", note="then confirm no nis_ar.exe remains"),
        c("b3-lines-free", "laser_combiner", "lines_free_probe", note="reserve and release; no level"),
        c("b3-close-all", "laser_combiner", "enable", {"laser_combiner": {"enable": []}},
          "the first write after the kill"),
        c("b3-load", "Core", "load_configuration", {"path": str(cfg), "sha256": _sha(cfg)}),
        c("b3-read", None, "get_state_and_properties",
          note="LightPath, CSUW1-*, FilterTurret1, Nosepiece, Aura, LightEngine, DiaLamp"),
        c("b3-exposure", CAMERA, "set_exposure", {CAMERA: {"exposure_ms": EXPOSURE_MS}}),
        c("b3-gate-light", None, "gate"),
        c("b3-dark", CAMERA, "snap_image"),
        c("b3-enable", "laser_combiner", "enable", {"laser_combiner": {"enable": [LINE]}},
          "through lunf.apply, every gate"),
        c("b3-lit", CAMERA, "snap_image"),
        c("b3-close", "laser_combiner", "enable", {"laser_combiner": {"enable": []}}),
        c("b3-after", CAMERA, "snap_image"),
        c("b3-abort", "laser_combiner", "abort", note="on finish and on any failure"),
    ]


def prepare(run_id: str) -> int:
    ro = _load("_session_036_readonly", AGENT / "src" / "session_036_readonly.py")
    d = ro.derive(run_id)
    row = line_row()
    free = eyepiece_free()
    path = AGENT / "runs" / run_id / "commands.json"
    path.write_text(json.dumps(commands(d["path"]), indent=2) + "\n", encoding="utf-8",
                    newline="\n")
    print(f"derived {d['path']} ({len(d['removed'])} lines removed)")
    print(f"line map from kb:{LINE_MAP_ENTRY}: {row['elements'][0]['lines']}")
    print(f"eyepiece-free states: {free}")
    print(f"commands {path}\nsha256   {_sha(path)}")
    return 0


class Stop(RuntimeError):
    pass


def pinhole_ratio(diff, crop: int = 400) -> tuple[float, float]:
    """Off-centre spectral peak over median on a central crop, and its period in px."""
    import numpy as np
    h, w = diff.shape
    crop = min(crop, h, w)
    y0, x0 = (h - crop) // 2, (w - crop) // 2
    c = diff[y0:y0 + crop, x0:x0 + crop].astype(np.float64)
    c -= c.mean()
    p = np.abs(np.fft.fftshift(np.fft.fft2(c))) ** 2
    n = p.shape[0]
    yy, xx = np.mgrid[:n, :n]
    r = np.hypot(yy - n // 2, xx - n // 2)
    p[r < 4] = 0.0
    med = float(np.median(p[r >= 4]))
    py, px = np.unravel_index(p.argmax(), p.shape)
    dist = float(np.hypot(py - n // 2, px - n // 2))
    return (float(p.max()) / med if med > 0 else float("inf")), (n / dist if dist else float("nan"))


class Run:
    def __init__(self, run_id: str, approved_by: str, sha: str):
        self.run_id, self.approved_by, self.sha = run_id, approved_by, sha
        self.dir = AGENT / "runs" / run_id
        self.frames = FRAMES_ROOT / run_id
        self.gates = self.frames / "gates"
        self.partial = self.dir / "log.partial.jsonl"
        self.t0_wall = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        self.t0 = time.monotonic()
        self.events: list[dict] = []
        self.frame_files: list[dict] = []
        self.lunf = None
        self.mm = None

    def rec(self, **event) -> dict:
        event = {"t_mono": round(time.monotonic() - self.t0, 3), "time_base": "software", **event}
        self.events.append(event)
        with self.partial.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(event, default=str) + "\n")
        print(json.dumps(event, default=str)[:500], flush=True)
        return event

    def gate(self, name: str, question: str) -> dict:
        self.gates.mkdir(parents=True, exist_ok=True)
        path = self.gates / f"{name}.json"
        self.rec(event="gate_open", gate=name, question=question)
        print(f"GATE {name}: {question}", flush=True)
        while not path.exists():
            time.sleep(0.5)
        time.sleep(0.2)
        answer = json.loads(path.read_text(encoding="utf-8"))
        self.rec(event="gate_answered", gate=name, **{k: answer.get(k) for k in
                 ("answer", "said", "by", "relayed_by")})
        if str(answer.get("answer", "")).lower() != "yes":
            raise Stop(f"gate {name}: the person answered {answer.get('answer')!r}")
        return answer

    def snap(self, frm: str, label: str):
        import numpy as np
        image, meta = self.mm.snap()
        image = np.asarray(image)
        self.frames.mkdir(parents=True, exist_ok=True)
        path = self.frames / f"{label}.npy"
        np.save(path, image)
        stats = {"mean": float(image.mean()), "p99_9": float(np.percentile(image, 99.9)),
                 "max": float(image.max()), "min": float(image.min())}
        entry = {"label": label, "path": str(path), "sha256": _sha(path),
                 "shape": list(image.shape), "dtype": str(image.dtype)}
        self.frame_files.append(entry)
        self.rec(event="acquire", channel=CAMERA, action="snap", frame=entry, stats=stats,
                 verification="none", verification_note="a frame is data, not a setting",
                 **{"from": frm})
        return image, stats

    def laser(self, frm: str, enable: list[str]) -> dict:
        out = self.lunf.apply({"enable": enable})
        self.rec(event="apply", channel="laser_combiner", action="enable",
                 params={"enable": {"value": enable, "from": frm}}, written=out["applied"],
                 verification="none", verification_note=out["why_none"], **{"from": frm})
        return out

    def close_all(self, frm: str) -> None:
        """Every line written closed. Used after the kill, on finish, and on any failure."""
        if self.lunf is None:
            return
        out = self.lunf.abort()
        # A blind laser is assumed on after any command (card 036 at b285223).
        # What could show it blocked here is the confocal unit's shutter, which
        # reads back; it is read, and reported as the barrier only if closed.
        barrier, readings = None, {}
        if self.mm is not None:
            try:
                core = self.mm._core()
                readings = {"CSUW1-Shutter": core.getProperty("CSUW1-Shutter", "State"),
                            "LightPath": int(core.getState("LightPath"))}
                if str(readings["CSUW1-Shutter"]).lower() == "closed":
                    barrier = "the confocal unit's shutter reads Closed"
            except Exception as exc:                            # noqa: BLE001
                readings = {"error": repr(exc)}
        self.rec(event="abort", channel="laser_combiner", blanked=out.get("blanked"),
                 could_not_blank=out.get("could_not_blank"), not_reachable=out["not_reachable"],
                 beam=out.get("beam"), barrier=barrier, barrier_readings=readings,
                 verification="none", **{"from": frm})

    def main(self) -> str:
        cmd_path = self.dir / "commands.json"
        if _sha(cmd_path) != self.sha:
            raise Stop(f"commands.json hashes {_sha(cmd_path)}, not the approved {self.sha}")
        cmds = json.loads(cmd_path.read_text(encoding="utf-8"))
        by = {c["from"].split(":", 1)[1]: c for c in cmds}
        cfg = Path(by["b3-load"]["settings"]["path"])
        if _sha(cfg) != by["b3-load"]["settings"]["sha256"]:
            raise Stop("the derived configuration changed after it was approved")
        self.rec(event="not_dispatched", note=NOT_DISPATCHED)

        self.lunf = _load("_dev_lunf_036", AGENT / "src" / "devices" / "lunf.py")
        row, free = line_row(), eyepiece_free()
        self.rec(event="lunf_bound", row=row, eyepiece_free=free,
                 covering_limit=list(self.lunf.COVERING_LIMIT))
        if not free:
            raise Stop(f"{MAPPING_RUN} records no eyepiece-free light path state")

        pids = _nis_pids()
        self.rec(event="process_check", nis_pids=pids, **{"from": "card-036:b3-nis-present"})
        if not pids:
            raise Stop("NIS is not running: there is nothing to hand over from, and the fiber "
                       "shutter is closed. Start NIS, open the fiber shutter, set the level, "
                       "then run again")
        self.gate("preload", (
            "In NIS now: the 561 nm level set LOW (within 0-5 V), the fiber shutter open, the "
            "red filter set to multi, the disk seen spinning, the light path at L100, and the "
            "lamp off. Nobody at the eyepieces. Proceed?"))
        self.gate("kill", (
            "NIS will be force-killed now. The fiber shutter then stays open with nothing "
            "owning it until NIS is restarted and closed normally, and the disk may stop. Kill "
            "NIS?"))
        rc = subprocess.run(["taskkill", "/F"] + sum([["/PID", str(p)] for p in pids], []),
                            capture_output=True, text=True)
        self.rec(event="kill", pids=pids, returncode=rc.returncode,
                 output=(rc.stdout or rc.stderr).strip(), **{"from": "card-036:b3-kill"})
        for _ in range(40):
            if not _nis_pids():
                break
            time.sleep(0.25)
        else:
            raise Stop("nis_ar.exe is still running 10 s after the kill")

        self.lunf.use_transport(self.lunf.NiDaqTransport())
        self.lunf.bind_log(self.rec)
        for i in range(20):
            state = self.lunf.preflight(row)
            if state["ready"]:
                break
            time.sleep(0.5)
        self.rec(event="preflight", channel="laser_combiner", state=state,
                 **{"from": "card-036:b3-lines-free"})
        if not state["ready"]:
            raise Stop(f"the blanking lines are not free after the kill: {state.get('reason')}")
        self.laser("card-036:b3-close-all", [])

        self.mm = _load("_micromanager_036l", AGENT / "src" / "devices" / "micromanager.py")
        info = self.mm.load_configuration(str(cfg))
        self.rec(event="load", config=info, **{"from": "card-036:b3-load"})
        if not info["autoshutter"]["verified"]:
            raise Stop("AutoShutter did not read back 0 after the load")
        core = self.mm._core()

        def prop(dev, p):
            return core.getProperty(dev, p)
        read = {"LightPath": (int(core.getState("LightPath")), core.getStateLabel("LightPath")),
                "CSUW1-Shutter": prop("CSUW1-Shutter", "State"),
                "CSUW1-Bright": prop("CSUW1-Bright", "BrightFieldPort"),
                "CSUW1-Port": (int(core.getState("CSUW1-Port")), core.getStateLabel("CSUW1-Port")),
                "CSUW1-Filter_Red": (int(core.getState("CSUW1-Filter_Red")),
                                     core.getStateLabel("CSUW1-Filter_Red")),
                "FilterTurret1": (int(core.getState("FilterTurret1")),
                                  core.getStateLabel("FilterTurret1")),
                "Nosepiece": (int(core.getState("Nosepiece")), core.getStateLabel("Nosepiece")),
                "Aura.State": prop("Aura", "State"), "LightEngine.State": prop("LightEngine", "State"),
                "DiaLamp.State": prop("DiaLamp", "State")}
        self.rec(event="read", values=read, verification="readback", **{"from": "card-036:b3-read"})
        problems = []
        if read["CSUW1-Filter_Red"][0] != RED_FILTER_MULTI:
            problems.append(f"red filter reads {read['CSUW1-Filter_Red']}, not multi (state 0)")
        if str(read["Aura.State"]) != "0" or str(read["LightEngine.State"]) != "0":
            problems.append("a widefield light engine is on")
        if str(read["DiaLamp.State"]) != "0":
            problems.append("the lamp is on")
        if read["LightPath"][0] not in free:
            problems.append(f"light path reads {read['LightPath']}, not a recorded eyepiece-free "
                            f"state {sorted(free)}")
        if read["FilterTurret1"][0] == 0:
            problems.append("filter turret 1 is on the multiband cube, which blocks the confocal path")
        if problems:
            raise Stop("; ".join(problems))
        exp = self.mm.set_exposure(EXPOSURE_MS)
        self.rec(event="apply", channel=CAMERA, action="set_exposure", read=exp,
                 verification="readback" if exp["verified"] else "none",
                 **{"from": "card-036:b3-exposure"})

        self.lunf.bind_light_path(lambda: {"state": int(core.getState("LightPath")),
                                           "read_back": True}, free)
        self.lunf.bind_approval(cmds, self.approved_by)
        self.gate("light", (
            f"The {LINE} nm line goes on now, at the level set in NIS, for one "
            f"{EXPOSURE_MS:.0f} ms frame and then closes. Nobody at the eyepieces. Yes?"))
        answer = json.loads((self.gates / "light.json").read_text(encoding="utf-8"))
        self.lunf.bind_bench(SEAT, answer.get("bench") or answer.get("said"))

        dark, dark_s = self.snap("card-036:b3-dark", "dark")
        self.laser("card-036:b3-enable", [LINE])
        lit, lit_s = self.snap("card-036:b3-lit", "lit")
        self.laser("card-036:b3-close", [])
        after, after_s = self.snap("card-036:b3-after", "after")

        import numpy as np
        ratio, period = pinhole_ratio(lit.astype(np.float64) - dark.astype(np.float64))
        self.rec(event="texture", peak_over_median=round(ratio, 1), period_px=round(period, 2),
                 contrast_lit_over_dark=round(lit_s["p99_9"] / max(dark_s["p99_9"], 1.0), 3),
                 after_over_dark=round(after_s["p99_9"] / max(dark_s["p99_9"], 1.0), 3),
                 prior_regimes=PRIOR_REGIMES,
                 note=("reported, not judged: no threshold has been chosen here. The prior "
                       "project's two regimes are beside it for reading, ruled downgrade"))
        return "finished"

    def write(self, outcome: str) -> Path:
        try:
            self.close_all("card-036:b3-abort")
        except Exception as exc:                                # noqa: BLE001
            self.rec(event="abort_failed", error=repr(exc))
        self.rec(event="shutdown", reason=outcome,
                 note=("the fiber shutter is open with nothing owning it if NIS was killed: "
                       "restart NIS and close it normally to shut it"))
        policy = json.loads((AGENT / "envelope" / "safety.json").read_text(
            encoding="utf-8")).get("policy_version")
        log = {"artifact": "run_log", "schema_version": "0.1", "run_id": self.run_id,
               "plan_id": None, "revision": None, "no_plan_because": NO_PLAN_BECAUSE,
               "not_dispatched": NOT_DISPATCHED,
               "approved_commands": {"path": f"microscope_agent/runs/{self.run_id}/commands.json",
                                     "sha256": self.sha, "approved_by": self.approved_by},
               "approval": {"id": None, "kind": None}, "safety_policy_version": policy,
               "stop_criteria": [], "t0_wall": self.t0_wall, "t0_mono": self.t0,
               "backend": "micromanager+lunf",
               "time_base_note": ("software offsets order the log and nothing else. A value "
                                  "physics depends on comes from a trigger counter or a device "
                                  "timestamp (4.6.9)"),
               "events": self.events,
               "finished_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds")}
        path = self.dir / "log.json"
        path.write_text(json.dumps(log, indent=2, default=str) + "\n", encoding="utf-8",
                        newline="\n")
        return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=("prepare", "run"))
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--approved-by")
    ap.add_argument("--sha256")
    a = ap.parse_args(argv)
    if a.step == "prepare":
        return prepare(a.run_id)
    if not (a.approved_by and a.sha256):
        print("run needs --approved-by and --sha256")
        return 2
    r = Run(a.run_id, a.approved_by, a.sha256)
    outcome = "finished"
    try:
        outcome = r.main()
    except Stop as exc:
        outcome = f"stopped: {exc}"
    except Exception as exc:                                    # noqa: BLE001
        outcome = f"failed: {exc!r}"
    print(f"log {r.write(outcome)}  outcome: {outcome}")
    return 0 if outcome == "finished" else 1


if __name__ == "__main__":
    sys.exit(main())
