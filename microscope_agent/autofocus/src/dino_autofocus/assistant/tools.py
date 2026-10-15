"""The tools Claude may call, in one place.

Two kinds, told apart by `ToolSpec.kind`:

- **read** tools run at once and return text: hardware state (`EngineAPI.snapshot`), agent
  questions, runs and inbox (AgentStore, T-008), sample records and maps, simulation status
  (T-012). A source that is not wired in yet answers from a placeholder marked
  `"source": "fake"`, and its spec has `stub=True`.
- **action** tools never touch the engine. Their handler only drafts an engine command; the
  runner turns the draft into a `Proposal` that waits for a person (PLAN.md 6절 11항). The
  card shows a description written here from the arguments, the model's stated reason
  labelled as such, and the gate verdict the engine's own gate code expects. The engine checks
  gates and guards again when the confirmed command arrives.

The data policy (D7) is applied here too: `prompt_only` offers no read tools, `text` sends
read results as JSON text with any image data cut out and counted, and `images` cannot be
switched on (`IMAGES_PERMITTED`).
"""

from __future__ import annotations

import copy
import dataclasses
import json
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

DATA_POLICIES = ("prompt_only", "text", "images")
# D7 (PLAN.md 7절): text only. Turning images on needs the user's separate permission and a
# task that changes this constant; no tool sends frames or map pictures before that.
IMAGES_PERMITTED = False

MAX_RESULT_CHARS = 20_000
REMOVED_IMAGE = "[image removed: data policy 'text']"

AGENTS = ("microscope", "simulation")


class ToolInputError(ValueError):
    """The model's tool input does not match the tool's schema."""


@dataclass
class Sources:
    """What the read tools read and what the action tools ask about. None = not wired yet.

    `snapshot` is `EngineAPI.snapshot`; `store` is an AgentStore; `samples` has
    `get_sample(sample_id)` and `get_map(sample_id)`; `simulations` has `list_runs()` and
    `get_status(run_id)`; `gates(op, args)` returns `(enabled, reasons)` from the engine's gate
    code (WP-G). None of them may move hardware.
    """

    snapshot: Callable[[], dict] | None = None
    store: Any = None
    samples: Any = None
    simulations: Any = None
    gates: Callable[[str, dict], tuple[bool, list[str]]] | None = None


@dataclass(frozen=True)
class ToolSpec:
    name: str
    kind: Literal["read", "action"]
    description: str
    input_schema: dict
    handler: Callable[[Sources, dict], Any]
    stub: bool = False  # answers from a placeholder until the real source lands

    def definition(self) -> dict:
        """What the provider sends: name, description, strict schema. Nothing else.

        `strict: true` makes the API keep arguments schema-valid (forced `tool_choice` is a
        400 on claude-opus-5-5, so this is the guarantee). Strict schemas take no numeric
        limits, so the sent schema carries them as text; `validate` still checks the full
        `input_schema` before anything runs.
        """
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": strict_schema(self.input_schema),
            "strict": True,
        }


_NUMERIC_LIMITS = (("minimum", ">="), ("maximum", "<="), ("exclusiveMinimum", ">"))


def strict_schema(schema: dict) -> dict:
    """`schema` without the keywords strict tool use rejects, each limit moved into the
    property's description."""
    props = {}
    for name, p in schema.get("properties", {}).items():
        q = {k: v for k, v in p.items() if k not in dict(_NUMERIC_LIMITS)}
        limits = [f"{op} {p[k]:g}" for k, op in _NUMERIC_LIMITS if k in p]
        if limits:
            text = "Must be " + " and ".join(limits) + "."
            q["description"] = f"{q['description']} {text}" if "description" in q else text
        props[name] = q
    return {**schema, "properties": props}


@dataclass
class ToolOutcome:
    """One tool call. `content` is the text the model gets back."""

    name: str
    kind: str  # "read" | "action" | "error"
    content: str
    is_error: bool = False
    images_removed: int = 0
    truncated: bool = False
    draft: dict | None = None  # action tools: the engine command draft


# --------------------------------------------------------------------------- placeholders

_FAKE_SNAPSHOT = {
    "source": "fake",
    "note": "engine not connected; placeholder values",
    "position": {"x_um": 0.0, "y_um": 0.0, "z_um": 2950.0},
    "lights": {"aura": "off", "dialamp": "off"},
    "objective": "4x",
    "running": None,
}

_FAKE_QUESTIONS = [
    {
        "qid": "mic-20260925-001",
        "agent": "microscope",
        "title": "(placeholder) tracer diffusivity",
        "status": "open",
    }
]


def _fake_sample(sample_id: str) -> dict:
    return {"source": "fake", "sample_id": sample_id, "note": "sample records not connected"}


def _fake_map(sample_id: str) -> dict:
    return {"source": "fake", "sample_id": sample_id, "tiles": 0, "flags": []}


_FAKE_SIMULATIONS = [
    {
        "source": "fake",
        "run_id": "run-fake-001",
        "state": "running",
        "step": 1200,
        "total_steps": 10000,
    }
]


# --------------------------------------------------------------------------- read handlers


def _hardware_state(src: Sources, _inp: dict) -> Any:
    return dict(_FAKE_SNAPSHOT) if src.snapshot is None else src.snapshot()


def _list_questions(src: Sources, inp: dict) -> Any:
    if src.store is None:
        return [q for q in _FAKE_QUESTIONS if q["agent"] == inp["agent"]]
    return src.store.list_questions(inp["agent"])


def _get_question(src: Sources, inp: dict) -> Any:
    if src.store is None:
        return {"source": "fake", "qid": inp["qid"], "note": "agent store not connected"}
    return src.store.get_question(inp["qid"], inp.get("version"))


def _list_runs(src: Sources, inp: dict) -> Any:
    if src.store is None:
        return []
    return src.store.list_runs(inp["agent"])


def _get_run(src: Sources, inp: dict) -> Any:
    if src.store is None:
        return {"source": "fake", "run_id": inp["run_id"], "note": "agent store not connected"}
    return src.store.get_run(inp["agent"], inp["run_id"])


def _list_inbox(src: Sources, _inp: dict) -> Any:
    return [] if src.store is None else src.store.list_inbox()


def _get_sample(src: Sources, inp: dict) -> Any:
    if src.samples is None:
        return _fake_sample(inp["sample_id"])
    return src.samples.get_sample(inp["sample_id"])


def _get_sample_map(src: Sources, inp: dict) -> Any:
    if src.samples is None:
        return _fake_map(inp["sample_id"])
    return src.samples.get_map(inp["sample_id"])


def _list_simulations(src: Sources, _inp: dict) -> Any:
    return (
        [dict(r) for r in _FAKE_SIMULATIONS]
        if src.simulations is None
        else (src.simulations.list_runs())
    )


def _simulation_status(src: Sources, inp: dict) -> Any:
    if src.simulations is None:
        return {"source": "fake", "run_id": inp["run_id"], "state": "unknown"}
    return src.simulations.get_status(inp["run_id"])


# --------------------------------------------------------------------------- action drafts
# Each returns {"command": <engine Command fields>, "summary": <text written here>}.
# Operation and argument names follow docs/operations-spec.md (T-006).


def _num(x: float) -> str:
    return f"{x:g}"


def _draft_goto_xy(_src: Sources, inp: dict) -> dict:
    args = {"x_um": inp["x_um"], "y_um": inp["y_um"], "sample_id": inp["sample_id"]}
    return {
        "command": {"kind": "start", "op": "goto_xy", "args": args},
        "summary": (
            f"Move the stage to x={_num(inp['x_um'])} um, y={_num(inp['y_um'])} um on sample "
            f"{inp['sample_id']}. The engine retracts Z first when the move is large."
        ),
    }


def _draft_lights_off(_src: Sources, _inp: dict) -> dict:
    return {
        "command": {"kind": "lights_off", "op": "", "args": {}},
        "summary": "Switch all lights off (Aura and DiaLamp). Stops a running operation.",
    }


def _draft_objective_change(_src: Sources, inp: dict) -> dict:
    args: dict[str, Any] = {"target_state": inp["target_state"], "escape": inp["escape"]}
    if "escape_dy_um" in inp:
        args["escape_dy_um"] = inp["escape_dy_um"]
    how = "with the Y step-out" if inp["escape"] else "without stepping out in Y"
    return {
        "command": {"kind": "start", "op": "objective_change", "args": args},
        "summary": f"Change the objective to nosepiece state {inp['target_state']} {how}.",
    }


def _draft_scan_4x(_src: Sources, inp: dict) -> dict:
    args: dict[str, Any] = {"sample_id": inp["sample_id"]}
    for k in ("margin_um", "overlap", "dry_run"):
        if k in inp:
            args[k] = inp[k]
    dry = " (dry run: plan only)" if inp.get("dry_run") else ""
    return {
        "command": {"kind": "start", "op": "scan_4x", "args": args},
        "summary": f"Start the 4x scan of sample {inp['sample_id']}{dry}.",
    }


def _draft_focus_100x(_src: Sources, inp: dict) -> dict:
    args: dict[str, Any] = {"sample_id": inp["sample_id"]}
    for k in ("centre_um", "half_um"):
        if k in inp:
            args[k] = inp[k]
    return {
        "command": {"kind": "start", "op": "focus_100x", "args": args},
        "summary": f"Run the 100x focus sweep on sample {inp['sample_id']}.",
    }


def _draft_map_flag(_src: Sources, inp: dict) -> dict:
    args = {k: inp[k] for k in ("sample_id", "x_um", "y_um", "name") if k in inp}
    args["note"] = inp.get("note", "")
    return {
        "command": {"kind": "start", "op": "map_flag", "args": args},
        "summary": (
            f"Add the flag {inp['name']!r} at x={_num(inp['x_um'])} um, y={_num(inp['y_um'])} um "
            f"on the map of sample {inp['sample_id']}. Nothing moves."
        ),
    }


# --------------------------------------------------------------------------- specs


def _obj(props: dict, required: list[str]) -> dict:
    return {
        "type": "object",
        "properties": props,
        "required": required,
        "additionalProperties": False,
    }


_AGENT = {"type": "string", "enum": list(AGENTS)}
_SAMPLE = {"type": "string", "description": "Sample id, e.g. 20260930_1849_1"}
_REASON = {"type": "string", "description": "Why you propose this, shown to the person"}

_ACTION_NOTE = (
    " Nothing moves: this creates a proposal card that a person must confirm on screen, "
    "and the engine's gates and guards still apply after confirmation."
)

TOOL_SPECS: tuple[ToolSpec, ...] = (
    ToolSpec(
        "get_hardware_state",
        "read",
        "Current hardware state from the engine: stage position, lights, objective, "
        "running operation.",
        _obj({}, []),
        _hardware_state,
    ),
    ToolSpec(
        "list_questions",
        "read",
        "Questions of one soft-matter-agents seat, newest first.",
        _obj({"agent": _AGENT}, ["agent"]),
        _list_questions,
    ),
    ToolSpec(
        "get_question",
        "read",
        "The cards (goal, axes, plan, synthesis, refusals, results) of one question.",
        _obj(
            {"qid": {"type": "string"}, "version": {"type": "integer", "minimum": 1}},
            ["qid"],
        ),
        _get_question,
    ),
    ToolSpec(
        "list_runs",
        "read",
        "Runs of one seat, newest first.",
        _obj({"agent": _AGENT}, ["agent"]),
        _list_runs,
    ),
    ToolSpec(
        "get_run",
        "read",
        "The record files of one run.",
        _obj({"agent": _AGENT, "run_id": {"type": "string"}}, ["agent", "run_id"]),
        _get_run,
    ),
    ToolSpec(
        "list_inbox",
        "read",
        "Bridge threads between the seats and the messages on them.",
        _obj({}, []),
        _list_inbox,
    ),
    ToolSpec(
        "get_sample",
        "read",
        "A sample's record: geometry, hole fit, visits.",
        _obj({"sample_id": _SAMPLE}, ["sample_id"]),
        _get_sample,
        stub=True,
    ),
    ToolSpec(
        "get_sample_map",
        "read",
        "A sample map as data: tiles, particle candidates, flags. No pictures.",
        _obj({"sample_id": _SAMPLE}, ["sample_id"]),
        _get_sample_map,
        stub=True,
    ),
    ToolSpec(
        "list_simulations",
        "read",
        "Simulation runs and their progress.",
        _obj({}, []),
        _list_simulations,
        stub=True,
    ),
    ToolSpec(
        "get_simulation_status",
        "read",
        "Progress and latest log values of one simulation run.",
        _obj({"run_id": {"type": "string"}}, ["run_id"]),
        _simulation_status,
        stub=True,
    ),
    ToolSpec(
        "propose_goto_xy",
        "action",
        "Propose moving the stage to an XY position on a sample." + _ACTION_NOTE,
        _obj(
            {
                "x_um": {"type": "number"},
                "y_um": {"type": "number"},
                "sample_id": _SAMPLE,
                "reason": _REASON,
            },
            ["x_um", "y_um", "sample_id", "reason"],
        ),
        _draft_goto_xy,
    ),
    ToolSpec(
        "propose_lights_off",
        "action",
        "Propose switching all lights off." + _ACTION_NOTE,
        _obj({"reason": _REASON}, ["reason"]),
        _draft_lights_off,
    ),
    ToolSpec(
        "propose_objective_change",
        "action",
        "Propose changing the objective (nosepiece state)." + _ACTION_NOTE,
        _obj(
            {
                "target_state": {"type": "integer", "minimum": 0},
                "escape": {"type": "boolean", "description": "Step out in Y for immersion"},
                "escape_dy_um": {"type": "number"},
                "reason": _REASON,
            },
            ["target_state", "escape", "reason"],
        ),
        _draft_objective_change,
    ),
    ToolSpec(
        "propose_scan_4x",
        "action",
        "Propose starting the 4x scan of a sample." + _ACTION_NOTE,
        _obj(
            {
                "sample_id": _SAMPLE,
                "margin_um": {"type": "number", "minimum": 0},
                "overlap": {"type": "number", "minimum": 0, "maximum": 0.9},
                "dry_run": {"type": "boolean"},
                "reason": _REASON,
            },
            ["sample_id", "reason"],
        ),
        _draft_scan_4x,
    ),
    ToolSpec(
        "propose_focus_100x",
        "action",
        "Propose the 100x focus sweep on a sample." + _ACTION_NOTE,
        _obj(
            {
                "sample_id": _SAMPLE,
                "centre_um": {"type": "number"},
                "half_um": {"type": "number", "exclusiveMinimum": 0},
                "reason": _REASON,
            },
            ["sample_id", "reason"],
        ),
        _draft_focus_100x,
    ),
    ToolSpec(
        "propose_map_flag",
        "action",
        "Propose adding a named flag at an XY position on a sample map. Only the operator on "
        "the microscope PC can confirm it." + _ACTION_NOTE,
        _obj(
            {
                "sample_id": _SAMPLE,
                "x_um": {"type": "number"},
                "y_um": {"type": "number"},
                "name": {"type": "string"},
                "note": {"type": "string"},
                "reason": _REASON,
            },
            ["sample_id", "x_um", "y_um", "name", "reason"],
        ),
        _draft_map_flag,
    ),
)


# --------------------------------------------------------------------------- validation

_TYPES: dict[str, Callable[[Any], bool]] = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, int | float) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
}


def validate(schema: dict, value: Any) -> list[str]:
    """The subset of JSON Schema the specs above use. Model input is untrusted, and with
    eager input streaming the API no longer validates it, so every call is checked here."""
    if not isinstance(value, dict):
        return ["input must be an object"]
    errors = []
    props = schema.get("properties", {})
    for k in schema.get("required", []):
        if k not in value:
            errors.append(f"missing {k!r}")
    for k, v in value.items():
        p = props.get(k)
        if p is None:
            errors.append(f"unknown field {k!r}")
            continue
        if not _TYPES[p["type"]](v):
            errors.append(f"{k!r} must be {p['type']}")
            continue
        if "enum" in p and v not in p["enum"]:
            errors.append(f"{k!r} must be one of {p['enum']}")
        if "minimum" in p and v < p["minimum"]:
            errors.append(f"{k!r} must be >= {p['minimum']}")
        if "maximum" in p and v > p["maximum"]:
            errors.append(f"{k!r} must be <= {p['maximum']}")
        if "exclusiveMinimum" in p and v <= p["exclusiveMinimum"]:
            errors.append(f"{k!r} must be > {p['exclusiveMinimum']}")
    return errors


# --------------------------------------------------------------------------- data policy


def check_policy(policy: str) -> str:
    if policy not in DATA_POLICIES:
        raise ValueError(f"data policy must be one of {DATA_POLICIES}, got {policy!r}")
    if policy == "images" and not IMAGES_PERMITTED:
        raise ValueError(
            "data policy 'images' is blocked: D7 sends text only until the user permits images"
        )
    return policy


def _is_image(v: Any) -> bool:
    if isinstance(v, bytes | bytearray | memoryview):
        return True
    if hasattr(v, "__array_interface__") and getattr(v, "ndim", 0) >= 2:
        return True  # a frame (numpy array) that slipped into a result
    if isinstance(v, str) and v[:11].lower() == "data:image/":
        return True
    return isinstance(v, dict) and v.get("type") == "image"


def strip_images(value: Any) -> tuple[Any, int]:
    """A copy of `value` with every image-like value replaced by a marker, and the count."""
    if _is_image(value):
        return REMOVED_IMAGE, 1
    if isinstance(value, dict):
        out, n = {}, 0
        for k, v in value.items():
            out[k], m = strip_images(v)
            n += m
        return out, n
    if isinstance(value, list | tuple):
        items = [strip_images(v) for v in value]
        return [v for v, _ in items], sum(m for _, m in items)
    return value, 0


def to_jsonable(value: Any) -> Any:
    """AgentStore records have `to_dict`; other dataclasses go through `asdict`."""
    if hasattr(value, "to_dict"):
        return to_jsonable(value.to_dict())
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return to_jsonable(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [to_jsonable(v) for v in value]
    return value


# --------------------------------------------------------------------------- tool set


class ToolSet:
    """The tools offered under one data policy, and the single place that runs them."""

    def __init__(
        self,
        sources: Sources | None = None,
        *,
        policy: str = "text",
        specs: tuple[ToolSpec, ...] = TOOL_SPECS,
    ):
        self.sources = sources or Sources()
        self.policy = check_policy(policy)
        offered = [s for s in specs if s.kind == "action" or policy != "prompt_only"]
        self._specs = {s.name: s for s in offered}
        self._all = {s.name: s for s in specs}
        # built once: the provider sends this list unchanged on every call (cache prefix)
        self._definitions = tuple(s.definition() for s in offered)

    def definitions(self) -> list[dict]:
        return copy.deepcopy(list(self._definitions))

    def spec(self, name: str) -> ToolSpec | None:
        return self._specs.get(name)

    def call(self, name: str, tool_input: Any) -> ToolOutcome:
        spec = self._specs.get(name)
        if spec is None:
            why = (
                f"tool {name!r} is off under data policy {self.policy!r}"
                if name in self._all
                else f"no tool named {name!r}"
            )
            return ToolOutcome(name, "error", why, is_error=True)
        errors = validate(spec.input_schema, tool_input)
        if errors:
            return ToolOutcome(name, "error", "invalid input: " + "; ".join(errors), is_error=True)
        try:
            result = spec.handler(self.sources, dict(tool_input))
        except Exception as e:
            # any failure of a source (NotFoundError is a KeyError, but a broken store may
            # raise anything) becomes an is_error result: a tool_use left without its
            # tool_result would make every later request in the conversation fail
            return ToolOutcome(name, "error", f"{type(e).__name__}: {e}", is_error=True)
        if spec.kind == "action":
            return ToolOutcome(name, "action", "", draft=result)
        clean, removed = strip_images(to_jsonable(result))
        text = json.dumps(clean, ensure_ascii=False, sort_keys=True, default=str)
        truncated = len(text) > MAX_RESULT_CHARS
        if truncated:
            text = text[:MAX_RESULT_CHARS] + f"... [truncated: {len(text)} characters in all]"
        return ToolOutcome(name, "read", text, images_removed=removed, truncated=truncated)

    def expected_gate(self, command: dict) -> dict:
        """What the engine's gate code says now. Advisory: the engine decides again later."""
        gates = self.sources.gates
        if gates is None:
            return {"checked": False, "enabled": None, "reasons": ["gates not connected"]}
        op = command.get("op") or command["kind"]
        try:
            enabled, reasons = gates(op, dict(command.get("args", {})))
        except Exception as e:  # the card still appears; the engine checks again anyway
            return {
                "checked": False,
                "enabled": None,
                "reasons": [f"gate check failed: {type(e).__name__}: {e}"],
            }
        return {"checked": True, "enabled": bool(enabled), "reasons": list(reasons)}


# --------------------------------------------------------------------------- proposals

PROPOSAL_STATES = ("proposed", "confirmed", "rejected", "failed")

# Permission names are `auth.roles.Action` values (T-018), repeated so this package imports
# alone. D16: map flag and candidate decisions need WRITE_MAP_FLAG (operator, loopback), the
# same check as the map routes; abort and lights_off need nothing (rule 12); the rest OPERATE.
PERM_OPERATE = "operate"
PERM_STOP = "stop"
PERM_WRITE_MAP_FLAG = "write_map_flag"
MAP_WRITE_OPS = frozenset({"map_flag", "map_flag_retire", "candidate_confirm", "candidate_reject"})
STOP_KINDS = frozenset({"abort", "lights_off"})

# `allows(role, permission, local=...)`: `auth.roles.allows` once T-018 is merged
Allows = Callable[..., bool]


def required_permission(command: dict) -> str:
    if command.get("kind") in STOP_KINDS:
        return PERM_STOP
    if command.get("op") in MAP_WRITE_OPS:
        return PERM_WRITE_MAP_FLAG
    return PERM_OPERATE


class ConfirmRefused(RuntimeError):
    """The engine refused a confirmed proposal (busy, no control, no open session...). The
    card stays proposed with the reason in `note`, so the person can try again."""


@dataclass
class Proposal:
    """A command Claude asked for. Nothing runs until a person confirms it.

    With an engine connected (`propose`), the engine holds the proposal too: an unconfirmed
    assistant `start` waits in its `proposed` state (T-011) under `engine_op_id`, every screen
    sees it in the snapshot, and the decision goes to the engine as `approve` / `reject`.
    Stops (lights_off) are never held: confirming one sends the person's own stop.
    `status` here: proposed -> confirmed | rejected, or failed when the engine refused to hold
    it. After confirmation `op_id` names the engine operation.
    """

    proposal_id: str
    conversation_id: str
    tool: str
    command: dict  # engine Command fields: kind, op, args
    summary: str  # written by tools.py from the arguments
    reason: str  # the model's own words, grade "model"
    expected_gate: dict
    origin: str = "assistant"
    status: str = "proposed"
    created_t: float = field(default_factory=time.time)
    user_id: str | None = None
    session_id: str | None = None
    decided_by: str | None = None
    decided_t: float | None = None
    note: str = ""
    op_id: str | None = None
    engine_op_id: str | None = None

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


Submit = Callable[[dict], str]


class ProposalBook:
    """Proposals in memory, and the only path from a proposal to the engine.

    Both hooks get plain dicts; the server turns them into engine `Command`s and adds what it
    knows about the request (remote, control grant):
    - `propose(cmd)` at creation, for every non-stop proposal: kind "start", op, args,
      origin "assistant", proposal_id, conversation_id, user_id, session_id, no confirmed_by.
      Returns the engine op_id that holds it. If it raises, the card is `failed`.
    - `submit(cmd)` at a decision: `approve` / `reject` with `op_id` for a held proposal, a
      `lights_off` for a stop card, or (no engine hold) the start itself with `confirmed_by`.
      Decisions carry origin "human" except that last case. A route passes its own `submit`
      per call, built from that request's login and control grant.

    Before anything is submitted, `allows(role, required_permission(command), local=...)`
    must say yes (D16, T-018). Without an `allows` only stops can be confirmed: a missing
    check refuses rather than lets through. A refused confirmation leaves the card proposed.
    """

    def __init__(
        self,
        submit: Submit | None = None,
        *,
        allows: Allows | None = None,
        propose: Submit | None = None,
    ):
        self._submit = submit
        self._allows = allows
        self._propose = propose
        self._items: dict[str, Proposal] = {}
        self._lock = threading.Lock()

    def add(self, **fields: Any) -> Proposal:
        p = Proposal(proposal_id="prop-" + uuid.uuid4().hex[:12], **fields)
        if self._propose is not None and p.command.get("kind") not in STOP_KINDS:
            try:
                p.engine_op_id = self._propose(
                    {
                        "kind": "start",
                        "op": p.command.get("op", ""),
                        "args": dict(p.command.get("args", {})),
                        "origin": "assistant",
                        "proposal_id": p.proposal_id,
                        "conversation_id": p.conversation_id,
                        "user_id": p.user_id,
                        "session_id": p.session_id,
                    }
                )
            except Exception as e:  # unknown operation, engine not running...
                p.status, p.note = "failed", f"the engine refused the proposal: {e}"
        with self._lock:
            self._items[p.proposal_id] = p
        return p

    def get(self, proposal_id: str) -> Proposal:
        with self._lock:
            if proposal_id not in self._items:
                raise KeyError(f"no proposal {proposal_id!r}")
            return self._items[proposal_id]

    def list(self, status: str | None = None, conversation_id: str | None = None) -> list:
        with self._lock:
            items = list(self._items.values())
        return [
            p
            for p in items
            if (status is None or p.status == status)
            and (conversation_id is None or p.conversation_id == conversation_id)
        ]

    def _decide(self, proposal_id: str, status: str, by: str, note: str) -> Proposal:
        with self._lock:
            p = self._items.get(proposal_id)
            if p is None:
                raise KeyError(f"no proposal {proposal_id!r}")
            if p.status != "proposed":
                raise ValueError(f"proposal {proposal_id} is already {p.status}")
            p.status, p.decided_by, p.decided_t, p.note = status, by, time.time(), note
            return p

    def check_permission(self, proposal_id: str, *, role: str | None, local: bool) -> str:
        """The permission the proposal's command needs; PermissionError if `role` lacks it."""
        p = self.get(proposal_id)
        if p.status != "proposed":
            raise ValueError(f"proposal {proposal_id} is already {p.status}")
        perm = required_permission(p.command)
        if perm == PERM_STOP:
            return perm
        if self._allows is None:
            raise PermissionError(f"no permission check connected: a {perm} card cannot be decided")
        if role is None or not self._allows(role, perm, local=local):
            where = "on the microscope PC" if local else "from a remote browser"
            raise PermissionError(f"role {role!r} may not decide a {perm} card {where}")
        return perm

    def _decision(self, p: Proposal, kind: str, by: str, session_id: str | None) -> dict:
        ids = {
            "proposal_id": p.proposal_id,
            "conversation_id": p.conversation_id,
            "user_id": by,
            "session_id": session_id or p.session_id,
        }
        if kind == "reject":
            return {"kind": "reject", "op_id": p.engine_op_id, "origin": "human", **ids}
        if p.engine_op_id:
            return {
                "kind": "approve",
                "op_id": p.engine_op_id,
                "origin": "human",
                "confirmed_by": by,
                **ids,
            }
        if p.command.get("kind") in STOP_KINDS:
            return {**p.command, "origin": "human", **ids}
        return {**p.command, "origin": p.origin, "confirmed_by": by, **ids}

    def confirm(
        self,
        proposal_id: str,
        *,
        by: str,
        role: str | None = None,
        local: bool = False,
        session_id: str | None = None,
        submit: Submit | None = None,
    ) -> Proposal:
        if not by:
            raise ValueError("a confirmation needs the person who confirmed")
        send = submit or self._submit
        if send is None:
            raise RuntimeError("no engine connected: a proposal cannot be confirmed")
        self.check_permission(proposal_id, role=role, local=local)
        p = self._decide(proposal_id, "confirmed", by, "")
        try:
            p.op_id = send(self._decision(p, "confirm", by, session_id))
        except Exception as e:
            with self._lock:  # the engine said no: the card stays and can be confirmed again
                p.status, p.decided_by, p.decided_t = "proposed", None, None
                p.note = f"{type(e).__name__}: {e}"
            raise ConfirmRefused(p.note) from e
        return p

    def reject(
        self, proposal_id: str, *, by: str, note: str = "", submit: Submit | None = None
    ) -> Proposal:
        if not by:
            raise ValueError("a rejection needs the person who rejected")
        p = self._decide(proposal_id, "rejected", by, note)
        send = submit or self._submit
        if p.engine_op_id and send is not None:
            try:
                send(self._decision(p, "reject", by, None))
            except Exception as e:  # rejected here regardless; the engine copy may linger
                p.note = (note + " " if note else "") + f"[engine: {type(e).__name__}: {e}]"
        return p
