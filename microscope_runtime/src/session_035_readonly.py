"""Card 035 phase B step 1: read the piezo controller, write nothing.

    python src/session_035_readonly.py --approved-by "<the person's words>" --sha256 <hash shown>

A preparatory run. It opens COM4 through the vendor library with the link in
read-only mode, sends only what runs/run-20260924-004/commands.json lists --
checked by sha256 against the hash the person approved -- and writes the run
log beside that file. Nothing moves and the security level is not touched:
the driver refuses a position write or a level change on a read-only link,
and this script refuses any command that is not a `.get` before it is sent.

Every event is appended to log.partial.jsonl as it happens, so a fault inside
the vendor library still leaves a record of how far the run got.
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

AGENT = Path(_HERE).parent
RUN_ID = "run-20260924-004"
RUN_DIR = AGENT / "runs" / RUN_ID
COMMANDS = RUN_DIR / "commands.json"
ADDRESS = "COM4"
CHANNELS = (1, 2, 3)
FIXED = ["stage.position.measured.get", "stage.position.calibrated-range.minimum.get",
         "stage.position.calibrated-range.maximum.get"]
PATTERN_WORDS = ("mode", "analogue", "analog", "digital", "identity", "version", "serial")
FORBIDDEN = (".set", "lock", "unlock", "start", "stop", "waveform", "function")

NO_PLAN_BECAUSE = (
    "A read-only first contact with the piezo controller: it opens the port, reads the command "
    "set, positions, calibrated range, security level and the analogue/digital path setting, and "
    "closes. It moves nothing, so no plan governs a motion, and card 035 phase B step 1 orders "
    "exactly this before any planned operation. The manager relayed the person's choice of "
    "check-first on 2026-09-24.")
NOT_DISPATCHED = (
    "This run did NOT come through the plan dispatcher and dispatches nothing to piezo_stage: it "
    "is src/session_035_readonly.py, committed before the run, sending only .get commands from "
    "the approved list through a read-only link that refuses position writes and security changes.")


def load_backend():
    path = Path(_HERE) / "devices" / "python_serial.py"
    spec = importlib.util.spec_from_file_location("_dev_python_serial", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)                                 # type: ignore[union-attr]
    return mod


class Log:
    def __init__(self):
        self.t0_mono = time.monotonic()
        self.t0_wall = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        self.events: list[dict] = []
        self.partial = RUN_DIR / "log.partial.jsonl"

    def rec(self, **event):
        event = {"t_mono": round(time.monotonic() - self.t0_mono, 3), "time_base": "software",
                 **event}
        self.events.append(event)
        with self.partial.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        print(json.dumps(event, ensure_ascii=False)[:300])


def allowed(name: str) -> bool:
    n = name.lower()
    return n.endswith(".get") and not any(bad in n for bad in FORBIDDEN)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--approved-by", required=True, help="the person's approval, in their words")
    ap.add_argument("--sha256", required=True, help="the hash of commands.json the person approved")
    ap.add_argument("--rehearsal", action="store_true",
                    help="the same sequence on the vendor simulator; writes nothing into runs/")
    args = ap.parse_args(argv)
    global ADDRESS, RUN_DIR
    if args.rehearsal:
        import tempfile
        ADDRESS = "sim:/NPC6330"
        RUN_DIR = Path(tempfile.mkdtemp(prefix="piezo_rehearsal_"))

    digest = hashlib.sha256(COMMANDS.read_bytes()).hexdigest()
    if digest != args.sha256:
        print(f"commands.json is {digest}, not the approved {args.sha256}; nothing is opened")
        return 2
    if not args.rehearsal and (RUN_DIR / "log.json").exists():
        print("a log for this run already exists; nothing is opened")
        return 3

    log = Log()
    log.rec(event="not_dispatched", note=NOT_DISPATCHED)
    log.rec(event="approved_commands", path=str(COMMANDS.relative_to(AGENT.parent)).replace("\\", "/"),
            sha256=digest, approved_by=args.approved_by)
    log.rec(event="bench", note="the person handed the bench to microscope-20260924-2 in that "
            "seat's own window on 2026-09-24, and said NanoBench is closed and NIS is off")
    log.rec(event="port_observation", note="no handle listing was taken, so whether the vendor "
            "simulator opens a port remains unobserved; this run opens COM4 deliberately")

    p = load_backend()
    outcome, link = "completed", None
    try:
        link = p.open_link("dll", address=ADDRESS, bench="the person, in this seat's window, "
                           "2026-09-24", read_only=True)
        ct = link._ct
        lib = link._lib
        major, minor, build = ct.c_int(0), ct.c_int(0), ct.c_int(0)
        lib.GetDllVersion.argtypes = [ct.c_void_p, ct.c_void_p, ct.c_void_p]
        lib.GetDllVersion(ct.byref(major), ct.byref(minor), ct.byref(build))
        log.rec(event="library_version", version=f"{major.value}.{minor.value}.{build.value}",
                path=str(p.DllLink.LIBRARY))
        log.rec(event="opened", address=ADDRESS, read_only=link.read_only)

        lib.FindCommands.restype = ct.c_int
        lib.FindCommands.argtypes = [ct.c_void_p, ct.c_char_p]
        lib.GetCommand.restype = ct.c_int
        lib.GetCommand.argtypes = [ct.c_void_p, ct.c_int, ct.c_char_p, ct.c_int]
        lib.GetCommandParameters.restype = ct.c_int
        lib.GetCommandParameters.argtypes = [ct.c_void_p, ct.c_char_p]
        n = lib.FindCommands(link._h, b"")
        names = []
        for i in range(max(n, 0)):
            size = lib.GetCommand(link._h, i, ct.create_string_buffer(2), 1) + 1
            buf = ct.create_string_buffer(size)
            lib.GetCommand(link._h, i, buf, size)
            names.append(buf.value.decode("utf-8", errors="replace"))
        log.rec(event="command_list", count=len(names), commands=names)

        def read(cmd: str, channel: int | None = None):
            if not allowed(cmd):
                log.rec(event="refused", command=cmd, reason="not a .get, or a forbidden word")
                return
            text = cmd if channel is None else f"{cmd} {channel}"
            try:
                log.rec(event="read", command=text, result=link.do(text))
            except p.PiezoRefused as exc:
                log.rec(event="read_failed", command=text, reason=str(exc))

        read("controller.security.user.get")
        for cmd in FIXED:
            for ch in CHANNELS:
                read(cmd, ch)
        matched = [c for c in names if allowed(c) and c not in FIXED
                   and c != "controller.security.user.get"
                   and any(w in c.lower() for w in PATTERN_WORDS)]
        for cmd in matched:
            k = lib.GetCommandParameters(link._h, cmd.encode("utf-8"))
            if k == 0:
                read(cmd)
            elif k == 1:
                for ch in CHANNELS:
                    read(cmd, ch)
            else:
                log.rec(event="skipped", command=cmd, parameters=k,
                        reason="takes more than one parameter; not in the approved rule")
        read("controller.security.user.get")
    except Exception as exc:                                     # recorded, then closed
        outcome = f"stopped: {type(exc).__name__}: {exc}"
        log.rec(event="stopped", reason=outcome)
    finally:
        if link is not None:
            p.close_link()
            log.rec(event="closed", address=ADDRESS)
        log.rec(event="run_end", outcome=outcome)

    doc = {
        "artifact": "run_log", "schema_version": "0.1", "run_id": RUN_ID,
        "plan_id": None, "revision": None,
        "no_plan_because": NO_PLAN_BECAUSE, "not_dispatched": NOT_DISPATCHED,
        "approved_commands": {"path": str(COMMANDS.relative_to(AGENT.parent)).replace("\\", "/"),
                              "sha256": digest, "approved_by": args.approved_by},
        "approval": {"id": None, "kind": None}, "stop_criteria": [],
        "t0_wall": log.t0_wall, "t0_mono": round(log.t0_mono, 3),
        "backend": "python_serial",
        "time_base_note": ("software offsets order the log and nothing else. A value physics "
                           "depends on comes from a trigger counter or a device timestamp (4.6.9)"),
        "events": log.events,
        "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (RUN_DIR / "log.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                                      encoding="utf-8")
    log.partial.unlink(missing_ok=True)
    print(f"wrote {RUN_DIR / 'log.json'}: {outcome}")
    return 0 if outcome == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
