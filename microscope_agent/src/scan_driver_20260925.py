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


def main(hold_dir: str, rec_dir: str, first: float) -> int:
    hold, rec = Path(hold_dir), Path(rec_dir)
    s = round(first, 1)
    while True:
        label = f"strength_1_{s:.1f}"
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
        (hold / "answer.txt").write_text("yes", encoding="utf-8")
        log("answered yes (the person's standing instruction)", strength=s)
        if s >= 1.0:
            log("done: the last hold answered; the plan finishes with both traps at 1.0")
            return 0
        s = round(s + 0.1, 1)
        if not wait_question(hold, f"trap_2 {s}"):
            log("STOP: the next strength's hold did not appear -- the command may have been "
                "refused; see the run log", strength=s)
            return 4


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2], float(sys.argv[3])))
