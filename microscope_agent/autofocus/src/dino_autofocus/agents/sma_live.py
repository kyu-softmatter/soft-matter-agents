"""Switch a soft-matter-agents live view on from the console (its card 062, plan.md 11-25).

The person decided on 2026-10-07 that a live camera view is switched on and off from the
console, outside a plan too, because it helps find the sample. On the soft-matter-agents side
a live view is an ordinary preparatory run: the person starts a live-view host, and the host
runs a live-view command list the person wrote and approved in `<seat>_agent/approvals/`.
The console can only name such a list by its sha256. It cannot send a list, a path or a value.

What this module speaks (proposed by the console, adopted unchanged in card 062 at
soft-matter-agents 032e556; the list's shape is contracts/schemas/live_view_list.schema.json
at 48242a2):

- The host's address is `%LOCALAPPDATA%\\soft-matter-agents\\live_host.json`, outside the
  soft-matter-agents tree, written atomically by the host while it runs and deleted when it
  stops: `{"host": "127.0.0.1", "port": N, "pid": P, "started_at": "<iso>"}`. Only 127.0.0.1
  is accepted. A missing file or a port that does not answer means the host is not running
  (a file left by a crash reads that way). `--live-host 127.0.0.1:N` is the manual fallback.
- A list is a JSON file in `<seat>_agent/approvals/` with `"artifact": "live_view_list"`
  (an artifact, not a card: no qid, identified by its bytes). Its sha256 is of the raw file
  bytes. The console shows the person's values (label, lamp intensity, exposure, frame
  ceiling, any excitation block) and sends only the sha256; the host checks the list itself.
- "Live on": exactly one line, `{"live_on": "<sha256>"}`. Reply, one line:
  `{"live_on": "started", "run_id": "<id>"}`, sent once `run_started` is in that run's
  events.jsonl, or `{"live_on": "refused", "reason": "<text>"}` (the host records every
  refusal). `reason` is for the person and never branched on. A close with no reply means the
  host died mid-request: shown as refused, no reason.
- The run is then followed like any run (`sma_run`), and "Live off" is that run's own stop
  channel (`sma_run.send_stop`). There is no other way to stop it. It also ends by itself at
  the frame ceiling the person wrote in the list, so a forgotten live view stops.

Nothing here opens a camera or a device, or writes in the soft-matter-agents tree.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .sma_run import CONNECT_TIMEOUT_S, Address

HOST_FILE_ENV = "DINO_AF_SMA_LIVE_HOST_FILE"
LIST_MARKER = ("artifact", "live_view_list")
MAX_LIST_BYTES = 200_000
REPLY_TIMEOUT_S = 15.0  # the host starts the run (and the camera) before it answers
_SHA256 = set("0123456789abcdef")


class LiveError(Exception):
    """The live-view host could not be reached or did not answer as agreed."""


def default_host_file() -> Path:
    """`$DINO_AF_SMA_LIVE_HOST_FILE`, else `%LOCALAPPDATA%\\soft-matter-agents\\live_host.json`."""
    env = os.environ.get(HOST_FILE_ENV)
    if env:
        return Path(env)
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "soft-matter-agents" / "live_host.json"


def parse_host(value: str) -> Address:
    """`--live-host 127.0.0.1:N` -> Address; anything else raises ValueError."""
    host, _, port = value.rpartition(":")
    addr = Address.parse({"host": host, "port": int(port) if port.isdigit() else None})
    if addr is None:
        raise ValueError(f"--live-host must be 127.0.0.1:<port>, got {value!r}")
    return addr


def host_address(path: str | os.PathLike[str] | None = None) -> tuple[Address | None, str | None]:
    """The host's announced address, or (None, why not) in words."""
    p = Path(path) if path is not None else default_host_file()
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return None, f"the live-view host is not running (no {p})"
    except (OSError, UnicodeDecodeError, ValueError):
        return None, f"the live-view host's address file {p} is unreadable"
    addr = Address.parse(data if isinstance(data, dict) else None)
    if addr is None:
        return None, f"the live-view host's address in {p} is not 127.0.0.1 and a port"
    return addr, None


@dataclass(frozen=True)
class LiveList:
    """A live-view command list the person approved, as a file in `<seat>_agent/approvals/`."""

    name: str
    sha256: str  # of the file's bytes, the value the console names
    data: Any  # the list as the person wrote it, untouched


def is_sha256(value: str) -> bool:
    return len(value) == 64 and set(value) <= _SHA256


def live_lists(sma_root: str | os.PathLike[str], seat: str = "microscope") -> list[LiveList]:
    """Every JSON file in `<seat>_agent/approvals/` marked `"artifact": "live_view_list"`."""
    from .sma_files import long_path

    base = long_path(Path(sma_root) / f"{seat}_agent" / "approvals")
    if not base.is_dir():
        return []
    out = []
    for p in sorted(base.iterdir()):
        if p.is_dir() or p.suffix != ".json":
            continue
        try:
            if p.stat().st_size > MAX_LIST_BYTES:
                continue
            raw = p.read_bytes()
            data = json.loads(raw.decode("utf-8-sig"))
        except (OSError, UnicodeDecodeError, ValueError):
            continue
        if isinstance(data, dict) and data.get(LIST_MARKER[0]) == LIST_MARKER[1]:
            out.append(LiveList(p.name, hashlib.sha256(raw).hexdigest(), data))
    return out


@dataclass(frozen=True)
class LiveOnResult:
    """`started` with the run id, or `refused` with the host's reason (None: no reason given)."""

    outcome: str
    run_id: str | None
    reason: str | None


def live_on(addr: Address, sha256: str, *,
            reply_timeout_s: float = REPLY_TIMEOUT_S) -> LiveOnResult:
    """Ask the host to start the approved list named by `sha256`. Only a person calls this."""
    if not is_sha256(sha256):
        raise ValueError("a live-view list is named by its sha256: 64 lowercase hex characters")
    line = json.dumps({"live_on": sha256}).encode() + b"\n"
    try:
        conn = socket.create_connection((addr.host, addr.port), timeout=CONNECT_TIMEOUT_S)
    except OSError as e:
        raise LiveError(f"the live-view host ({addr.host}:{addr.port}) did not answer: {e}") from e
    with conn:
        try:
            conn.sendall(line)
            conn.shutdown(socket.SHUT_WR)
            conn.settimeout(reply_timeout_s)
            reply = b""
            while b"\n" not in reply and len(reply) < 4096:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                reply += chunk
        except TimeoutError as e:
            raise LiveError(f"the live-view host did not answer within {reply_timeout_s:g} s; "
                            "look at Runs for a new run before pressing again") from e
        except OSError as e:
            raise LiveError(f"talking to the live-view host failed: {e}") from e
    try:
        answer = json.loads(reply.decode("utf-8")) if reply.strip() else None
    except (UnicodeDecodeError, ValueError):
        answer = None
    if not isinstance(answer, dict):
        return LiveOnResult("refused", None, None)
    run_id = answer.get("run_id")
    if answer.get("live_on") == "started" and isinstance(run_id, str) and run_id:
        return LiveOnResult("started", run_id, None)
    reason = answer.get("reason")
    return LiveOnResult("refused", None, reason if isinstance(reason, str) else None)
