"""A live view of the centre of the red camera, for the person watching a trap (card 049).

    python src/live_view_20260925.py <out_dir>

Preparatory, not a planned measurement: it records nothing for the store.
It loads the configuration the day's bench used, sets AutoShutter 0 (the
load does), switches the transmitted lamp to State 1 at Intensity 2100 --
the state architecture left it in, and the loaded file's startup preset
turns it off -- and streams a centre crop of the sensor to a window until
the window is closed. Every write goes through GuardedCore and is read back.

On close: the acquisition stops. The lamp is LEFT ON and the configuration
stays loaded, and the log says so, because the double-well record after this
needs both. Nothing here touches the tweezers.
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

CONFIG = Path(r"C:\agentic_microscope\config\micromanager\single_cam_red_noDMD_nocom10.cfg")
CROP = 600          # pixels on a side at the sensor centre: 39 um at 100x, 1x (0.065 um/px, E2)
EXPOSURE_MS = 30.0  # the person's 30 ms of this morning
LAMP = {"State": 1, "Intensity": 2100}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def main(out_dir: str) -> int:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    log = (out / "live_view_log.jsonl").open("a", encoding="utf-8")

    def rec(**event):
        event = {"t": datetime.now().astimezone().isoformat(timespec="milliseconds"), **event}
        log.write(json.dumps(event, default=str) + "\n")
        log.flush()
        print(json.dumps(event, default=str), flush=True)

    mm = _load("_mm_live", Path(_HERE) / "devices" / "micromanager.py")
    rec(event="start", by="microscope-20260924-6", config=str(CONFIG), crop_px=CROP,
        note="preparatory live view for the person; not a planned measurement")
    rec(event="load", **mm.load_configuration(str(CONFIG)))
    core = mm._core()
    for prop, value in LAMP.items():
        rec(event="lamp", **mm.set_and_read("DiaLamp", prop, value))
    rec(event="exposure", **mm.set_exposure(EXPOSURE_MS))
    w, h = core.getImageWidth(), core.getImageHeight()
    x0, y0 = (w - CROP) // 2, (h - CROP) // 2
    core.setROI(x0, y0, CROP, CROP)
    rec(event="roi", x=x0, y=y0, width=CROP, height=CROP, read=list(core.getROI()))

    # tkinter, not matplotlib: matplotlib is not installed on this computer,
    # and installing a package is provisioning, which is the person's. A frame
    # is shown as an 8-bit PGM, scaled between its own min and max.
    import tkinter as tk
    import numpy as np

    root = tk.Tk()
    root.title("live view: centre of camera_red (Kinetix_red), 100x -- red cross = trap (0, 0)")
    canvas = tk.Canvas(root, width=CROP, height=CROP)
    canvas.pack()
    photo = {"img": None}
    item = canvas.create_image(0, 0, anchor="nw")
    canvas.create_line(CROP // 2, 0, CROP // 2, CROP, fill="red")
    canvas.create_line(0, CROP // 2, CROP, CROP // 2, fill="red")
    state = {"frames": 0, "open": True}

    def on_close():
        state["open"] = False
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    core.startContinuousSequenceAcquisition(0.0)
    rec(event="acquisition_started")

    def tick():
        if not state["open"]:
            return
        if core.getRemainingImageCount() > 0:
            img = np.asarray(core.getLastImage(), dtype=np.float32)
            core.clearCircularBuffer()
            lo, hi = float(img.min()), float(img.max())
            g = ((img - lo) * (255.0 / max(hi - lo, 1.0))).astype(np.uint8)
            data = b"P5 %d %d 255\n" % (g.shape[1], g.shape[0]) + g.tobytes()
            photo["img"] = tk.PhotoImage(data=data, format="PPM")
            canvas.itemconfigure(item, image=photo["img"])
            state["frames"] += 1
        root.after(30, tick)

    try:
        root.after(30, tick)
        root.mainloop()
    finally:
        if core.isSequenceRunning():
            core.stopSequenceAcquisition()
        rec(event="stop", frames_displayed=state["frames"],
            left_as="lamp ON (State 1, Intensity 2100); acquisition stopped; the core "
                    "unloads when this process exits")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else r"D:\soft-matter-agents-frames\run-20260925-002"))
