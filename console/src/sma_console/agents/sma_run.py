"""Follow a soft-matter-agents run, ask it to stop, and read its latest frame.

soft-matter-agents plan.md 11-25 gives a console three things for a run its orchestrator is
executing (origin/feature/autofocus-ui f297a28; f6c0996 card 057, 0c6452d card 058):

- `runs/<run_id>/events.jsonl` beside `log.json`, append only: the first line is
  `run_started` (run_id, plan_id, revision, t0_wall, `stop_channel`, `frame_tap`), then every
  event the run records, in its order, and last `run_ended` with `how` one of RUN_ENDED_HOW.
- The stop channel: a socket on 127.0.0.1 at a port the OS chose, announced only in
  `run_started`. It takes exactly one line, `{"stop": <run_id>, "reason": <text>}`, at most
  STOP_MAX_BYTES, and answers `{"abort": "begun"}` once it has called the run's abort(). Any
  other message is refused, recorded in the run as `stop_refused`, and closed unanswered.
- The frame tap: a socket announced in `run_started` as `frame_tap`. It answers
  `{"get": "latest_frame"}` with one header line (frame, metadata, t_mono, bytes, shape,
  dtype) and then the frame's bytes. It holds no core and never snaps, so it has a frame
  only while the run's own acquisition is producing them.

This module reads the events file and talks to those two sockets. It writes nothing in the
soft-matter-agents tree and imports none of its code. It opens no camera or device: the
console's live view of a run is the tap's copy, so there is never a second Micro-Manager core
(OD-13). Nothing here sends a stop by itself: a stop is sent only when a person asks for it
(`send_stop`), and a viewer that goes away stops nothing (OD-30; soft-matter-agents keeps the
run going too).

An address is accepted only as 127.0.0.1 and a port, because it is read from a file: a file
that names another host does not make the console connect there.
"""

from __future__ import annotations

import json
import math
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

EVENTS_FILE = "events.jsonl"
#: run_ended's `how`, as soft-matter-agents' Orchestrator.end_run documents it
RUN_ENDED_HOW = ("completed", "aborted_by_monitor", "stopped_from_outside", "failed")
#: the longest stop message the run accepts (Orchestrator.STOP_MAX_BYTES)
STOP_MAX_BYTES = 1024
STOP_LINE_PREFIX = "the dino console: "
#: the one request the frame tap answers, sent as one line
FRAME_REQUEST = b'{"get": "latest_frame"}\n'
MAX_EVENTS_BYTES = 16_000_000  # a followed run's events file larger than this is not opened
MAX_HEADER_BYTES = 65_536
MAX_FRAME_BYTES = 128_000_000  # 3200 x 3200 uint16 is 20.5 MB
# abort() runs on the channel's thread before the reply (lights, shutters): give it time
STOP_REPLY_TIMEOUT_S = 15.0
CONNECT_TIMEOUT_S = 2.0
FRAME_TIMEOUT_S = 5.0

_DTYPES = ("uint8", "uint16", "uint32", "int8", "int16", "int32", "float32", "float64")


class SmaRunError(Exception):
    """A followed run could not be read or reached."""


class NotFollowedError(SmaRunError):
    """The run has no events.jsonl, or its first line is not `run_started`."""


class RunEndedError(SmaRunError):
    """The run has written `run_ended`; its sockets are closed."""


class UnreachableError(SmaRunError):
    """The announced socket did not answer a connection."""


@dataclass(frozen=True)
class Address:
    """A loopback socket a run announced. Only 127.0.0.1 is accepted."""

    host: str
    port: int

    @classmethod
    def parse(cls, value: Any) -> Address | None:
        """`{"host": "127.0.0.1", "port": N}` -> Address; anything else -> None."""
        if not isinstance(value, dict):
            return None
        host, port = value.get("host"), value.get("port")
        if host != "127.0.0.1" or not isinstance(port, int) or isinstance(port, bool):
            return None
        if not 0 < port < 65536:
            return None
        return cls(host, port)


@dataclass(frozen=True)
class RunStream:
    """What a run's events.jsonl says so far.

    `events` holds every complete line after `run_started` in file order, `run_ended`
    included when written. A last line without its newline is still being written and is
    left for the next read (`partial_tail`). A line that is not a JSON object is counted in
    `bad_lines` and skipped, not guessed at.
    """

    run_id: str
    plan_id: str | None
    revision: Any
    t0_wall: str | None
    stop_channel: Address | None
    frame_tap: Address | None
    events: list[dict[str, Any]]
    ended: dict[str, Any] | None
    partial_tail: bool = False
    bad_lines: int = 0
    started: dict[str, Any] = field(default_factory=dict)

    @property
    def running(self) -> bool:
        return self.ended is None

    @property
    def ended_how(self) -> str | None:
        if self.ended is None:
            return None
        how = self.ended.get("how")
        return how if isinstance(how, str) else "unknown"


def read_stream(run_dir: str | Path, *, max_bytes: int = MAX_EVENTS_BYTES) -> RunStream:
    """Read `<run_dir>/events.jsonl`. Raises NotFollowedError when the run was not followed
    (no file, or a first line that is not `run_started`), SmaRunError when it is too big."""
    path = Path(run_dir) / EVENTS_FILE
    try:
        size = path.stat().st_size
    except OSError as e:
        raise NotFollowedError(f"{path.parent.name} has no {EVENTS_FILE}") from e
    if size > max_bytes:
        raise SmaRunError(f"{EVENTS_FILE} of {path.parent.name} is {size} bytes, over "
                          f"{max_bytes}; not opened")
    try:
        raw = path.read_bytes()
    except OSError as e:
        raise SmaRunError(f"cannot read {EVENTS_FILE} of {path.parent.name}: {e}") from e
    return parse_stream(raw, path.parent.name)


def parse_stream(raw: bytes, folder: str = "") -> RunStream:
    """The bytes of an events.jsonl, as `read_stream` reads them."""
    lines = raw.split(b"\n")
    tail = lines.pop()  # b"" when the file ends with a newline
    rows: list[dict[str, Any]] = []
    bad = 0
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            row = None
        if isinstance(row, dict):
            rows.append(row)
        else:
            bad += 1
    if not rows or rows[0].get("event") != "run_started":
        raise NotFollowedError(f"{EVENTS_FILE} of {folder or 'this run'} does not begin with "
                               "run_started")
    started, events = rows[0], rows[1:]
    ended = next((e for e in reversed(events) if e.get("event") == "run_ended"), None)
    run_id = started.get("run_id")
    plan_id = started.get("plan_id")
    t0 = started.get("t0_wall")
    return RunStream(
        run_id=run_id if isinstance(run_id, str) else folder,
        plan_id=plan_id if isinstance(plan_id, str) else None,
        revision=started.get("revision"),
        t0_wall=t0 if isinstance(t0, str) else None,
        stop_channel=Address.parse(started.get("stop_channel")),
        frame_tap=Address.parse(started.get("frame_tap")),
        events=events,
        ended=ended,
        partial_tail=bool(tail.strip()),
        bad_lines=bad,
        started=started,
    )


# -- the stop channel ---------------------------------------------------------------------


@dataclass(frozen=True)
class StopResult:
    """What the run answered. `outcome`: `begun` (it called abort), `refused` (it closed
    without a reply: it records why as `stop_refused` in its events), or `no_answer` (sent,
    no reply in time: watch the events for `stop_requested`)."""

    outcome: str
    message: str
    sent_bytes: int


def stop_line(run_id: str, reason: str) -> bytes:
    """The one line the channel accepts, cut to STOP_MAX_BYTES by shortening the reason."""
    text = STOP_LINE_PREFIX + " ".join(reason.split())
    while True:
        line = json.dumps({"stop": run_id, "reason": text}, ensure_ascii=False).encode() + b"\n"
        if len(line) <= STOP_MAX_BYTES or not text:
            break
        text = text[: max(0, len(text) - max(1, len(line) - STOP_MAX_BYTES))]
    if len(line) > STOP_MAX_BYTES:
        raise SmaRunError(f"run id {run_id!r} alone makes the stop longer than "
                          f"{STOP_MAX_BYTES} bytes")
    return line


def send_stop(stream: RunStream, reason: str, *,
              reply_timeout_s: float = STOP_REPLY_TIMEOUT_S) -> StopResult:
    """Ask the run to stop through the channel it announced. Only a person calls this."""
    if stream.ended is not None:
        raise RunEndedError(f"run {stream.run_id} has ended ({stream.ended_how}); its stop "
                            "channel is closed")
    addr = stream.stop_channel
    if addr is None:
        raise NotFollowedError(f"run {stream.run_id} announced no loopback stop channel")
    line = stop_line(stream.run_id, reason)
    try:
        conn = socket.create_connection((addr.host, addr.port), timeout=CONNECT_TIMEOUT_S)
    except OSError as e:
        raise UnreachableError(f"the stop channel of run {stream.run_id} "
                               f"({addr.host}:{addr.port}) did not answer: {e}") from e
    with conn:
        try:
            conn.sendall(line)
            conn.shutdown(socket.SHUT_WR)  # one line and nothing after it
        except OSError as e:
            raise UnreachableError(f"sending the stop to run {stream.run_id} failed: {e}") from e
        conn.settimeout(reply_timeout_s)
        reply = b""
        try:
            while b"\n" not in reply and len(reply) < 4096:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                reply += chunk
        except TimeoutError:
            return StopResult("no_answer", f"sent; run {stream.run_id} did not answer within "
                              f"{reply_timeout_s:g} s. Its events show whether it began to "
                              "abort (stop_requested).", len(line))
        except OSError:
            reply = b""
    try:
        answer = json.loads(reply.decode("utf-8")) if reply.strip() else None
    except (UnicodeDecodeError, ValueError):
        answer = None
    if isinstance(answer, dict) and answer.get("abort") == "begun":
        return StopResult("begun", f"run {stream.run_id} began to abort", len(line))
    return StopResult("refused", f"run {stream.run_id} refused the stop without a reply; it "
                      "records why as stop_refused in its events", len(line))


# -- the frame tap ------------------------------------------------------------------------


@dataclass(frozen=True)
class TapFrame:
    """The run's latest frame as the tap served it. `pixels` is a 2-D array when the header's
    shape and dtype describe the bytes, else None (the bytes are kept)."""

    metadata: dict[str, Any]
    t_mono: float | None
    shape: list[int]
    dtype: str
    data: bytes
    pixels: Any = None


def _recv_exact(conn: socket.socket, n: int, have: bytes) -> bytes:
    buf = bytearray(have)
    while len(buf) < n:
        chunk = conn.recv(min(1 << 20, n - len(buf)))
        if not chunk:
            raise SmaRunError(f"the frame tap closed after {len(buf)} of {n} bytes")
        buf += chunk
    return bytes(buf)


def latest_frame(stream: RunStream, *, timeout_s: float = FRAME_TIMEOUT_S) -> TapFrame | None:
    """Ask the run's frame tap for its latest frame. None: no frame yet (the run has acquired
    nothing, and the tap never acquires). Asks; never commands."""
    if stream.ended is not None:
        raise RunEndedError(f"run {stream.run_id} has ended ({stream.ended_how}); its frame "
                            "tap is closed")
    addr = stream.frame_tap
    if addr is None:
        raise NotFollowedError(f"run {stream.run_id} announced no loopback frame tap")
    try:
        conn = socket.create_connection((addr.host, addr.port), timeout=CONNECT_TIMEOUT_S)
    except OSError as e:
        raise UnreachableError(f"the frame tap of run {stream.run_id} did not answer: {e}") from e
    with conn:
        conn.settimeout(timeout_s)
        try:
            conn.sendall(FRAME_REQUEST)
            got = b""
            while b"\n" not in got:
                if len(got) > MAX_HEADER_BYTES:
                    raise SmaRunError("the frame tap's header line is too long")
                chunk = conn.recv(65_536)
                if not chunk:
                    raise SmaRunError("the frame tap closed without answering")
                got += chunk
            head_raw, rest = got.split(b"\n", 1)
            try:
                head = json.loads(head_raw.decode("utf-8"))
            except (UnicodeDecodeError, ValueError) as e:
                raise SmaRunError("the frame tap's header is not JSON") from e
            if not isinstance(head, dict):
                raise SmaRunError("the frame tap's header is not an object")
            if not head.get("frame"):
                return None
            n = head.get("bytes")
            if not isinstance(n, int) or n < 0 or n > MAX_FRAME_BYTES:
                raise SmaRunError(f"the frame tap announced {n!r} bytes")
            data = _recv_exact(conn, n, rest)[:n]
        except TimeoutError as e:
            raise SmaRunError(f"the frame tap did not finish within {timeout_s:g} s") from e
        except OSError as e:
            raise UnreachableError(f"reading the frame tap failed: {e}") from e
    shape = head.get("shape") if isinstance(head.get("shape"), list) else []
    dtype = head.get("dtype") if isinstance(head.get("dtype"), str) else ""
    t_mono = head.get("t_mono")
    meta = head.get("metadata")
    return TapFrame(
        metadata=meta if isinstance(meta, dict) else {},
        t_mono=float(t_mono) if isinstance(t_mono, int | float) else None,
        shape=[int(x) for x in shape if isinstance(x, int)],
        dtype=dtype,
        data=data,
        pixels=_pixels(data, shape, dtype),
    )


def _pixels(data: bytes, shape: Any, dtype: str) -> Any:
    """A 2-D numpy view of the bytes when the header describes them exactly, else None."""
    if dtype not in _DTYPES or not isinstance(shape, list) or len(shape) != 2:
        return None
    if not all(isinstance(x, int) and x > 0 for x in shape):
        return None
    import numpy as np

    want = math.prod(shape) * np.dtype(dtype).itemsize
    if want != len(data):
        return None
    return np.frombuffer(data, dtype=dtype).reshape(shape)
