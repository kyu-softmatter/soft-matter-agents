"""[Lights off] from the console (card 023 part 5; `plan.md` 15.1 item 11, the person's `27139a5a`).

The live-view host accepts a fourth message: exactly `{"lights_off": true}`. It names no source, no
value and no run, so it can only ask for less light. The host does the turning off, through the one
execution path, and answers once it has finished (`lights_off_reply` in
`contracts/schemas/run_interface.schema.json`). **The console sends that line and shows the answer.** It
builds no power-down of its own, never reads a device and never decides from the answer what is off:
a row is shown as the host gave it, read from the reply that the schema accepted.

What the console adds is only what the schema leaves to the sender:

- The line is built here once, as bytes, and nothing else is ever sent. It is not assembled from a
  request, so nothing the browser sends can reach the host.
- **It is sent once.** A failure, a silence or a refused reply is shown, never retried: a second
  request would be a second power-down the person did not ask for.
- A reply the schema refuses is not shown at all, not even in part. It is `no_answer`, and the page
  says nothing is known about the lights.
- Nothing here raises: every way the press can fail is an answer, because the person pressing it may
  be pressing it because something is wrong.
- **The address is the one the server was started with** (`--live-host`, or `--live-host-file`), never
  the default file the live view falls back to. A press with no host given sends nothing.
"""

from __future__ import annotations

import json
import socket
from dataclasses import dataclass, field
from typing import Any

from .schema_lite import SchemaError, Schemas
from .sma_live import host_address, parse_host
from .sma_run import CONNECT_TIMEOUT_S, Address

LIGHTS_OFF_LINE = b'{"lights_off": true}\n'
REPLY_TIMEOUT_S = 60.0  # the host answers when it has finished: it may stop a run first
MAX_REPLY_BYTES = 65536
SCHEMA_FILE = "run_interface.schema.json"
REPLY_DEF = "#/$defs/lights_off_reply"

NO_HOST = ("no live-view host was given to this console, so nothing was sent. "
           "Nothing is known about the lights: use the switches.")
NO_ANSWER = "Nothing is known about the lights: use the switches."


@dataclass(frozen=True)
class LightsOffResult:
    """`answer` is the host's own word (`done`, `stop_sent`, `refused`) or the console's: `no_host`
    (nothing was sent) or `no_answer` (it was sent, or could not be, and no acceptable reply came)."""

    answer: str
    how: str | None = None
    run_id: str | None = None
    reason: str | None = None
    sources: list[dict[str, Any]] = field(default_factory=list)


def host_to_ask(spec: str | None, file: Any) -> tuple[Address | None, str | None]:
    """The address this server was given on its command line, and nothing it finds by itself."""
    if spec:
        try:
            return parse_host(spec), None
        except ValueError as e:
            return None, f"{e}. {NO_HOST}"
    if file is not None:
        addr, why = host_address(file)
        return addr, (f"{why}. {NO_HOST}" if addr is None else None)
    return None, NO_HOST


def _no_answer(why: str) -> LightsOffResult:
    return LightsOffResult("no_answer", reason=f"{why}. {NO_ANSWER}")


def lights_off(addr: Address, schemas: Schemas, *, reply_timeout_s: float | None = None) -> LightsOffResult:
    """Send the one line, once, and read the one reply line. Never raises."""
    wait = REPLY_TIMEOUT_S if reply_timeout_s is None else reply_timeout_s
    try:
        conn = socket.create_connection((addr.host, addr.port), timeout=CONNECT_TIMEOUT_S)
    except OSError as e:
        return _no_answer(f"the live-view host ({addr.host}:{addr.port}) did not answer: {e}")
    with conn:
        try:
            conn.sendall(LIGHTS_OFF_LINE)
            conn.shutdown(socket.SHUT_WR)
            conn.settimeout(wait)
            reply = b""
            while b"\n" not in reply and len(reply) <= MAX_REPLY_BYTES:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                reply += chunk
        except TimeoutError:
            return _no_answer(f"the live-view host did not answer within {wait:g} s; "
                              "the request was sent once and is not repeated")
        except OSError as e:
            return _no_answer(f"talking to the live-view host failed: {e}")
    if len(reply) > MAX_REPLY_BYTES:
        return _no_answer("the live-view host's reply was longer than any reply it may give")
    try:
        doc = json.loads(reply.decode("utf-8")) if reply.strip() else None
    except (UnicodeDecodeError, ValueError):
        doc = None
    if not isinstance(doc, dict):
        return _no_answer("the live-view host's reply was not one JSON object")
    try:
        problems = schemas.validate_def(doc, SCHEMA_FILE, REPLY_DEF)
    except SchemaError as e:
        return _no_answer(f"the reply could not be checked against its schema: {e}")
    if problems:
        return _no_answer("the live-view host's reply is not one its schema allows")
    answer = doc["lights_off"]
    if answer == "done":
        return LightsOffResult("done", how=doc["as"], run_id=doc["run_id"], sources=list(doc["sources"]))
    if answer == "stop_sent":
        return LightsOffResult("stop_sent", run_id=doc["run_id"], reason=doc["reason"])
    return LightsOffResult("refused", reason=doc["reason"])
