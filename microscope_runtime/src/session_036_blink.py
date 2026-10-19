"""Card 036 phase B step 3, reduced: can software switch the 561 nm line at all?

    python src/session_036_blink.py prepare --run-id run-20260924-NNN
    python src/session_036_blink.py run --run-id run-20260924-NNN \
        --approved-by "<the person's words>" --sha256 <hash prepare printed>

The person's request after run-20260924-009 hung loading the dual-camera
configuration: check only whether the combiner can be controlled, the way
the prior project did it, and leave the cameras and the confocal unit out.

So the LASER goes exactly the prior project's way -- NI-DAQmx digital lines
written from Python, no Micro-Manager -- through devices/lunf.py. Micro-Manager
is loaded for ONE thing, which the prior project never did and 2.1 rule 11
requires: the light path read back at the moment of each enable. The
configuration is therefore the stand alone: the prior dual-camera file with
every line kept only if every device it names is a Ti2 device, the Core
camera and shutter roles dropped, and every config group, the startup
preset and the pixel-size table dropped. No camera, no confocal unit, no
light engine, no DAQ device, no COM port.

Proof that light came out is the person's: a card on the stage, watched from
above the objective, never through the eyepieces. The line BLINKS -- on 1 s,
off 1 s, five times -- which a person tells from room light far more easily
than a steady spot. No frame is taken, so nothing here shows the light
reached the camera or the disk was spinning; the log says so.

Every gate lunf.apply holds applies to every one of the five enables: the
person's voltage pair, the approved list naming the enable, the bench, the
log, and the light path read back and logged at that moment. On any stop,
every line is written closed before the log.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]

import argparse                                                  # noqa: E402
import importlib.util                                            # noqa: E402
import json                                                      # noqa: E402
import subprocess                                                # noqa: E402
import time                                                      # noqa: E402
from pathlib import Path                                         # noqa: E402

AGENT = Path(_HERE).parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)                              # type: ignore[union-attr]
    return module


L = _load("_session_036_laser", AGENT / "src" / "session_036_laser.py")
RO = _load("_session_036_readonly", AGENT / "src" / "session_036_readonly.py")

TI2 = frozenset({"Ti2-E__0", "ZDrive", "XYStage", "Nosepiece", "CondenserTurret",
                 "FilterTurret1", "Turret1Shutter", "FilterTurret2", "Turret2Shutter",
                 "LightPath", "PFS", "PFSOffset", "IntermediateMagnification",
                 "LappMainBranch1", "DiaLamp"})
BLINKS = 5
HALF_PERIOD_S = 1.0

NO_PLAN = (
    "A check that software can switch one confocal laser line, the person's request after "
    "run-20260924-009 hung loading the dual-camera configuration: 561 nm blinked five times at "
    "the level the person set by hand, watched by the person on a card on the stage. No plan "
    "governs it and no frame is taken; card 036 phase B step 3's frame is replaced, by the "
    "person's choice, with the person's observation.")
NOT_DISPATCHED = (
    "This run did NOT come through the plan dispatcher, which cannot reach laser_combiner. It "
    "is src/session_036_blink.py, committed before the run. The laser is written only through "
    "devices/lunf.py (NI-DAQmx, no Micro-Manager); Micro-Manager holds the stand alone, loaded "
    "only to read the light path through micromanager.py's GuardedCore.")


def derive_ti2(run_id: str) -> dict:
    text = RO.SOURCE_CFG.read_text(encoding="utf-8")
    kept, removed = [], []
    for line in text.splitlines():
        f = [x.strip() for x in line.split(",")]
        kind = f[0] if f else ""
        keep = True
        if not line.strip() or line.startswith("#"):
            keep = True
        elif kind == "Device":
            keep = f[1] in TI2
        elif kind in ("Property", "Label"):
            keep = f[1] in TI2 or (f[1] == "Core" and f[2] in ("Initialize", "AutoShutter"))
        elif kind == "Parent":
            keep = f[1] in TI2 and f[2] in TI2
        else:                               # ConfigGroup, ConfigPixelSize, PixelSize_um, ...
            keep = False
        (kept if keep else removed).append(line)
    header = [f"# DERIVED for {run_id} by src/session_036_blink.py from",
              f"#   {RO.SOURCE_CFG} (sha256 {L._sha(RO.SOURCE_CFG)})",
              "# Kept: comments, and lines whose every device is a Ti2 device, plus Core",
              "# Initialize and AutoShutter. Dropped: everything else, including every config",
              "# group, the startup preset and the pixel-size table."]
    out = AGENT / "runs" / run_id / "ti2_only.cfg"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(header + kept) + "\n", encoding="utf-8", newline="\n")
    return {"path": out, "removed": removed}


def commands(cfg: Path) -> list[dict]:
    c = lambda frm, dev, action, settings=None, note=None: {          # noqa: E731
        "from": f"card-036:{frm}", "device": dev, "action": action, "settings": settings,
        **({"note": note} if note else {})}
    return [
        c("b4-nis-present", None, "process_check", note="NIS must be running before the handoff"),
        c("b4-gate-preload", None, "gate"),
        c("b4-gate-kill", None, "gate"),
        c("b4-kill", "nis_ar.exe", "taskkill_force", note="then confirm no nis_ar.exe remains"),
        c("b4-lines-free", "laser_combiner", "lines_free_probe", note="reserve and release; no level"),
        c("b4-close-all", "laser_combiner", "enable", {"laser_combiner": {"enable": []}},
          "the first write after the kill"),
        c("b4-load", "Core", "load_configuration", {"path": str(cfg), "sha256": L._sha(cfg)},
          "the stand alone; no camera, confocal unit, light engine or DAQ device"),
        c("b4-read", None, "get_state", note="LightPath and DiaLamp"),
        c("b4-gate-light", None, "gate"),
        c("b4-blink-on", "laser_combiner", "enable", {"laser_combiner": {"enable": ["561"]}},
          f"{BLINKS} times, each through lunf.apply with every gate and a light-path read"),
        c("b4-blink-off", "laser_combiner", "enable", {"laser_combiner": {"enable": []}},
          f"after each on, {HALF_PERIOD_S:g} s later"),
        c("b4-gate-seen", None, "gate", note="the person says what the card showed"),
        c("b4-abort", "laser_combiner", "abort", note="on finish and on any failure"),
    ]


def prepare(run_id: str) -> int:
    d = derive_ti2(run_id)
    path = AGENT / "runs" / run_id / "commands.json"
    path.write_text(json.dumps(commands(d["path"]), indent=2) + "\n", encoding="utf-8",
                    newline="\n")
    kept = [l for l in d["path"].read_text(encoding="utf-8").splitlines() if l.startswith("Device")]
    print(f"derived {d['path']}: {len(d['removed'])} lines removed; devices kept:")
    for line in kept:
        print(f"   {line}")
    print(f"eyepiece-free states: {L.eyepiece_free()}")
    print(f"commands {path}\nsha256   {L._sha(path)}")
    return 0


class Blink(L.Run):
    NO_PLAN = NO_PLAN
    NOT_DISPATCHED_NOTE = NOT_DISPATCHED
    BACKEND_NAME = "lunf+micromanager(stand only)"

    def main(self) -> str:
        cmd_path = self.dir / "commands.json"
        if L._sha(cmd_path) != self.sha:
            raise L.Stop(f"commands.json hashes {L._sha(cmd_path)}, not the approved {self.sha}")
        cmds = json.loads(cmd_path.read_text(encoding="utf-8"))
        by = {c["from"].split(":", 1)[1]: c for c in cmds}
        cfg = Path(by["b4-load"]["settings"]["path"])
        if L._sha(cfg) != by["b4-load"]["settings"]["sha256"]:
            raise L.Stop("the derived configuration changed after it was approved")
        self.rec(event="not_dispatched", note=NOT_DISPATCHED)

        self.lunf = _load("_dev_lunf_036b", AGENT / "src" / "devices" / "lunf.py")
        row, free = L.line_row(), L.eyepiece_free()
        self.rec(event="lunf_bound", row=row, eyepiece_free=free,
                 covering_limit=list(self.lunf.COVERING_LIMIT))
        if not free:
            raise L.Stop(f"{L.MAPPING_RUN} records no eyepiece-free light path state")

        pids = L._nis_pids()
        self.rec(event="process_check", nis_pids=pids, **{"from": "card-036:b4-nis-present"})
        if not pids:
            raise L.Stop("NIS is not running, so the fiber shutter is closed and nothing can "
                         "emit. Start NIS, set the level, open the fiber shutter, then run again")
        self.gate("preload", (
            "In NIS now: 561 nm level set low (1 V), fiber shutter open, light path at L100, lamp "
            "off, a card on the stage, nobody at the eyepieces. Proceed?"))
        self.gate("kill", (
            "NIS will be force-killed now; the fiber shutter then stays open until NIS is "
            "restarted and closed normally. Kill NIS?"))
        rc = subprocess.run(["taskkill", "/F"] + sum([["/PID", str(p)] for p in pids], []),
                            capture_output=True, text=True)
        self.rec(event="kill", pids=pids, returncode=rc.returncode,
                 output=(rc.stdout or rc.stderr).strip(), **{"from": "card-036:b4-kill"})
        for _ in range(40):
            if not L._nis_pids():
                break
            time.sleep(0.25)
        else:
            raise L.Stop("nis_ar.exe is still running 10 s after the kill")

        self.lunf.use_transport(self.lunf.NiDaqTransport())
        self.lunf.bind_log(self.rec)
        for _ in range(20):
            state = self.lunf.preflight(row)
            if state["ready"]:
                break
            time.sleep(0.5)
        self.rec(event="preflight", channel="laser_combiner", state=state,
                 **{"from": "card-036:b4-lines-free"})
        if not state["ready"]:
            raise L.Stop(f"the blanking lines are not free after the kill: {state.get('reason')}")
        self.laser("card-036:b4-close-all", [])

        self.mm = _load("_micromanager_036b", AGENT / "src" / "devices" / "micromanager.py")
        self.rec(event="load_start", config=str(cfg), **{"from": "card-036:b4-load"})
        info = self.mm.load_configuration(str(cfg))
        self.rec(event="load", config=info, **{"from": "card-036:b4-load"})
        core = self.mm._core()
        path_state = int(core.getState("LightPath"))
        read = {"LightPath": (path_state, core.getStateLabel("LightPath")),
                "DiaLamp.State": core.getProperty("DiaLamp", "State")}
        self.rec(event="read", values=read, verification="readback",
                 **{"from": "card-036:b4-read"})
        if path_state not in free:
            raise L.Stop(f"light path reads {read['LightPath']}, not a recorded eyepiece-free "
                         f"state {sorted(free)}")

        self.lunf.bind_light_path(lambda: {"state": int(core.getState("LightPath")),
                                           "read_back": True}, free)
        self.lunf.bind_approval(cmds, self.approved_by)
        answer = self.gate("light", (
            f"561 nm blinks now, {BLINKS} times, {HALF_PERIOD_S:g} s on and {HALF_PERIOD_S:g} s "
            "off. Watch the card on the stage from above, never the eyepieces. Yes?"))
        self.lunf.bind_bench(L.SEAT, answer.get("said"))

        t0 = time.monotonic()
        for k in range(BLINKS):
            # Deadlines from an integer count, never a running sum.
            self._until(t0 + (2 * k) * HALF_PERIOD_S)
            self.laser("card-036:b4-blink-on", ["561"])
            self._until(t0 + (2 * k + 1) * HALF_PERIOD_S)
            self.laser("card-036:b4-blink-off", [])
        self.rec(event="blinks_done", blinks=BLINKS, half_period_s=HALF_PERIOD_S)

        seen = self.observe("seen", (
            "What did the card show? Answer 'blinked' if the spot went on and off, 'steady' if "
            "it stayed on, 'nothing' if no light appeared -- and anything else you saw."))
        return f"finished; the person saw: {seen.get('answer')}"

    @staticmethod
    def _until(deadline: float) -> None:
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                return
            time.sleep(min(left, 0.05))

    def observe(self, name: str, question: str) -> dict:
        """A gate whose answer is recorded and never stops the run: it comes after the light."""
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
        return answer


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
    r = Blink(a.run_id, a.approved_by, a.sha256)
    outcome = "finished"
    try:
        outcome = r.main()
    except L.Stop as exc:
        outcome = f"stopped: {exc}"
    except Exception as exc:                                    # noqa: BLE001
        outcome = f"failed: {exc!r}"
    print(f"log {r.write(outcome)}  outcome: {outcome}")
    return 0 if outcome.startswith("finished") else 1


if __name__ == "__main__":
    sys.exit(main())
