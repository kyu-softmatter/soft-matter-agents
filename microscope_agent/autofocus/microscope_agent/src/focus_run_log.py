# origin: dino-autofocus, public since 2026-10-03:
#   https://github.com/kyu-softmatter/dino-autofocus/blob/ab4978710228bb7f392a1f9050b95dfb10b42a92/microscope_agent/src/focus_run_log.py
# body-sha256: cb47d6d43e1d4695be71480afb945ff114a2cda103728c783631098d736a06c6
"""A focus verdict as one soft-matter-agents run-log event (integration-sma.md, P3).

The event follows `contracts/schemas/run_log.schema.json` `$defs/event` there: `t_mono` and
`time_base` are required, other keys are allowed. It carries no `params` (a verdict is not a
command, so it has no plan field to name in `from`) and no `channel` (nothing was sent).

Grades follow that repository's table (plan.md 5.3): a value read in this run (encoder z,
pixel statistics) is E1, a deterministic computation on them (a classical metric, a parabola
vertex) is E4. A model number has no grade there: it is E6, which may appear in no card, so
it goes under `signals` without a grade, as plan.md 13.1 item 2 describes (choice and
confidence as a signal). The chosen frame's z is the encoder readback, never a model value.

The SMA grade mapping is unmeasured provisional until the user rules on it at merge time
(workplan OD-17 may replace grades with sources; that is a later, separate change).

Contract (D-07; ``test_focus_contract.py`` pins it):

* ``to_run_log_event(verdict, t_mono, time_base="software")`` returns a JSON-native dict
  with exactly the keys ``EVENT_KEYS``: ``t_mono`` (float, the offset from the run's
  ``t0_mono``), ``time_base`` (one of ``TIME_BASES``), ``event`` (``EVENT``), ``choice``
  (one of the verdict vocabulary), ``source``, ``reason``, ``frame_index``, ``z`` (None or
  ``{value, unit: "um", grade: "E1", read_from: "z_drive"}`` -- the frame's encoder
  readback), ``evidence`` (``{name, value[, unit], grade}`` with grade E1 or E4) and
  ``signals`` (``{name, value[, unit]}`` with no grade: the model numbers).
* None of ``COMMAND_KEYS`` is ever present: a verdict is not a command, so it names no
  ``channel``, ``action``, ``params``, ``from``, ``verification`` or ``deletion``.
* Non-finite numbers become None; a non-finite ``t_mono`` or an unknown ``time_base``
  raises ``ValueError``. The text never contains the string ``E6``.
"""

from __future__ import annotations

import importlib.util
import math
import os
import sys
from typing import Any

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name: str, filename: str):
    """A sibling file by path, the soft-matter-agents idiom (no package, no relative import).
    A name already loaded is reused, so every importer shares one module object."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, os.path.join(_HERE, filename))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


_verdict = _load("_mic_focus_verdict", "focus_verdict.py")
Evidence = _verdict.Evidence
FocusVerdict = _verdict.FocusVerdict

EVENT = "focus_verdict"
TIME_BASES = ("software", "device", "trigger")  # the schema's enum
SMA_GRADE = {"measured": "E1", "computed": "E4"}  # "model" -> signals, no grade
#: The exact key set of an event, and the command fields a verdict event never carries.
EVENT_KEYS = ("t_mono", "time_base", "event", "choice", "source", "reason", "frame_index",
              "z", "evidence", "signals")
COMMAND_KEYS = ("params", "channel", "action", "from", "verification", "deletion")


def _value(v: Any) -> Any:
    return None if isinstance(v, float) and not math.isfinite(v) else v


def _entry(e: Evidence, with_grade: bool) -> dict[str, Any]:
    d: dict[str, Any] = {"name": e.name, "value": _value(e.value)}
    if e.unit:
        d["unit"] = e.unit
    if with_grade:
        d["grade"] = SMA_GRADE[e.grade]
    return d


def to_run_log_event(v: FocusVerdict, t_mono: float, *,
                     time_base: str = "software") -> dict[str, Any]:
    """`t_mono` is the offset from the run's `t0_mono`, in seconds. JSON-native result."""
    if time_base not in TIME_BASES:
        raise ValueError(f"time_base {time_base!r} not in {TIME_BASES}")
    if not math.isfinite(t_mono):
        raise ValueError(f"t_mono {t_mono!r} is not finite")
    ev: dict[str, Any] = {
        "t_mono": float(t_mono),
        "time_base": time_base,
        "event": EVENT,
        "choice": str(v.verdict),
        "source": v.source,
        "reason": v.reason,
        "frame_index": v.frame_index,
        "z": None if v.z_um is None else {
            "value": float(v.z_um), "unit": "um", "grade": "E1", "read_from": "z_drive"},
        "evidence": [_entry(e, True) for e in v.evidence if e.grade != "model"],
        "signals": [_entry(e, False) for e in v.evidence if e.grade == "model"],
    }
    return ev
