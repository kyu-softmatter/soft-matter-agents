"""Run plan-mic-20260925-002-r1 through operator.run, with the person's hand-over and hold answers.

    python src/run_trap_plan_20260925.py <run_id> <answer_dir>

The hold asks the person in the seat's window; the seat writes the person's
answer, verbatim, to <answer_dir>/answer.txt, and this process reads it.
Nothing here composes a command: operator.run derives every one from the plan.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]

import importlib.util                                            # noqa: E402
import json                                                      # noqa: E402
import time                                                      # noqa: E402
from pathlib import Path                                         # noqa: E402

AGENT = Path(_HERE).parent
PLAN = AGENT / "questions" / "mic-20260925-002" / "plan_microscope_mic-20260925-002.json"

HANDOVER = {
    "objective": "100x",
    "statements": [
        {"gate": "bench_is_this_seats", "said": "it is yours. no other session",
         "asked": "A bead is in view, and the bench is mine, with no other session on the camera or tweezers."},
        {"gate": "laser_power_at_the_dial", "said": "now 0.05",
         "asked": "The laser power on the dial, and that the laser is emitting.",
         "note": "the person's reading of the hand control; nothing here reads it. Emission was not restated"},
        {"gate": "objective", "said": "correct", "asked": "The objective: 100x oil."},
        {"gate": "bead_height", "said": "I wiil see that, show me live view (you don't need to show me full frame)",
         "asked": "How you'll judge the bead is lifted off the glass.",
         "note": "judged by the person by eye on a centre-crop live view this seat started"},
    ],
    # Asked in this seat's window at ~20:40Z: "Is the tweezers software's position
    # calibration done for the 100x objective as it sits now?" -> "Yes, calibrated
    # at 100x". No value was given, so pixel_to_um records the statement itself.
    "tweezers_calibration": {"objective": "100x", "stated_by": "kyuhwan",
                             "pixel_to_um": "calibrated at 100x, the person's statement; value not given"},
    "lamp_at_handover":"DiaLamp State 1, Intensity 2100, set and read back by this seat's live view",
}

# Every number the link needs, with where it came from (python_tcp.Link has no defaults).
LINK = {
    "host": "127.0.0.1", "port": 2070,
    "connect_timeout_s": 5.0, "reply_timeout_s": 2.0, "min_gap_s": 0.1,
    "busy_retries": 3, "busy_backoff_s": 0.1,
    "numbers_from": ("port 2070: observed 2026-09-24 and by architecture's netstat 2026-09-25 "
                     "(tweezers_live_checklist 1c, no entry). min_gap 0.1 s: above the 10 ms at which "
                     "a create still came back busy (tweez300_back_to_back_sends_come_back_busy, E3). "
                     "busy_retries 3 with 0.1 s backoff: a busy is an explicit refusal, safe to re-send; "
                     "count and backoff chosen here. Timeouts chosen here; a silence is never retried."),
}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def main(run_id: str, answer_dir: str) -> int:
    ans = Path(answer_dir)
    ans.mkdir(parents=True, exist_ok=True)

    def ask_person(statement: str):
        (ans / "question.txt").write_text(statement, encoding="utf-8")
        print(f"HOLD: {statement}", flush=True)
        f = ans / "answer.txt"
        # A stale answer must never answer the next hold: clear any leftover
        # before asking, and consume the answer when it is read. Until
        # run-20260925-011 the file stayed, so a second hold would have read the
        # first hold's "yes" and gone on without the person.
        if f.exists():
            f.unlink()
        (ans / "question.txt").write_text(statement, encoding="utf-8")
        while not f.exists():
            time.sleep(0.5)
        time.sleep(0.2)                     # let the writer finish
        answer = f.read_text(encoding="utf-8").strip()
        f.unlink()
        return answer

    op = _load("_mic_operator_run", Path(_HERE) / "operator.py")
    link = {**LINK, "log_path": ans / "tweezers_dispatch.jsonl"}
    plan = Path(sys.argv[3]) if len(sys.argv) > 3 else PLAN
    record = op.run(plan, run_id, backend="hardware", handover=HANDOVER,
                    ask_person=ask_person, tweezers_link=link)
    folder = op.write_run(record)
    print(f"WROTE {folder}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
