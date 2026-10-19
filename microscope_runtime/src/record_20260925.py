"""Record one fixed-length video of the centre of the red camera, under the Aura (card 049).

    python src/record_20260925.py <out_dir> <label> <n_frames> [--crop=256]

Preparatory, not a planned measurement. The person asked on 2026-09-25 for
"videos for each powers for 3 min" during the trap-strength scan, and that
no live view is needed. Each call loads the day's configuration (AutoShutter
0), sets DiaLamp State 0 and the Aura GREEN at 50 per-mille with State 1 --
the person's "Green, 5%, 30 ms" -- sets a centre crop, and takes exactly
n_frames through the sequence call, counting frames and never elapsed time.
Frames go to <out_dir>/<label>.raw (uint16, C order, crop x crop) with each
frame's camera metadata in <label>_meta.jsonl. The Aura is LEFT ON at exit
and the log says so. Nothing here touches the tweezers.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]

import importlib.util                                            # noqa: E402
import json                                                      # noqa: E402
import time                                                      # noqa: E402
from datetime import datetime                                    # noqa: E402
from pathlib import Path                                         # noqa: E402

import numpy as np                                               # noqa: E402

CONFIG = Path(r"C:\agentic_microscope\config\micromanager\single_cam_red_noDMD_nocom10.cfg")
EXPOSURE_MS = 30.0
AURA = [("GREEN_Intensity", 50), ("GREEN", 1), ("State", 1)]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def main(out_dir: str, label: str, n_frames: int, crop: int) -> int:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    log = (out / "record_log.jsonl").open("a", encoding="utf-8")

    def rec(**event):
        event = {"t": datetime.now().astimezone().isoformat(timespec="milliseconds"),
                 "label": label, **event}
        log.write(json.dumps(event, default=str) + "\n")
        log.flush()
        print(json.dumps(event, default=str)[:300], flush=True)

    mm = _load("_mm_record", Path(_HERE) / "devices" / "micromanager.py")
    rec(event="start", by="microscope-20260924-6", n_frames=n_frames, crop_px=crop,
        exposure_ms=EXPOSURE_MS, note="preparatory recording at the person's request; not a planned measurement")
    rec(event="load", **mm.load_configuration(str(CONFIG)))
    core = mm._core()
    rec(event="lamp", **mm.set_and_read("DiaLamp", "State", 0))
    for prop, value in AURA:
        rec(event="aura", **mm.set_and_read("Aura", prop, value))
    rec(event="exposure", **mm.set_exposure(EXPOSURE_MS))
    w, h = core.getImageWidth(), core.getImageHeight()
    x0, y0 = (w - crop) // 2, (h - crop) // 2
    core.setROI(x0, y0, crop, crop)
    rec(event="roi", x=x0, y=y0, width=crop, height=crop, read=list(core.getROI()))

    raw = (out / f"{label}.raw").open("wb")
    meta = (out / f"{label}_meta.jsonl").open("w", encoding="utf-8")

    def sink(i, image, md):
        raw.write(np.asarray(image, dtype=np.uint16).tobytes())
        meta.write(json.dumps({"n": i, "ImageNumber": md.get("ImageNumber"),
                               "ElapsedTime-ms": md.get("ElapsedTime-ms"),
                               "host_t": time.time()}) + "\n")

    t0 = time.time()
    result = mm.sequence(n_frames, sink)
    raw.close()
    meta.close()
    rec(event="sequence", wall_s=round(time.time() - t0, 2), dtype="uint16", shape=[crop, crop],
        raw=str(out / f"{label}.raw"), **{k: v for k, v in result.items() if k != "image_numbers"})
    rec(event="stop", left_as="Aura GREEN ON at 50 per-mille, State 1; DiaLamp State 0; "
                              "the core unloads when this process exits")
    return 0 if result.get("received") == n_frames else 1


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    crop = next((int(a.split("=", 1)[1]) for a in sys.argv if a.startswith("--crop=")), 256)
    sys.exit(main(args[0], args[1], int(args[2]), crop))
