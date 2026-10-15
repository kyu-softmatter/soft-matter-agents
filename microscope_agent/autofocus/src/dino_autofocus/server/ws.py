"""WebSocket bridges: `/ws/events` (engine events out, commands in) and `/ws/frames` (live view).

Engine sinks are called from engine threads. Every sink here only serialises and hands the
message to the event loop with `call_soon_threadsafe`, and never raises back into the engine.

Frames: the engine says `frame_ready`; the bridge then takes the newest frame from the engine
(`MultiFrameSource.latest_frames`, one per camera, else `FrameSource.latest_frame`), bins
each camera's frame that changed to at most `target_px` on the long side, maps it to 8 bit and
encodes a JPEG, at most `max_fps` times a second however fast frames arrive. Each client holds
one pending batch (one frame per camera); a slow client skips to the newest instead of
queueing.
Nothing is encoded while nobody watches. Raw frames go to disk records only, never here.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import logging
import math
from collections.abc import Awaitable, Callable
from typing import Any

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from starlette.requests import HTTPConnection

from ..focus import score
from .api import (
    LOGIN_REQUIRED,
    LoginState,
    Refusal,
    command_refusal,
    logged_in_refusal,
    login_state,
    origin_refusal,
)
from .schemas import (
    EngineAPI,
    Event,
    EventOut,
    FrameSource,
    MultiFrameSource,
    WsAccepted,
    WsCommand,
    WsError,
    WsEvent,
    WsFrame,
    WsLock,
)
from .schemas.common import FocusDz

log = logging.getLogger(__name__)

EVENT_QUEUE_MAX = 1000  # a client this far behind is closed (1013) and should reload /api/state
CLOSE_TRY_AGAIN = 1013
CLOSE_UNSUPPORTED = 1003
CLOSE_REFUSED = 4000  # + the HTTP status: 4401 login_required, 4423 locked, 4403 origin
LIVE_FOCUS_METRIC = "vollath4"  # the classical default (focus/classical.py)
LOCK_POLL_S = 1.0  # how soon an open socket notices a lock or unlock with no events flowing


def _ws_error(why: Refusal) -> str:
    return WsError(status=why.status, detail=why.message, code=why.code).model_dump_json()


async def _refuse(websocket: WebSocket, why: Refusal) -> None:
    await websocket.send_text(_ws_error(why))
    await websocket.close(CLOSE_REFUSED + why.status, why.code)


async def _admitted(websocket: WebSocket, *, locked_ok: bool = False) -> LoginState | None:
    """Accept, then require a page from this server's own origin (or a `--dev-origin`; a
    cross-site page can open a WebSocket to 127.0.0.1) and a live login, unlocked unless
    `locked_ok` and the socket is local (D14: a locked microscope-PC page still counts as a
    viewer). A refusal is sent as a WsError before the close, so the browser can read it."""
    await websocket.accept()
    if why := origin_refusal(websocket):
        await _refuse(websocket, why)
        return None
    me = login_state(websocket)
    if why := logged_in_refusal(me, locked_ok=locked_ok and me.local):
        await _refuse(websocket, why)
        return None
    return me


def _drop_events(out: asyncio.Queue, item: Any) -> Any:
    """Drop the queued `event` messages (and `item`, if it is one); keep replies and an
    overflow mark in order. Returns what to handle instead of `item`."""
    kept = []
    while not out.empty():
        queued = out.get_nowait()
        if queued is None or queued[0] != "event":
            kept.append(queued)
    for queued in kept:
        out.put_nowait(queued)
    return () if item and item[0] == "event" else item


def _login_now(conn: HTTPConnection, me: LoginState):
    """The socket's login as it is now (lock state changes; logout or expiry ends it)."""
    return conn.app.state.auth.login(me.token)


class LocalViewers:
    """D14: the engine learns how many microscope-PC browsers watch (`/ws/events` from
    loopback, logged in). The count is reported on every change."""

    def __init__(self, engine: EngineAPI) -> None:
        self._engine = engine
        self.count = 0

    def _report(self) -> None:
        try:
            self._engine.set_local_viewers(self.count)
        except Exception:
            log.exception("could not report %d local viewers", self.count)

    def joined(self) -> None:
        self.count += 1
        self._report()

    def left(self) -> None:
        self.count -= 1
        self._report()


def install(
    app: FastAPI, engine: EngineAPI, *, stopped: Callable[[], bool] = lambda: False
) -> None:
    frames = FrameBridge(engine)
    viewers = LocalViewers(engine)
    app.state.frames = frames
    app.state.local_viewers = viewers

    @app.websocket("/ws/events")
    async def events(websocket: WebSocket) -> None:
        """Events out, commands in. A locked login (local only) gets its lock state and the
        replies to its commands, never event payloads (T-009c, D14)."""
        me = await _admitted(websocket, locked_ok=True)
        if me is None:
            return
        loop = asyncio.get_running_loop()
        # ("event" | "reply", text); None closes the socket (overflow)
        out: asyncio.Queue[tuple[str, str] | None] = asyncio.Queue(maxsize=EVENT_QUEUE_MAX)

        def push(item: tuple[str, str]) -> None:
            try:
                out.put_nowait(item)
            except asyncio.QueueFull:
                while not out.empty():
                    out.get_nowait()
                out.put_nowait(None)  # sender closes the socket

        def sink(ev: Event) -> None:
            try:
                text = WsEvent(event=EventOut.from_engine(ev)).model_dump_json()
                loop.call_soon_threadsafe(push, ("event", text))
            except RuntimeError:
                pass  # loop already closed: the client has gone
            except Exception:
                log.exception("event %r could not be forwarded", getattr(ev, "kind", ev))

        async def send() -> None:
            locked = bool(me.info and me.info.locked)
            await websocket.send_text(WsLock(locked=locked).model_dump_json())
            while True:
                try:
                    item = await asyncio.wait_for(out.get(), LOCK_POLL_S)
                except TimeoutError:
                    item = ()  # no message: only look at the lock
                info = _login_now(websocket, me)
                if info is None:  # logged out or expired while connected
                    await _refuse(websocket, LOGIN_REQUIRED)
                    return
                if info.locked != locked:
                    locked = info.locked
                    if not locked:  # events queued while locked are stale: the client
                        item = _drop_events(out, item)  # reloads /api/state on unlock
                    await websocket.send_text(WsLock(locked=locked).model_dump_json())
                if item is None:
                    await websocket.close(CLOSE_TRY_AGAIN, "event queue overflow; reload state")
                    return
                if not item or (locked and item[0] == "event"):
                    continue  # a locked page never shows data
                await websocket.send_text(item[1])

        async def receive() -> None:
            while True:
                reply = await _command_reply(await websocket.receive_text(), websocket)
                push(("reply", reply.model_dump_json()))

        async def _command_reply(text: str, conn: HTTPConnection) -> WsAccepted | WsError:
            try:
                msg = WsCommand.model_validate_json(text)
            except ValidationError as e:
                return WsError(status=422, detail=str(e), code="invalid")
            # login and lock are read again for every command: the socket outlives a lock
            if why := command_refusal(conn, msg.command.kind, msg.command.op):
                return WsError(status=why.status, detail=why.message, code=why.code)
            if stopped():
                return WsError(status=503, detail="the server is shutting down",
                               code="shutting_down")
            me = login_state(conn)
            cmd = msg.command.to_engine(remote=not me.local, user_id=me.user_id,
                                        control_grant=conn.app.state.auth.grant_for(me.info))
            try:
                op_id = await asyncio.to_thread(engine.submit, cmd)
            except ValueError as e:  # runner.CommandRefused
                return WsError(status=400, detail=str(e), code="refused")
            return WsAccepted(op_id=op_id)

        local = me.local
        unsubscribe = engine.subscribe(sink)
        if local:
            viewers.joined()
        try:
            await _until_first_done(send(), receive())
        finally:
            unsubscribe()
            if local:
                viewers.left()

    @app.websocket("/ws/frames")
    async def live_frames(websocket: WebSocket) -> None:
        me = await _admitted(websocket)
        if me is None:
            return
        if not isinstance(engine, FrameSource):
            await websocket.send_text(WsError(status=501, detail="this engine provides no frames",
                                              code="no_frames").model_dump_json())
            await websocket.close(CLOSE_UNSUPPORTED)
            return
        slot: asyncio.Queue[FrameBatch] = asyncio.Queue(maxsize=1)

        async def send() -> None:
            while True:
                batch = await slot.get()
                info = _login_now(websocket, me)
                if info is None:
                    await _refuse(websocket, LOGIN_REQUIRED)
                    return
                if info.locked:
                    continue  # a locked page never shows data; frames resume on unlock
                for meta, jpeg in batch:
                    await websocket.send_text(meta)
                    await websocket.send_bytes(jpeg)

        async def wait_disconnect() -> None:
            while (await websocket.receive())["type"] != "websocket.disconnect":
                pass

        frames.add(slot)
        try:
            await _until_first_done(send(), wait_disconnect())
        finally:
            frames.remove(slot)


async def _until_first_done(*coros: Awaitable[None]) -> None:
    """Run until one finishes (or the client disconnects), then cancel the rest."""
    tasks = [asyncio.ensure_future(c) for c in coros]
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in done:
            exc = t.exception()
            if exc is not None and not isinstance(exc, WebSocketDisconnect):
                raise exc
    finally:
        for t in tasks:
            t.cancel()
        for t in tasks:
            with contextlib.suppress(asyncio.CancelledError, WebSocketDisconnect, Exception):
                await t


#: one wake's frames, one per camera that changed: (WsFrame JSON, JPEG) pairs
FrameBatch = tuple[tuple[str, bytes], ...]


class FrameBridge:
    def __init__(
        self, engine: EngineAPI, *, max_fps: float = 10.0, target_px: int = 800,
        quality: int = 80,
    ) -> None:
        self.engine = engine
        self.max_fps = max_fps
        self.target_px = target_px
        self.quality = quality
        self.seq = 0
        self._clients: set[asyncio.Queue[FrameBatch]] = set()
        self._sent: dict[str, object] = {}  # camera -> the frame tuple last encoded
        self._unsubscribe: Callable[[], None] | None = None
        self._pump: asyncio.Task[None] | None = None
        self._wake = asyncio.Event()

    @property
    def watching(self) -> int:
        return len(self._clients)

    def add(self, slot: asyncio.Queue[FrameBatch]) -> None:
        self._clients.add(slot)
        if self._unsubscribe is None:
            loop = asyncio.get_running_loop()
            self._wake = asyncio.Event()

            def sink(ev: Event) -> None:
                if ev.kind == "frame_ready":
                    with contextlib.suppress(RuntimeError):  # loop closed
                        loop.call_soon_threadsafe(self._wake.set)

            self._unsubscribe = self.engine.subscribe(sink)
            self._pump = asyncio.ensure_future(self._run())
        # a newcomer gets every camera's current frame at once, including one that is idle
        self._sent.clear()
        self._wake.set()

    def remove(self, slot: asyncio.Queue[FrameBatch]) -> None:
        self._clients.discard(slot)
        if not self._clients and self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
            if self._pump is not None:
                self._pump.cancel()
                self._pump = None

    async def _run(self) -> None:
        loop = asyncio.get_running_loop()
        last = -math.inf
        while True:
            await self._wake.wait()
            wait = last + 1.0 / self.max_fps - loop.time()
            if wait > 0:
                await asyncio.sleep(wait)
            self._wake.clear()  # frames that came during the wait are covered by this one
            fresh = [(cam, got) for cam, got in self._latest().items()
                     if self._sent.get(cam) is not got]
            if not fresh:
                continue
            last = loop.time()
            batch: list[tuple[str, bytes]] = []
            for cam, got in sorted(fresh, key=lambda kv: kv[0]):
                self._sent[cam] = got
                try:
                    frame, jpeg = await asyncio.to_thread(
                        encode_frame, got[0], got[1], self.seq + 1, self.target_px,
                        self.quality)
                except Exception:
                    log.exception("live frame could not be encoded")
                    continue
                self.seq = frame.seq
                batch.append((frame.model_dump_json(), jpeg))
            if not batch:
                continue
            item: FrameBatch = tuple(batch)
            for slot in self._clients:
                if slot.full():
                    slot.get_nowait()  # drop the stale batch
                slot.put_nowait(item)

    def _latest(self) -> dict[str, tuple[Any, dict[str, Any]]]:
        """The newest frame per camera; a single-camera engine counts as one camera."""
        if isinstance(self.engine, MultiFrameSource):
            many = self.engine.latest_frames()
            if many:
                return many
        got = self.engine.latest_frame()  # type: ignore[attr-defined]
        if got is None:
            return {}
        return {str(got[1].get("camera") or ""): got}


def encode_frame(
    pixels: Any, meta: dict[str, Any], seq: int, target_px: int = 800, quality: int = 80
) -> tuple[WsFrame, bytes]:
    """Bin a mono frame to at most `target_px` on the long side and JPEG it. Display range is
    the 0.5-99.5 percentile of the binned frame (reported, so the UI can say so). The live
    focus score is `LIVE_FOCUS_METRIC` on the binned frame (cheap at 10 fps per camera)."""
    from PIL import Image

    a = np.asarray(pixels)
    if a.ndim != 2:
        raise ValueError(f"expected a mono 2-D frame, got shape {a.shape}")
    h, w = a.shape
    b = max(1, math.ceil(max(h, w) / target_px))
    hb, wb = h // b, w // b
    binned = a[: hb * b, : wb * b].astype(np.float32).reshape(hb, b, wb, b).mean(axis=(1, 3))
    lo, hi = (float(v) for v in np.percentile(binned, (0.5, 99.5)))
    if hi <= lo:
        hi = lo + 1.0
    u8 = np.clip((binned - lo) * (255.0 / (hi - lo)), 0, 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(u8).save(buf, format="JPEG", quality=quality)
    jpeg = buf.getvalue()
    focus = score(binned, LIVE_FOCUS_METRIC) if min(binned.shape) >= 3 else None
    if focus is not None and not math.isfinite(focus):
        focus = None
    try:  # the engine's gauge reading, if any (engine/live_dz.py); a bad one is dropped
        dz = FocusDz.model_validate(meta["focus_dz"]) if meta.get("focus_dz") else None
    except ValidationError:
        dz = None
    frame = WsFrame(
        # the runner's frames carry t_read (when popped from the camera), the placeholder t
        seq=seq, t=float(meta.get("t", meta.get("t_read", 0.0)) or 0.0), width=wb, height=hb,
        binning=b,
        source_width=w, source_height=h, display_min=lo, display_max=hi,
        jpeg_bytes=len(jpeg), camera=(str(meta["camera"]) if meta.get("camera") else None),
        focus_score=focus, focus_metric=LIVE_FOCUS_METRIC if focus is not None else None,
        focus_dz=dz, meta=meta,
    )
    return frame, jpeg
