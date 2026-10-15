"""The assistant's routes (T-013; PLAN.md 5 "Claude 연동", D6-D8, D16). Mounted at
`/api/assistant` by the area registration in `server/api/__init__.py`.

- `GET  /status`: exactly `{provider, connected, data_stage}` (the web shell reads these).
- `POST /ask`: a question and its screen context; the answer streams back as NDJSON (one
  `AssistantEvent` per line) over plain fetch. Needs `submit_question` (operator, on the
  microscope PC; D16).
- `GET  /conversations/{id}`: one conversation, for every screen's prompt box.
- `POST /proposals/{id}/confirm` and `/reject`: a person decides a proposal card.

The middleware has already refused writes without a live unlocked login, from a remote PC or
from a foreign page. Here each route adds what depends on the content: `submit_question` for a
question, and for a confirmation or a rejection (T-013c: clearing a card is a write too) the
same rule the command's own route uses, so a Claude
proposal cannot get round it: a stop as a stop, a map write by WRITE_MAP_FLAG (D16, as in
`/api/map`), anything else as a `start` of that operation (role OPERATE). The engine then
checks control, session and state, as for any command.

The engine holds each proposal too (an unconfirmed assistant `start`, T-011), so it appears in
every screen's snapshot; a confirmation sends `approve` with this request's login and control
grant. The browser never sees the grant.

The `Assistant` lives in `app.state.assistant`; it is built on first use from
`AssistantConfig.from_env()` (fake provider unless the server was started with
`DINO_AF_ASSISTANT_PROVIDER=anthropic`) unless something set it before. Its records also go to
the audit log (questions, answers, proposals, decisions).
"""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
from typing import Any, Literal

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from ...assistant import Assistant, AssistantConfig, Sources, connection_status
from ...assistant.records import RecordLog
from ...assistant.runner import check_context
from ...assistant.tools import (
    PERM_STOP,
    PERM_WRITE_MAP_FLAG,
    ConfirmRefused,
    Proposal,
    required_permission,
)
from ...auth import AuditKind, allows
from ..schemas import ApiError, Command, EngineAPI
from . import (
    AuthSeat,
    LoginState,
    Refusal,
    SessionSeat,
    command_why,
    login_state,
    server_action_why,
)

log = logging.getLogger(__name__)

router = APIRouter()

_BUILD_LOCK = threading.Lock()

NOT_FOUND = "not_found"


# -- wire models ------------------------------------------------------------------------


class AssistantStatus(BaseModel):
    """Exactly these three names (T-010 status bar). `connected` is true only for the
    anthropic provider with the package and credentials on this server."""

    provider: Literal["fake", "anthropic"]
    connected: bool
    data_stage: Literal["prompt_only", "text", "images"]


class AskIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    context: dict[str, Any] = Field(default_factory=dict)  # the screen's: area, ids, region
    conversation_id: str | None = None  # continue this one; None starts a new one


class AssistantEvent(BaseModel):
    """One NDJSON line of `POST /ask`. `type` says which fields are set:
    start (conversation_id), text (text: a piece of the answer), tool_call (id, name, input,
    kind), tool_result (id, name, is_error, images_removed), proposal (proposal), usage
    (usage), error (error), done (answer). The stream ends after done or error."""

    type: Literal["start", "text", "tool_call", "tool_result", "proposal", "usage", "error", "done"]
    conversation_id: str | None = None
    text: str | None = None
    id: str | None = None
    name: str | None = None
    input: dict[str, Any] | None = None
    kind: str | None = None
    is_error: bool | None = None
    images_removed: int | None = None
    proposal: dict[str, Any] | None = None
    usage: dict[str, int] | None = None
    error: str | None = None
    answer: dict[str, Any] | None = None


class ProposalOut(BaseModel):
    """A proposal card. `command` is what runs if a person confirms it; `summary` is written
    by the server from it; `reason` is the model's own text (grade model). `expected_gate` is
    the engine's answer when the card was made; it decides again on confirmation."""

    proposal_id: str
    conversation_id: str
    tool: str
    command: dict[str, Any]
    summary: str
    reason: str
    expected_gate: dict[str, Any]
    origin: str
    status: Literal["proposed", "confirmed", "rejected", "failed"]
    created_t: float
    user_id: str | None = None
    session_id: str | None = None
    decided_by: str | None = None
    decided_t: float | None = None
    note: str = ""
    op_id: str | None = None
    engine_op_id: str | None = None

    @classmethod
    def of(cls, p: Proposal | dict) -> ProposalOut:
        return cls.model_validate(p if isinstance(p, dict) else p.to_dict())


class ConversationOut(BaseModel):
    """`messages` are the Messages API turns as sent (user and assistant content blocks)."""

    conversation_id: str
    messages: list[dict[str, Any]]
    usage: dict[str, int]
    proposals: list[ProposalOut]


class RejectIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str = ""


ERRORS = {s: {"model": ApiError} for s in (400, 401, 403, 404, 409, 422, 423, 503)}


# -- wiring -----------------------------------------------------------------------------

_AUDIT = {
    "question": AuditKind.QUESTION_SUBMITTED,
    "answer": AuditKind.ASSISTANT_MESSAGE,
    "proposal": AuditKind.COMMAND_PROPOSED,
    "proposal_confirmed": AuditKind.COMMAND_CONFIRMED,
    "proposal_rejected": AuditKind.COMMAND_REJECTED,
}
_AUDIT_FIELDS = (
    "conversation_id",
    "proposal_id",
    "engine_op_id",
    "op_id",
    "question",
    "context",
    "text",
    "stop_reason",
    "usage",
    "command",
    "summary",
    "note",
)


def audit_sink(audit: Any):
    """The assistant's records that the audit log keeps (PLAN.md 5: Claude conversations,
    every proposal and decision). A failing audit write is logged, never raised."""

    def sink(entry: dict) -> None:
        kind = _AUDIT.get(entry["kind"])
        if kind is None:
            return
        fields = {k: entry[k] for k in _AUDIT_FIELDS if k in entry}
        try:
            audit.append(
                kind,
                entry.get("user_id"),
                session_id=entry.get("session_id"),
                source="assistant",
                **fields,
            )
        except Exception:
            log.exception("audit write for assistant record %s failed", entry["kind"])

    return sink


def engine_gates(engine: EngineAPI):
    """The card's expected gate: the engine's own `check` for that operation."""

    def gates(op: str, args: dict) -> tuple[bool, list[str]]:
        r = engine.check([op], {"args": {op: dict(args)}}).get(op) or {}
        return bool(r.get("allowed")), [r["reason"]] if r.get("reason") else []

    return gates


def engine_propose(engine: EngineAPI):
    """Hand a new proposal to the engine, which holds it as `proposed` until a person
    decides (an assistant `start` without `confirmed_by` never runs)."""

    def propose(d: dict) -> str:
        return engine.submit(
            Command(
                kind="start",
                op=d["op"],
                args=dict(d.get("args") or {}),
                origin="assistant",
                user_id=d.get("user_id"),
                session_id=d.get("session_id"),
                proposal_id=d.get("proposal_id"),
                conversation_id=d.get("conversation_id"),
                t=time.time(),
            )
        )

    return propose


def request_submit(engine: EngineAPI, me: LoginState, seat: AuthSeat):
    """A decision as an engine Command from this request: its login, place and control
    grant (held by the server, never sent to the browser)."""
    grant = seat.grant_for(me.info)

    def submit(d: dict) -> str:
        origin = d.get("origin", "human")
        return engine.submit(
            Command(
                kind=d["kind"],
                op=d.get("op", ""),
                op_id=d.get("op_id") or "",
                args=dict(d.get("args") or {}),
                origin=origin,
                user_id=me.user_id,
                session_id=d.get("session_id"),
                proposal_id=d.get("proposal_id"),
                conversation_id=d.get("conversation_id"),
                confirmed_by=d.get("confirmed_by") if origin == "assistant" else None,
                remote=not me.local,
                control_grant=grant,
                t=time.time(),
            )
        )

    return submit


def build_assistant(state: Any, config: AssistantConfig | None = None) -> Assistant:
    config = config or AssistantConfig.from_env()
    engine = state.engine
    audit = getattr(state.auth, "audit", None)
    # the card's expected gate: the T-028 hardware provider's `check(op, args)` when
    # create_app has one (T-009g), else the engine's own `check`
    hardware = getattr(state, "hardware", None)
    gates = hardware.check if hardware is not None else engine_gates(engine)
    return Assistant(
        config,
        sources=Sources(snapshot=engine.snapshot, store=state.agent_store, gates=gates),
        propose=engine_propose(engine),
        allows=allows,
        records=RecordLog(config.records_dir, sinks=[audit_sink(audit)] if audit else []),
    )


def get_assistant(request: Request) -> Assistant:
    state = request.app.state
    a = getattr(state, "assistant", None)
    if a is None:
        with _BUILD_LOCK:
            a = getattr(state, "assistant", None)
            if a is None:
                a = state.assistant = build_assistant(state)
    return a


def _session_id(sessions: SessionSeat | None) -> str | None:
    cur = getattr(sessions, "current", None)
    return cur.info.session_id if cur is not None else None


def _not_found(what: str) -> Refusal:
    return Refusal(404, NOT_FOUND, f"no {what}")


def _decision_gate(request: Request, proposal_id: str) -> tuple[LoginState, Assistant]:
    """Who decides a card, checked the same way for confirm and reject: the rule of the
    card's command (`confirm_why`), and a login (a stop passes without one, a card decision
    does not). The assistant's book checks the role once more."""
    me = login_state(request)
    a = get_assistant(request)
    try:
        p = a.proposals.get(proposal_id)
    except KeyError as e:
        raise _not_found("proposal with that id").http() from e
    remote_abort = getattr(request.app.state, "remote_abort", True)
    if why := confirm_why(me, p.command, remote_abort):
        raise why.http()
    if me.info is None:
        raise Refusal(401, "login_required", "log in first").http()
    return me, a


def confirm_why(me: LoginState, command: dict, remote_abort: bool) -> Refusal | None:
    """The rule of the command's own route (see the module docstring)."""
    perm = required_permission(command)
    if perm == PERM_STOP:
        return command_why(me, command["kind"], remote_abort=remote_abort)
    if perm == PERM_WRITE_MAP_FLAG:
        return server_action_why(me, command["op"])
    return command_why(me, "start", command.get("op", ""), remote_abort=remote_abort)


# -- routes -----------------------------------------------------------------------------


@router.get("/status", response_model=AssistantStatus)
def status(request: Request) -> AssistantStatus:
    return AssistantStatus(**connection_status(get_assistant(request).config))


@router.post(
    "/ask",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "NDJSON: one AssistantEvent per line, ending with done or error",
            "content": {"application/x-ndjson": {"schema": AssistantEvent.model_json_schema()}},
        },
        **ERRORS,
    },
)
def ask(body: AskIn, request: Request) -> StreamingResponse:
    me = login_state(request)
    if why := server_action_why(me, "submit_question"):
        raise why.http()
    if not body.question.strip():
        raise Refusal(422, "invalid", "empty question").http()
    try:
        context = check_context(body.context)
    except ValueError as e:
        raise Refusal(422, "invalid", str(e)).http() from e
    a = get_assistant(request)
    try:
        cid = a.open_conversation(body.conversation_id)
    except KeyError as e:
        raise _not_found("conversation with that id").http() from e
    sid = _session_id(request.app.state.sessions)
    events: queue.Queue = queue.Queue()
    failed = threading.Event()

    def emit(ev: dict) -> None:
        if ev.get("type") == "error":
            failed.set()
        events.put(ev)

    def work() -> None:
        try:
            a.ask(
                body.question,
                context=context,
                conversation_id=cid,
                user_id=me.user_id,
                session_id=sid,
                on_event=emit,
            )
        except Exception as e:  # the runner has said so already for provider errors
            if not failed.is_set():
                emit({"type": "error", "error": f"{type(e).__name__}: {e}"})
        finally:
            events.put(None)

    events.put({"type": "start", "conversation_id": cid})
    threading.Thread(target=work, daemon=True, name=f"assistant-{cid}").start()

    def lines():
        while (ev := events.get()) is not None:
            yield json.dumps(ev, ensure_ascii=False, default=str) + "\n"

    return StreamingResponse(lines(), media_type="application/x-ndjson")


@router.get("/conversations/{conversation_id}", response_model=ConversationOut, responses=ERRORS)
def conversation(conversation_id: str, request: Request) -> ConversationOut:
    try:
        c = get_assistant(request).conversation(conversation_id)
    except KeyError as e:
        raise _not_found("conversation with that id").http() from e
    return ConversationOut(
        conversation_id=c["conversation_id"],
        messages=c["messages"],
        usage=c["usage"],
        proposals=[ProposalOut.of(p) for p in c["proposals"]],
    )


@router.post("/proposals/{proposal_id}/confirm", response_model=ProposalOut, responses=ERRORS)
def confirm(proposal_id: str, request: Request) -> ProposalOut:
    me, a = _decision_gate(request, proposal_id)
    state = request.app.state
    try:
        out = a.confirm(
            proposal_id,
            by=me.user_id,
            role=str(me.info.role),
            local=me.local,
            session_id=_session_id(state.sessions),
            submit=request_submit(state.engine, me, state.auth),
        )
    except PermissionError as e:
        raise Refusal(403, "role", str(e)).http() from e
    except ConfirmRefused as e:
        raise Refusal(400, "refused", str(e)).http() from e
    except ValueError as e:
        raise Refusal(409, "decided", str(e)).http() from e
    return ProposalOut.of(out)


@router.post("/proposals/{proposal_id}/reject", response_model=ProposalOut, responses=ERRORS)
def reject(proposal_id: str, request: Request, body: RejectIn | None = None) -> ProposalOut:
    """Clearing a card needs the same permission as confirming it (T-013c, D16)."""
    me, a = _decision_gate(request, proposal_id)
    state = request.app.state
    try:
        out = a.reject(
            proposal_id,
            by=me.user_id,
            note=(body.note if body else ""),
            role=str(me.info.role),
            local=me.local,
            submit=request_submit(state.engine, me, state.auth),
        )
    except KeyError as e:
        raise _not_found("proposal with that id").http() from e
    except PermissionError as e:
        raise Refusal(403, "role", str(e)).http() from e
    except ValueError as e:
        raise Refusal(409, "decided", str(e)).http() from e
    return ProposalOut.of(out)
