"""Plan drafts for the Instruments screens (console card 012; plan.md 4.5, 15.1).

A draft is an **ordinary plan card**: the shape `plan.schema.json` takes, checked against that schema read
from the tree, and nothing else. It is built here from what the person chose on the screen, **shown in full,
and saved nowhere**: where a console draft goes before the person signs it is still to be designed, and
this module writes no file. Console drafts have no goal, so the question number in a draft is a placeholder
(`mic-<UTC date>-900`).

* `trap_steps_card` is a goal-less `trap_steps` plan, a shape the schema holds: traps created at absolute
  positions and switched on, then a hold for the person.
* `piezo_card` is an `operation` plan: a step (and, if asked, the return step) or a host-timed sine on the fine
  piezo stage, the one thing a draft may command here that has both a software path and a schema shape.
* `part_card` composes what a change to the Aura LED, the transmitted lamp or the red camera's exposure
  would be. `plan.schema.json` has no operation that sets a light or an exposure, so such a card is
  checked and its refusal shown, not offered for signing; nothing is bent to make it pass.

Limits are not written here. The ranges a trap pattern is held to come from the person's safety file
(`instruments.tweezers_ranges`) and are passed in.
"""

from __future__ import annotations

import math
import re
from datetime import UTC, datetime
from typing import Any

PATTERNS = ("line", "circle", "grid")
OBJECTIVES = ("40x", "60x", "100x")
MAX_TRAPS = 64  # a screen-side sanity ceiling on what is composed; the instrument's own count limit does not exist yet
PIEZO_DEVICE = "piezo_stage"
PIEZO_STEP_ROLES = ("verify_mapping", "direction_finding", "approach", "return")
PIEZO_Z_ROLES = ("direction_finding", "return")  # until the piezo-Z direction is recorded (plan.schema.json)
PARTS = {
    "aura": {"device": "Aura", "label": "Aura III LED"},
    "dialamp": {"device": "DiaLamp", "label": "Transmitted lamp"},
    "camera_exposure": {"device": "Kinetix_red", "label": "Camera, red arm: exposure"},
}


class DraftError(ValueError):
    """What was asked cannot be drafted (the message says why)."""


def pattern_points(pattern: str, n: int, spacing_um: float) -> list[tuple[float, float]]:
    """Absolute trap positions in micrometres about the image centre."""
    if pattern not in PATTERNS:
        raise DraftError(f"pattern is one of {', '.join(PATTERNS)}")
    if not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= MAX_TRAPS:
        raise DraftError(f"the number of traps is a whole number from 1 to {MAX_TRAPS}")
    if not isinstance(spacing_um, (int, float)) or isinstance(spacing_um, bool) or not spacing_um > 0:
        raise DraftError("the spacing is a number of micrometres above zero")
    pts: list[tuple[float, float]] = []
    if pattern == "line":
        pts = [((i - (n - 1) / 2) * spacing_um, 0.0) for i in range(n)]
    elif pattern == "circle":
        radius = spacing_um if n == 1 else spacing_um / (2 * math.sin(math.pi / n))
        pts = [(radius * math.cos(2 * math.pi * i / n), radius * math.sin(2 * math.pi * i / n)) for i in range(n)]
    else:
        cols = math.ceil(math.sqrt(n))
        rows = math.ceil(n / cols)
        pts = [((i % cols - (cols - 1) / 2) * spacing_um, (i // cols - (rows - 1) / 2) * spacing_um) for i in range(n)]
    return [(round(x, 3) + 0.0, round(y, 3) + 0.0) for x, y in pts]


def _head(now: datetime, kind: str) -> dict[str, Any]:
    now = now.astimezone(UTC)
    qid = f"mic-{now.strftime('%Y%m%d')}-900"
    return {
        "card": "plan", "schema_version": "0.1", "id": f"plan-{qid}-{kind}-r1", "qid": qid, "thread": f"solo-{qid}",
        "round": 0, "revision": 1, "author": "human", "created_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "DRAFT", "numbers": [], "degraded": [],
    }


def trap_steps_card(*, pattern: str, objective: str, n: int, spacing_um: float, strength: float,
                    now: datetime) -> dict[str, Any]:
    """A goal-less trap_steps plan: create each trap at its absolute position and strength, switch each on,
    then hold for the person to say a bead is held."""
    if objective not in OBJECTIVES:
        raise DraftError(f"the objective is one of {', '.join(OBJECTIVES)}")
    if not isinstance(strength, (int, float)) or isinstance(strength, bool) or not 0 <= strength <= 1:
        raise DraftError("a trap's strength is a number from 0 to 1")
    pts = pattern_points(pattern, n, spacing_um)
    steps: list[dict[str, Any]] = []
    for i, (x, y) in enumerate(pts, 1):
        steps.append({"id": f"t{i}_create", "kind": "create", "trap": f"trap_{i}", "x_um": x, "y_um": y, "strength": float(strength)})
        steps.append({"id": f"t{i}_on", "kind": "on", "trap": f"trap_{i}"})
    steps.append({"id": "hold_bead", "kind": "hold_for_person",
                  "statement": "the person confirms a bead is held in the first trap"})
    card = _head(now, "traps")
    card.update({
        "purpose": "verify", "intent": "confirm",
        "actions": [{"id": s["id"], "device": "optical_tweezers", "action": s["kind"], "reversible": True,
                     "parameters": [], "tier": 1} for s in steps],
        "envelope_check": {"checked_against": [], "status": "unavailable",
                           "note": "The console does not check limits. The runtime checks every position and strength "
                                   "against the person's safety file before anything is sent."},
        "targets": [{"metric": "bead_held", "kind": "detection", "value": 1, "unit": "count",
                     "note": "the person's confirmation at the hold"}],
        "stop_criteria": [{"id": "sc_no_bead", "metric": "bead_held", "comparator": "<", "target": "bead_held",
                           "on_met": "fault", "statement": "stop if the person does not confirm a bead held"}],
        "success_criteria": [{"id": "ok_bead", "metric": "bead_held", "comparator": ">=", "target": "bead_held",
                              "statement": "the person confirms a bead held in the first trap"}],
        "open_risks": ["the tweezers are blind; only the person's confirmation or a frame says a bead is held"],
        "trap_steps": {
            "device": "optical_tweezers", "objective": objective, "read_back": "none",
            "verifies": f"That {n} trap(s) made in a {pattern} at {objective} hold a bead the person brings to them.",
            "falsified_by": "the person does not confirm a bead held, or the bead escapes once the stage stops",
            "steps": steps,
        },
        "pre_stop_buffer": {"length_s": 10},
    })
    return card


def trap_range_problems(card: dict[str, Any], ranges: dict[str, Any]) -> list[str]:
    """Why a trap pattern is outside the person's safety file, in words; empty when every position and
    strength is inside. A limit the file does not hold is a refusal (a missing limit refuses)."""
    ts = card["trap_steps"]
    objective = ts["objective"]
    span = ranges.get("positions", {}).get(objective)
    problems: list[str] = []
    if span is None:
        problems.append(f"Your safety file has no trap position range for {objective}, so every position is refused.")
    strength = ranges.get("strength")
    if strength is None:
        problems.append("Your safety file has no trap strength range, so every strength is refused.")
    for s in ts["steps"]:
        if s["kind"] != "create":
            continue
        if span is not None:
            lo, hi = span["min"]["value"], span["max"]["value"]
            for axis in ("x_um", "y_um"):
                if not lo <= s[axis] <= hi:
                    problems.append(f"{s['trap']} at {axis[0]} = {s[axis]} um is outside {lo} to {hi} um at {objective} (from your safety file).")
        if strength is not None and not strength["min"]["value"] <= s["strength"] <= strength["max"]["value"]:
            problems.append(f"{s['trap']} strength {s['strength']} is outside {strength['min']['value']} to {strength['max']['value']} (from your safety file).")
    return problems


def part_card(*, part: str, fields: dict[str, Any], now: datetime) -> dict[str, Any]:
    """What a change to one of the three parts software may command would be, as a plan card. The schema
    cannot say it (see the module note), so this card is checked and its refusal is shown."""
    if part not in PARTS:
        raise DraftError(f"software may command only: {', '.join(PARTS)}")
    device = PARTS[part]["device"]
    numbers: list[dict[str, Any]] = []
    params: list[str] = []

    def number(name: str, value: Any, unit: str, low: float | None = None, high: float | None = None) -> None:
        if not isinstance(value, (int, float)) or isinstance(value, bool) or (low is not None and value < low) or (
                high is not None and value > high):
            raise DraftError(f"{name} is a number" + (f" from {low} to {high}" if low is not None and high is not None else " above zero"))
        numbers.append({"name": name, "value": value, "unit": unit, "source": "assumed:the_persons_choice",
                        "grade": "E5", "precision": "order_of_magnitude"})
        params.append(name)

    if part == "aura":
        if not isinstance(fields.get("color"), str) or not fields["color"].strip():
            raise DraftError("the Aura LED's colour is a name")
        number("power", fields.get("power_mw"), "mW", 1e-9, 1e9)
        action = f"set_{fields['color'].strip().lower().replace(' ', '_')}"
    elif part == "dialamp":
        if fields.get("state") not in ("on", "off"):
            raise DraftError("the lamp's state is on or off")
        number("intensity", fields.get("intensity_percent"), "percent", 0, 100)
        action = f"state_{fields['state']}_and_intensity"
    else:
        number("exposure", fields.get("exposure_ms"), "ms", 1e-9, 1e9)
        action = "set_exposure"
    card = _head(now, part)
    card.update({
        "numbers": numbers, "purpose": "verify", "intent": "confirm",
        "actions": [{"id": f"set_{part}", "device": device, "action": action, "reversible": True,
                     "parameters": params, "tier": 1}],
        "envelope_check": {"checked_against": [], "status": "unavailable",
                           "note": "No limit has been named for this part yet, so the instrument refuses it."},
        "stop_criteria": [], "success_criteria": [], "open_risks": [],
    })
    return card


#: What each part's quantity is called when it is refused. **No limit has been named for any of them**: which limit
#: in the person's safety file would cover the Aura's power, the lamp's intensity or the red camera's exposure is the
#: runtime's and the safety schema's to say, so nothing here names one, reads one or treats another quantity's limit as
#: covering it. Until that is said, every part draft is refused before signing.
PART_WORDS = {
    "aura": "the Aura LED's power",
    "dialamp": "the transmitted lamp's intensity",
    "camera_exposure": "the red camera's exposure",
}
SELECTOR_ELEMENT = re.compile(r"^[a-z][a-z0-9_]*$")


def part_refusals(parts: list[dict[str, Any]]) -> list[str]:
    """Why the parts of a changes draft may not be signed, in words: one line for each quantity touched, in the order
    added. Nothing is read from the safety file and no value is compared, so no value can pass."""
    return [f"No limit has been named for {PART_WORDS[p['kind']]} yet, so this draft cannot be signed." for p in parts]


def changes_card(*, parts: list[dict[str, Any]], selectors: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    """The clicks of the Instruments drawing, collected into **one** ordinary plan card: each part software may
    command contributes its action and its numbers, each slot chosen by hand becomes a selector under
    `system_configuration`. The schema decides whether that is a plan; nothing here bends it to pass."""
    if not parts and not selectors:
        raise DraftError("nothing has been added to the changes")
    kinds = [p.get("kind") for p in parts]
    if len(set(kinds)) != len(kinds):
        raise DraftError("each part is in the changes once")
    cards = [part_card(part=p["kind"], fields=p, now=now) for p in parts]
    seen: set[str] = set()
    chosen: list[dict[str, Any]] = []
    for s in selectors:
        element, value = s.get("element"), s.get("value")
        if not isinstance(element, str) or not SELECTOR_ELEMENT.match(element):
            raise DraftError("a required state names its element in lower case letters, digits and underscores")
        if not isinstance(value, str) or not value.strip():
            raise DraftError("a required state names the slot it asks for")
        if element in seen:
            raise DraftError(f"{element} has two required states in the changes")
        seen.add(element)
        one: dict[str, Any] = {"element": element, "value": value}
        if isinstance(s.get("note"), str) and s["note"].strip():
            one["note"] = s["note"].strip()
        chosen.append(one)
    card = _head(now, "changes")
    devices = [PARTS[p["kind"]]["device"] for p in parts]
    config: dict[str, Any] = {"config": "console_draft", "devices": devices}
    if chosen:
        config["selectors"] = chosen
    card.update({
        "numbers": [n for c in cards for n in c["numbers"]], "purpose": "verify", "intent": "confirm",
        "actions": [a for c in cards for a in c["actions"]],
        "system_configuration": config,
        "envelope_check": {"checked_against": [], "status": "unavailable",
                           "note": "The console does not check limits. No limit has been named for these quantities yet, so every draft of them is refused before signing."},
        "stop_criteria": [], "success_criteria": [], "open_risks": [],
    })
    return card


def _plain(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def piezo_card(*, fields: dict[str, Any], now: datetime) -> dict[str, Any]:
    """An `operation` plan for the fine piezo stage: one step on x, y or z (with its return step if
    `return_um` is given), or a host-timed sine on x or y behind the approach step the schema asks for.
    Positions are absolute, in um. The read-back tolerance is the person's number and is never defaulted."""
    axis, move = fields.get("axis"), fields.get("move")
    if axis not in ("x", "y", "z"):
        raise DraftError("the axis is x, y or z")
    if move not in ("step", "sine"):
        raise DraftError("the move is a step or a sine")
    tol = fields.get("tolerance_um")
    if not _plain(tol) or not tol > 0:
        raise DraftError("the read-back tolerance is a number of micrometres above zero, and it is yours to say")
    moves: list[dict[str, Any]] = []
    if move == "step":
        role = fields.get("role") or "verify_mapping"
        if role not in PIEZO_STEP_ROLES:
            raise DraftError(f"the role of a step is one of {', '.join(PIEZO_STEP_ROLES)}")
        if axis == "z" and role not in PIEZO_Z_ROLES:
            raise DraftError("a step on z has the role direction_finding or return until the piezo-Z direction is recorded")
        if not _plain(fields.get("target_um")):
            raise DraftError("the target is a number of micrometres")
        moves.append({"id": f"step_{axis}_out", "axis": axis, "kind": "step", "target_um": fields["target_um"], "role": role})
        if fields.get("return_um") is not None:
            if not _plain(fields["return_um"]):
                raise DraftError("the position to return to is a number of micrometres")
            moves.append({"id": f"step_{axis}_back", "axis": axis, "kind": "step", "target_um": fields["return_um"], "role": "return"})
    else:
        if axis == "z":
            raise DraftError("a sine is on x or y only: z never takes periodic motion under an operation plan")
        for name in ("centre_um", "amplitude_um", "period_s"):
            if not _plain(fields.get(name)):
                raise DraftError(f"{name} is a number")
        if not fields["amplitude_um"] > 0 or not fields["period_s"] > 0:
            raise DraftError("the amplitude and the period are above zero")
        cycles, ppp = fields.get("cycles"), fields.get("points_per_period")
        if not isinstance(cycles, int) or isinstance(cycles, bool) or cycles < 1:
            raise DraftError("the number of cycles is a whole number, at least 1")
        if not isinstance(ppp, int) or isinstance(ppp, bool) or ppp < 4:
            raise DraftError("points per period is a whole number, at least 4")
        start = fields.get("start") or "centre"
        if start not in ("centre", "minimum", "maximum"):
            raise DraftError("the sine starts at its centre, minimum or maximum")
        first = fields["centre_um"] + {"centre": 0.0, "minimum": -fields["amplitude_um"], "maximum": fields["amplitude_um"]}[start]
        moves.append({"id": f"approach_{axis}", "axis": axis, "kind": "step", "target_um": round(first, 6) + 0.0, "role": "approach"})
        moves.append({"id": f"sine_{axis}", "axis": axis, "kind": "sine", "centre_um": fields["centre_um"],
                      "amplitude_um": fields["amplitude_um"], "period_s": fields["period_s"], "cycles": cycles,
                      "points_per_period": ppp, "host_timed": True, "start": start})
    card = _head(now, "piezo")
    what = (f"That the piezo stage moves along {axis} to the {'position' if move == 'step' else 'positions'} asked for "
            f"and reads back within {tol} um.")
    card.update({
        "purpose": "verify", "intent": "confirm",
        "operation": {
            "device": PIEZO_DEVICE, "verifies": what,
            "falsified_by": "the read-back after a move differs from its target by more than the tolerance, or the image does not move along the axis",
            "read_back": "before_and_after_each_move", "moves": moves,
        },
        "actions": [{"id": m["id"], "device": PIEZO_DEVICE, "action": "move_absolute" if m["kind"] == "step" else "sine_positions",
                     "reversible": True, "parameters": [], "tier": 1} for m in moves],
        "envelope_check": {"checked_against": [f"piezo_{axis}_position_min", f"piezo_{axis}_position_max"], "status": "unavailable",
                           "note": "The console does not check limits. The runtime checks every position against the person's safety file before anything is sent."},
        "targets": [{"metric": "position_readback_error", "kind": "uncertainty", "value": tol, "unit": "um",
                     "note": "the person's choice for this operation"}],
        "stop_criteria": [{"id": "sc_readback", "metric": "position_readback_error", "comparator": ">", "target": "position_readback_error",
                           "on_met": "fault", "statement": "stop if a read-back after a move differs from its target by more than the tolerance"}],
        "success_criteria": [{"id": "ok_readback", "metric": "position_readback_error", "comparator": "<=", "target": "position_readback_error",
                              "statement": "each move read back within the tolerance"}],
        "open_risks": ["the piezo-Z direction is unmeasured" if axis == "z" else "the piezo-Z direction is unmeasured; this plan commands no Z"],
        "pre_stop_buffer": {"length_s": 10},
    })
    return card


def piezo_range_problems(card: dict[str, Any], ranges: dict[str, Any]) -> list[str]:
    """Why the positions of a piezo draft are outside the person's range, in words (a missing range refuses)."""
    op = card["operation"]
    axis = op["moves"][0]["axis"]
    span = ranges.get(axis)
    if span is None:
        return [f"Your safety file has no piezo range for {axis}, so every position on it is refused."]
    lo, hi = span["min"]["value"], span["max"]["value"]
    problems: list[str] = []
    for m in op["moves"]:
        pts = [m["target_um"]] if m["kind"] == "step" else [m["centre_um"] - m["amplitude_um"], m["centre_um"] + m["amplitude_um"]]
        for p in pts:
            if not lo <= p <= hi:
                problems.append(f"{m['id']}: {axis} = {p} um is outside {lo} to {hi} um (from your safety file).")
    return problems
