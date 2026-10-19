"""Card 036 phase B steps 1 and 2: read the confocal path, and map the eyepieces by hand.

    python src/session_036_readonly.py prepare --run-id run-20260924-NNN
    python src/session_036_readonly.py run --run-id run-20260924-NNN \
        --approved-by "<the person's words>" --sha256 <hash prepare printed>

A preparatory run. NOTHING IS WRITTEN TO ANY DEVICE except what loading a
configuration does, and the configuration is derived so that loading moves
nothing and touches no laser line:

  - from the prior project's dualcam_noDMD.cfg, read in place and hashed;
  - WITHOUT the NIDAQHub and LUNF-Blanking devices and every line naming
    them, including the LaserLine group, so Micro-Manager never opens the
    DAQ port that carries the confocal laser's blanking lines;
  - WITHOUT the System/Startup preset, which in that file moves the Lapp
    branch and the CSU-W1 port on load (2.1 rule 10: loading saved state is
    a command).

The derived file is written into this run's directory and its sha256 goes in
the approved list, so what the person approves is the exact file loaded.

STEP 1 reads every property of the light path, the CSU-W1 devices, the
turrets, the nosepiece and both light engines, and searches the CSU-W1
devices for anything that reports disk speed.

STEP 2 is the eyepiece mapping. The person sets the light path BY HAND at
the stand, with the lamp only and no laser -- the vendor program was closed
normally, which closes the fiber shutter -- and says whether the image is in
the eyepieces. For each answer the script reads the light path's state
integer AT THAT MOMENT and records the pair. Pinned by integer; the label is
recorded beside it and is not what the mapping keys on (2.1 rule 11). The
answers arrive as gate files written from the chat with the person's words.

Every event is appended to log.partial.jsonl as it happens.
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
SOURCE_CFG = Path(r"C:\agentic_microscope\config\micromanager\dualcam_noDMD.cfg")
FRAMES_ROOT = Path(r"D:\soft-matter-agents-frames")
LASER_DEVICES = ("NIDAQHub", "LUNF-Blanking")
READ_DEVICES = ("LightPath", "CSUW1-Hub", "CSUW1-Shutter", "CSUW1-Bright", "CSUW1-Port",
                "CSUW1-Dichroic", "CSUW1-Filter_Red", "CSUW1-Filter_Blue", "FilterTurret1",
                "Turret1Shutter", "FilterTurret2", "Turret2Shutter", "Nosepiece",
                "IntermediateMagnification", "DiaLamp", "Aura", "LightEngine")
STATE_DEVICES = ("LightPath", "CSUW1-Shutter", "CSUW1-Bright", "CSUW1-Port", "CSUW1-Dichroic",
                 "CSUW1-Filter_Red", "CSUW1-Filter_Blue", "FilterTurret1", "FilterTurret2",
                 "Nosepiece", "IntermediateMagnification")
DISK_WORDS = ("speed", "rpm", "motor", "rotation", "disk")

NO_PLAN_BECAUSE = (
    "A read-only first look at the confocal path, and the eyepiece mapping 2.1 rule 11 requires "
    "before any laser line is enabled. It writes nothing to any device; loading moves nothing "
    "because the startup preset is removed from the derived configuration, and no laser can "
    "emit because the vendor program was closed normally, which closes the fiber shutter. No "
    "plan governs it, and card 036 phase B orders exactly these two steps first.")
NOT_DISPATCHED = (
    "This run did NOT come through the plan dispatcher: it is src/session_036_readonly.py, "
    "committed before the run. It loads one derived configuration, reads properties, and "
    "waits for the person's answers; it sends no set call of any kind.")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)                              # type: ignore[union-attr]
    return module


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_dir(run_id: str) -> Path:
    return AGENT / "runs" / run_id


def derive(run_id: str) -> dict:
    """Write the derived configuration and return what was removed."""
    text = SOURCE_CFG.read_text(encoding="utf-8", errors="strict")
    kept, removed = [], []
    for line in text.splitlines():
        fields = [f.strip() for f in line.split(",")]
        names_laser = any(dev in fields for dev in LASER_DEVICES)
        startup = line.startswith("ConfigGroup,System,Startup")
        laser_group = line.startswith("ConfigGroup,LaserLine")
        if names_laser or startup or laser_group:
            removed.append(line)
        else:
            kept.append(line)
    header = [f"# DERIVED for {run_id} by src/session_036_readonly.py from",
              f"#   {SOURCE_CFG} (sha256 {_sha(SOURCE_CFG)})",
              "# Removed: every line naming NIDAQHub or LUNF-Blanking, the LaserLine group,",
              "# and the System/Startup preset. Nothing else changed."]
    out = run_dir(run_id) / "dualcam_noDMD_nolaser_nostartup.cfg"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(header + kept) + "\n", encoding="utf-8", newline="\n")
    return {"path": out, "removed": removed, "source_sha256": _sha(SOURCE_CFG)}


def commands(cfg: Path) -> list[dict]:
    cmds = [{"from": "card-036:b1-process-check", "device": None, "action": "process_check",
             "settings": None, "note": "nis_ar.exe must not be running"},
            {"from": "card-036:b1-load", "device": "Core", "action": "load_configuration",
             "settings": {"path": str(cfg), "sha256": _sha(cfg)},
             "note": "then AutoShutter 0 and read back, as load_configuration always does"}]
    for dev in READ_DEVICES:
        cmds.append({"from": "card-036:b1-read", "device": dev, "action": "get_all_properties",
                     "settings": None})
    for dev in STATE_DEVICES:
        cmds.append({"from": "card-036:b1-state", "device": dev, "action": "get_state_and_labels",
                     "settings": None})
    cmds.append({"from": "card-036:b2-eyepiece-map", "device": "LightPath",
                 "action": "get_state_per_answer", "settings": None,
                 "note": "the person moves the light path by hand; this only reads it"})
    return cmds


def prepare(run_id: str) -> int:
    d = derive(run_id)
    path = run_dir(run_id) / "commands.json"
    path.write_text(json.dumps(commands(d["path"]), indent=2) + "\n", encoding="utf-8",
                    newline="\n")
    print(f"derived {d['path']} ({len(d['removed'])} lines removed):")
    for line in d["removed"]:
        print(f"   - {line}")
    print(f"commands {path}\nsha256   {_sha(path)}")
    return 0


class Stop(RuntimeError):
    pass


class Run:
    def __init__(self, run_id: str, approved_by: str, sha: str):
        self.run_id, self.approved_by, self.sha = run_id, approved_by, sha
        self.dir = run_dir(run_id)
        self.gates = FRAMES_ROOT / run_id / "gates"
        self.partial = self.dir / "log.partial.jsonl"
        self.t0_wall = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        self.t0 = time.monotonic()
        self.events: list[dict] = []

    def rec(self, **event) -> dict:
        event = {"t_mono": round(time.monotonic() - self.t0, 3), "time_base": "software", **event}
        self.events.append(event)
        with self.partial.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(event, default=str) + "\n")
        print(json.dumps(event, default=str)[:400], flush=True)
        return event

    def wait(self, name: str, question: str) -> dict:
        self.gates.mkdir(parents=True, exist_ok=True)
        path = self.gates / f"{name}.json"
        self.rec(event="gate_open", gate=name, question=question)
        print(f"GATE {name}: {question}", flush=True)
        while not path.exists():
            time.sleep(0.5)
        time.sleep(0.2)
        answer = json.loads(path.read_text(encoding="utf-8"))
        self.rec(event="gate_answered", gate=name, **{k: answer.get(k) for k in
                 ("answer", "eyepieces", "said", "by", "relayed_by")})
        return answer

    def main(self) -> str:
        cmd_path = self.dir / "commands.json"
        if _sha(cmd_path) != self.sha:
            raise Stop(f"commands.json hashes {_sha(cmd_path)}, not the approved {self.sha}")
        cmds = json.loads(cmd_path.read_text(encoding="utf-8"))
        cfg = Path(cmds[1]["settings"]["path"])
        if _sha(cfg) != cmds[1]["settings"]["sha256"]:
            raise Stop("the derived configuration changed after it was approved")
        self.rec(event="not_dispatched", note=NOT_DISPATCHED)

        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq nis_ar.exe", "/NH"],
                             capture_output=True, text=True).stdout
        running = "nis_ar.exe" in out.lower()
        self.rec(event="process_check", nis_running=running, **{"from": cmds[0]["from"]})
        if running:
            raise Stop("NIS is running; it holds the stand, and this run needs it closed normally")

        mm = _load("_micromanager_036", AGENT / "src" / "devices" / "micromanager.py")
        info = mm.load_configuration(str(cfg))
        self.rec(event="load", config=info, **{"from": cmds[1]["from"]})
        if not info["autoshutter"]["verified"]:
            raise Stop("AutoShutter did not read back 0 after the load")
        core = mm._core()
        loaded = set(core.getLoadedDevices())

        for c in cmds:
            dev = c["device"]
            if c["action"] == "get_all_properties":
                if dev not in loaded:
                    self.rec(event="read", device=dev, loaded=False, **{"from": c["from"]})
                    continue
                props = {}
                for p in core.getDevicePropertyNames(dev):
                    try:
                        props[p] = core.getProperty(dev, p)
                    except Exception as exc:                    # noqa: BLE001
                        props[p] = f"<unreadable: {exc!r}>"
                disk = [p for p in props if any(w in p.lower() for w in DISK_WORDS)]
                self.rec(event="read", device=dev, loaded=True, properties=props,
                         disk_related_properties=disk, verification="readback",
                         **{"from": c["from"]})
            elif c["action"] == "get_state_and_labels":
                if dev not in loaded:
                    continue
                try:
                    state, label = core.getState(dev), core.getStateLabel(dev)
                    labels = list(core.getStateLabels(dev))
                except Exception as exc:                        # noqa: BLE001
                    self.rec(event="state", device=dev, error=repr(exc), **{"from": c["from"]})
                    continue
                self.rec(event="state", device=dev, state=int(state), label=label,
                         labels_by_state=labels, verification="readback", **{"from": c["from"]})

        mapping, k = [], 0
        while True:
            k += 1
            ans = self.wait(f"path_{k}", (
                "Set the light path by hand at the stand, lamp only. Then answer: answer "
                "'set' with eyepieces 'yes' or 'no', or answer 'done' to finish."))
            if str(ans.get("answer")).lower() == "done":
                break
            if str(ans.get("answer")).lower() != "set" or ans.get("eyepieces") not in ("yes", "no"):
                raise Stop(f"gate path_{k}: unreadable answer {ans!r}")
            state, label = int(core.getState("LightPath")), core.getStateLabel("LightPath")
            row = {"state": state, "label": label, "eyepieces": ans["eyepieces"],
                   "said": ans.get("said")}
            mapping.append(row)
            self.rec(event="eyepiece_mapping", **row, verification="readback",
                     **{"from": "card-036:b2-eyepiece-map"})
        self.rec(event="eyepiece_mapping_done", rows=mapping)
        return "finished"

    def write(self, outcome: str) -> Path:
        policy = None
        try:
            policy = json.loads((AGENT / "envelope" / "safety.json").read_text(
                encoding="utf-8")).get("policy_version")
        except (OSError, ValueError) as exc:
            self.rec(event="safety_policy_unreadable", error=repr(exc))
        self.rec(event="shutdown", reason=outcome)
        log = {"artifact": "run_log", "schema_version": "0.1", "run_id": self.run_id,
               "plan_id": None, "revision": None, "no_plan_because": NO_PLAN_BECAUSE,
               "not_dispatched": NOT_DISPATCHED,
               "approved_commands": {"path": f"microscope_agent/runs/{self.run_id}/commands.json",
                                     "sha256": self.sha, "approved_by": self.approved_by},
               "approval": {"id": None, "kind": None}, "safety_policy_version": policy,
               "stop_criteria": [], "t0_wall": self.t0_wall, "t0_mono": self.t0,
               "backend": "micromanager",
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
