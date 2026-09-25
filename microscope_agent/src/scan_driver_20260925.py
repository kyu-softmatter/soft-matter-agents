"""Drive the strength scan's holds with the person's standing yes, recording 3 min at each strength.

    python src/scan_driver_20260925.py <hold_dir> <rec_dir> <first_strength>

The person, 2026-09-25 in this seat's window: "take videos for each powers for
3 min", "now you don't need to show me the real time view", and, asked whether
to carry on alone through 0.4 to 1.0 -- record, check the bead is in view,
answer yes -- "Carry on by yourself". This script is that standing answer and
nothing more: it writes "yes" to a hold only after the recording at the
current strength is complete and its last frames show a bead, and it stops,
answering nothing, when either fails. The hold then waits for the person.
It sends no command: operator.run, running separately, derives every one.
"""

from __future__ import annotations

import os
import sys

# The four lines every script in src/ carries: src/ holds operator.py, which
# shadows the standard module for anything imported after it (operator.py's header).
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]

import json                                                      # noqa: E402
import subprocess                                                # noqa: E402
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
CROP, N = 256, 6000


def log(msg, **kw):
    print(json.dumps({"t": time.strftime("%H:%M:%S"), "msg": msg, **kw}), flush=True)


def bead_in_view(raw: Path) -> dict:
    """The last 100 frames: a bright blob of about a bead's size, well above background."""
    nbytes = CROP * CROP * 2
    size = raw.stat().st_size
    k = min(100, size // nbytes)
    with raw.open("rb") as fh:
        fh.seek(size - k * nbytes)
        a = np.frombuffer(fh.read(k * nbytes), dtype=np.uint16).reshape(k, CROP, CROP).astype(float)
    frame = a.mean(axis=0)
    med, top = float(np.median(frame)), float(frame.max())
    area = int((frame > med + 0.5 * (top - med)).sum())
    ok = top > 10 * med and 1000 <= area <= 30000
    return {"ok": bool(ok), "median": med, "max": top, "bright_area_px": area}


def record(rec_dir: str, label: str) -> bool:
    out = subprocess.run([sys.executable, str(HERE / "record_20260925.py"), rec_dir, label, str(N)],
                         capture_output=True, text=True)
    log("recorded", label=label, returncode=out.returncode, tail=out.stdout[-300:])
    return out.returncode == 0


def wait_question(hold: Path, contains: str, timeout=60) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        q = hold / "question.txt"
        if q.exists() and contains in q.read_text(encoding="utf-8"):
            return True
        time.sleep(0.5)
    return False


def main(hold_dir: str, rec_dir: str, first: float, last: float = 1.0, step: float = 0.1,
         prefix: str = "strength_1_", ready_from: str | None = None,
         pre: float | None = None) -> int:
    """`last`: the strength after whose recording the hold is answered "no" -- a planned
    stop, both traps left as they are -- unless it is the plan's final hold. `ready_from`:
    a completed recording whose bead check answers the plan's opening readiness hold."""
    hold, rec = Path(hold_dir), Path(rec_dir)
    if ready_from:
        check = bead_in_view(Path(ready_from))
        log("readiness bead check", source=ready_from, **check)
        if not check["ok"] or not wait_question(hold, "Before anything is sent"):
            log("STOP: readiness not established; nothing answered")
            return 5
        (hold / "answer.txt").write_text("yes", encoding="utf-8")
        log("answered yes at readiness (the person's standing instruction)")
    if pre is not None:
        # A hold the person asked to pass without a recording ("we can use our
        # 1/0 data"): answer it once the plan reaches it, then wait for the
        # first strength that is recorded.
        if not wait_question(hold, f"trap_2 {pre}", timeout=120):
            log("STOP: the pre-hold did not appear", strength=pre)
            return 6
        (hold / "answer.txt").write_text("yes", encoding="utf-8")
        log("answered yes at a hold not recorded, by the person's instruction", strength=pre)
        if not wait_question(hold, f"trap_2 {round(first, 1)}", timeout=120):
            log("STOP: the first recorded strength's hold did not appear", strength=first)
            return 7
    s = round(first, 1)
    while True:
        label = f"{prefix}{s:.1f}"
        raw = rec / f"{label}.raw"
        if not raw.exists() or raw.stat().st_size < CROP * CROP * 2 * N:
            if not record(rec_dir, label):
                log("STOP: the recording did not complete; nothing answered", label=label)
                return 1
        check = bead_in_view(raw)
        log("bead check", label=label, **check)
        if not check["ok"]:
            log("STOP: no bead-like blob in the last frames; nothing answered", label=label)
            return 2
        if not wait_question(hold, f"trap_2 {s}"):
            log("STOP: the hold for this strength is not the one waiting", strength=s)
            return 3
        if s >= last - 1e-9 and s < 1.0 - 1e-9:
            (hold / "answer.txt").write_text("no", encoding="utf-8")
            log("answered no: a planned stop after the last strength asked for", strength=s)
            return 0
        (hold / "answer.txt").write_text("yes", encoding="utf-8")
        log("answered yes (the person's standing instruction)", strength=s)
        if s >= 1.0:
            log("done: the last hold answered; the plan finishes with both traps at 1.0")
            return 0
        s = round(s + step, 1)
        if not wait_question(hold, f"trap_2 {s}"):
            log("STOP: the next strength's hold did not appear -- the command may have been "
                "refused; see the run log", strength=s)
            return 4


if __name__ == "__main__":
    kw = dict(a[2:].split("=", 1) for a in sys.argv[4:] if a.startswith("--"))
    sys.exit(main(sys.argv[1], sys.argv[2], float(sys.argv[3]),
                  last=float(kw.get("last", 1.0)), step=float(kw.get("step", 0.1)),
                  prefix=kw.get("prefix", "strength_1_"), ready_from=kw.get("ready_from"),
                  pre=float(kw["pre"]) if "pre" in kw else None))
