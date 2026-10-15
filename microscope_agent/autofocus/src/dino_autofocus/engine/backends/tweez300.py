"""Tweez300 (the vendor tweezers software) as `engine.tweezers.Tweezers`: a stub that REFUSES,
and will not be wired here.

Tweez300 stays running on the microscope PC and owns the tweezers hardware. The driver for it
already exists in soft-matter-agents, `microscope_agent/src/devices/python_tcp.py` (the GUI's TCP
text interface: a fixed set of wrapped verbs, `LASER_ON` deliberately not among them, pattern
files written by `write_pattern` as `.tpf` and loaded with `LOAD_PATTERN` /
`TRAP_ASSIGN_PATTERN`, a silence-is-never-retried rule because several commands are relative,
and `verification: none` on every dispatch because the device reports nothing back; its live
checklist is `microscope_agent/src/tweezers_live_checklist.md`). Under the merge decisions
(docs/integration-sma.md sections 7 and 9; docs/integration-sma-workplan.md P-01, D-05) that
driver is the only path to the real tweezers, moves happen only as soft-matter-agents plans the
person approves, and this stub is deleted once that path is in use on the bench. Until then
every call here refuses and nothing is opened, sent or imported, so the console cannot reach
the tweezers by accident; `bench=True` keeps `guards.TrapAxis` refusing while the stand's
bench-motion lock is on (T-036). `MockTweezers` is the console's demo device.

Known from the 2026-09 mock agent data: Tweez300GUI.exe / Tweez300GUIPython.exe /
Tweez300SystemManager.exe; positions in its own units; laser power set by hand; no position
feedback; limits per objective. The single-camera cfg notes Tweez300 may hold Kinetix_blue.
"""

from __future__ import annotations

from typing import Literal

from ..backend import require_token
from ..tweezers import TrapState, TweezersInfo

Transport = Literal["python", "tcp"]

NOT_WIRED = ("Tweez300 is not wired yet: its Python API / TCP command reference is not in "
             "(card T-20261002-2205). Nothing was sent.")


class Tweez300NotWired(RuntimeError):
    pass


class Tweez300Tweezers:
    def __init__(self, transport: Transport = "tcp", *, host: str = "127.0.0.1",
                 port: int | None = None, module: str | None = None) -> None:
        # stored only; no socket is opened and no module is imported
        self.transport, self.host, self.port, self.module = transport, host, port, module

    def info(self) -> TweezersInfo:
        return TweezersInfo("tweez300", 0, bench=True,
                            notes={"state": NOT_WIRED, "transport": self.transport})

    def traps(self) -> list[TrapState]:
        raise Tweez300NotWired(NOT_WIRED)

    def move_trap(self, index: int, x_um: float, y_um: float, z_um: float, *,
                  token: object) -> TrapState:
        require_token(token)
        raise Tweez300NotWired(NOT_WIRED)

    def set_trap(self, index: int, on: bool, *, token: object) -> TrapState:
        require_token(token)
        raise Tweez300NotWired(NOT_WIRED)

    def close(self) -> None:
        return None
