"""Signed live focus reading for the live view's -10..+10 gauge (scripts/live_focus.py `Gauge`,
the 2026-09-30 run): dz = stage - best focus in depths of field, 0 = in focus.

Two sources, both attached to a frame's meta as `focus_dz` (see `focus_dz`):

- the mock's own truth (`Frame.dz_truth_dof`), marked ``"mock_truth"``: a picture aid, not a
  measurement;
- a trained DINO head (`DzReader` over `dino_autofocus.live.FocusScorer`), marked ``"model"``.
  Scoring runs on its own thread on the newest frame only (it never queues up), and the value
  shown is the median of the last `MEDIAN_N` readings, as on 9/30: one frame's score scatters by
  ~1 DoF, the median of five by much less.

Display only: nothing here moves anything or feeds a decision.
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from typing import Any

import numpy as np

log = logging.getLogger(__name__)

MEDIAN_N = 5
GAUGE_DOF = 10.0  # the gauge's half range, depths of field


def focus_dz(dz_dof: float | None, sigma_dof: float | None, source: str, note: str = "",
             sign_known: bool | None = None) -> dict[str, Any]:
    """The `focus_dz` meta entry. `dz_dof` None: nothing readable in view (`note` says why)."""
    if dz_dof is not None and not np.isfinite(dz_dof):
        dz_dof = None
    if sigma_dof is not None and not np.isfinite(sigma_dof):
        sigma_dof = None
    if sign_known is None:
        sign_known = dz_dof is not None and (sigma_dof is None or abs(dz_dof) > sigma_dof)
    return {"dz_dof": dz_dof, "sigma_dof": sigma_dof, "source": source, "note": note,
            "sign_known": bool(sign_known)}


def truth_dz(dz_dof: float) -> dict[str, Any]:
    return focus_dz(float(dz_dof), None, "mock_truth", "mock truth, not a measurement", True)


class DzReader:
    """Scores the newest frame given to `feed` on a worker thread with `scorer` (a callable
    image -> `FocusReading`); `latest()` is the median of the last `MEDIAN_N` readings. With
    `camera` set, the runner feeds it only that camera's frames (two cameras on one stand)."""

    def __init__(self, scorer: Any, *, camera: str | None = None, median_n: int = MEDIAN_N):
        self._scorer = scorer
        self.camera = camera
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._frame: np.ndarray | None = None
        self._hist: deque[float] = deque(maxlen=median_n)
        self._latest: dict[str, Any] | None = None
        self._stop = False
        self._thread: threading.Thread | None = None

    def feed(self, image: np.ndarray) -> dict[str, Any] | None:
        """Hand over a frame (the newest wins) and return the current reading, or None before
        the first one."""
        with self._lock:
            self._frame = image
            if self._thread is None and not self._stop:
                self._thread = threading.Thread(target=self._run, daemon=True,
                                                name="engine-live-dz")
                self._thread.start()
            latest = self._latest
        self._wake.set()
        return None if latest is None else dict(latest)

    def latest(self) -> dict[str, Any] | None:
        with self._lock:
            return None if self._latest is None else dict(self._latest)

    def stop(self) -> None:
        with self._lock:
            self._stop = True
        self._wake.set()

    def _run(self) -> None:
        while True:
            self._wake.wait()
            self._wake.clear()
            with self._lock:
                if self._stop:
                    return
                img, self._frame = self._frame, None
            if img is not None:
                self.read_now(img)

    def read_now(self, img: np.ndarray) -> dict[str, Any]:
        """Score one frame here (the worker's step; tests call it directly)."""
        try:
            rd = self._scorer(img)
        except Exception as e:  # noqa: BLE001 - a failed read is shown, never raised
            log.exception("live DINO reading failed")
            out = focus_dz(None, None, "model", f"reading failed: {type(e).__name__}")
        else:
            n_tiles = len(rd.tiles)
            if rd.score is None:
                with self._lock:
                    self._hist.clear()
                out = focus_dz(None, None, "model", "no readable sample in view")
            else:
                with self._lock:
                    self._hist.append(float(rd.score))
                    med = float(np.median(self._hist))
                note = (f"{rd.where}: {rd.n_used}/{n_tiles} tiles"
                        + ("" if rd.sign_known else ", sign unsure"))
                out = focus_dz(med, rd.sigma, "model", note, rd.sign_known)
        with self._lock:
            self._latest = out
        return dict(out)
