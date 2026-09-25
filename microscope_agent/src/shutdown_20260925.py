"""End of the day's bench, at the person's word: "turn off OT laser, and microsceop" (2026-09-25).

    python src/shutdown_20260925.py <log_dir>

Only the directions that remove light, which python_tcp always allows and
which is the abort path's own sequence: TRAP_OFF for each trap, then
LASER_OFF. A zero is acceptance, not a dark sample: the beam is reported
ASSUMED ON afterwards until the person sees it off. Then the Aura's master
State 0 and the transmitted lamp's State 0 through Micro-Manager, each read
back. Nothing is switched on, moved or powered down: switching the stand,
controllers and the tweezers' key off is the person's hand.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]

import importlib.util                                            # noqa: E402
import json                                                      # noqa: E402
from pathlib import Path                                         # noqa: E402

CONFIG = Path(r"C:\agentic_microscope\config\micromanager\single_cam_red_noDMD_nocom10.cfg")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def main(log_dir: str) -> int:
    out = Path(log_dir)
    out.mkdir(parents=True, exist_ok=True)
    tcp = _load("_tcp_shutdown", Path(_HERE) / "devices" / "python_tcp.py")
    tcp.connect(host="127.0.0.1", port=2070, connect_timeout_s=5.0, reply_timeout_s=2.0, min_gap_s=0.1,
                busy_retries=3, busy_backoff_s=0.1, log_path=out / "tweezers_dispatch.jsonl",
                numbers_from="as run_trap_plan_20260925.py LINK")
    report = tcp.abort(traps=["trap_1", "trap_2"])
    print(json.dumps({"tweezers": [(e.get("command"), e.get("outcome"), e.get("status"))
                                   for e in report["dispatched"]], "beam": report["beam"]}))
    mm = _load("_mm_shutdown", Path(_HERE) / "devices" / "micromanager.py")
    mm.load_configuration(str(CONFIG))
    for dev, prop in (("Aura", "State"), ("Aura", "GREEN"), ("DiaLamp", "State")):
        print(json.dumps(mm.set_and_read(dev, prop, 0)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
