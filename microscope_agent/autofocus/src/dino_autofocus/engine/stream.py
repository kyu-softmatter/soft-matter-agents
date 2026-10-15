"""The engine-owned live stream (`runner.AcquisitionStream`) for simulated backends.

A thread asks the backend for its next stream frame (`start_stream` / `next_frame`) and hands
each one to `Runner.publish_frame`, so the live view shows frames while nothing runs. The
runner pauses it around an operation that snaps (`Operation.snaps`), stops it at shutdown.

- Only for the mock backend: `BackendStream.for_backend` refuses the bench (`is_bench`) and
  every other backend.
  The stand's stream is a later, separate decision (it shares one Micro-Manager core).
- `decorate(frame) -> list[Frame]` may add pictures to each frame (the mock tweezers draw their
  traps, and a second camera shows the trap laser spots); it runs on this thread.
- `wanted() -> bool` (the server: someone has `/ws/frames` open) keeps a slow simulated
  picture (the mock world takes ~0.4 s a frame) from using a core while nobody watches.
- The backend call never waits inside the runner's backend lock: `next_frame(timeout_s=0)`
  answers at once, and the thread sleeps outside the lock.
"""

from __future__ import annotations

import dataclasses
import logging
import threading
import time
from collections.abc import Callable
from typing import Any

from .backend import Frame, is_bench

log = logging.getLogger(__name__)

Publish = Callable[[Frame], Any]
Decorate = Callable[[Frame], list[Frame]]


class BackendStream:
    def __init__(self, backend: Any, *, interval_s: float = 0.1,
                 decorate: Decorate | None = None, pixel_um: Callable[[], float | None] | None
                 = None, wanted: Callable[[], bool] | None = None) -> None:
        self.backend = backend
        self.interval_s = interval_s
        self.decorate = decorate
        self._pixel_um = pixel_um
        self.wanted = wanted
        self._publish: Publish | None = None
        self._lock = threading.Lock()
        self._want = threading.Event()  # set: streaming (not paused, not stopped)
        self._stopped = threading.Event()
        self._thread: threading.Thread | None = None
        self._streaming = False  # the backend's stream is on (under self._lock)

    @classmethod
    def for_backend(cls, backend: Any, **kw) -> BackendStream:
        """The mock only: the thread calls the backend outside the runner's SerializedBackend,
        which the in-memory mock tolerates and a Micro-Manager core would not."""
        info = backend.info()
        if is_bench(info) or getattr(info, "kind", None) != "mock":
            raise ValueError("the live stream is for the mock backend only (not the bench, "
                             "not mm-demo or replay)")
        return cls(backend, **kw)

    def attach(self, publish: Publish) -> None:
        """Start streaming into `publish` (the runner's `publish_frame`)."""
        with self._lock:
            self._publish = publish
            if self._thread is None and not self._stopped.is_set():
                self._want.set()
                self._thread = threading.Thread(target=self._run, name="live-stream",
                                                daemon=True)
                self._thread.start()

    # -- runner.AcquisitionStream
    def running(self) -> bool:
        """Not paused and not stopped: the runner pauses the stream around an operation that
        snaps whenever this is True, watched or not, so no viewer arriving mid-operation can
        restart the camera stream under it."""
        return self._want.is_set() and not self._stopped.is_set()

    def live(self) -> bool:
        """Frames really come now: running and watched. A frame grab that finds this False
        snaps for itself (the thread stops the camera stream within ~0.2 s of the last viewer
        leaving; a snap in that window gets `StreamActive` and retries)."""
        return self.running() and (self.wanted is None or bool(self.wanted()))

    def pause(self) -> None:
        self._want.clear()
        with self._lock:  # the thread holds this lock while it touches the backend
            self.backend.stop_stream()
            self._streaming = False

    def resume(self) -> None:
        if not self._stopped.is_set():
            self._want.set()

    def stop(self) -> None:
        self._stopped.set()
        self._want.set()  # wake the thread so it can leave
        t = self._thread
        if t is not None and t is not threading.current_thread():
            t.join(timeout=2.0)
        with self._lock:
            self.backend.stop_stream()
            self._streaming = False

    # -- thread
    def _run(self) -> None:
        while not self._stopped.is_set():
            if not self._want.wait(timeout=0.5):
                continue
            if self._stopped.is_set():
                break
            if self.wanted is not None and not self.wanted():
                with self._lock:  # nobody watches: render nothing, and let snaps through
                    if self._streaming:
                        self.backend.stop_stream()
                        self._streaming = False
                time.sleep(0.2)
                continue
            frame = None
            with self._lock:
                if not self._want.is_set():
                    continue
                try:
                    if not self._streaming:
                        self.backend.start_stream(self.interval_s * 1000.0)
                        self._streaming = True
                    frame = self.backend.next_frame(timeout_s=0.0)
                except Exception:  # noqa: BLE001 - a failed frame is logged, the stream goes on
                    log.exception("live stream frame failed")
                    self._streaming = False
                    time.sleep(0.5)  # do not spin on a backend that keeps failing
            if frame is None:
                time.sleep(min(self.interval_s, 0.02))
                continue
            self._send(frame)

    def _send(self, frame: Frame) -> None:
        if self._pixel_um is not None:
            frame = dataclasses.replace(frame, pixel_um=self._pixel_um())
        frames = [frame]
        if self.decorate is not None:
            try:
                frames = self.decorate(frame)
            except Exception:  # noqa: BLE001
                log.exception("live stream decoration failed")
        for f in frames:
            if self._publish is not None:
                self._publish(f)
