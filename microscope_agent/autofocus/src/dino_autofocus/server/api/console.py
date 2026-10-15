"""Console area (PLAN.md F1, ui-spec 7.1, docs/screens/console.md): the agents' questions, runs
and inbox, read from the AgentStore, and the one write, a question to the mock store.

A run that soft-matter-agents' orchestrator is executing is followed through what it offers a
console (its plan.md 11-25; `agents/sma_run.py`): `GET .../stream` reads its events.jsonl,
`GET .../frame` asks its frame tap for the latest frame (it holds no core and never snaps;
OD-13), and `POST .../stop` is the console's Abort for that run, sent on the run's own
loopback stop channel. The stop is a stop: the access middleware treats it as `abort` (from
the microscope PC always, from a logged-in remote viewer when remote abort is on, D13), and
it is sent only when a person presses it. Closing the page stops nothing (OD-30). Nothing is
written in the soft-matter-agents tree.

The router reads only. Whether someone may submit is not decided here: the access middleware
already refuses a remote or logged-out write, and the route asks `server_action_why` for the
T-018 permission `SUBMIT_QUESTION` (operator on the microscope PC, D16). The console's own rule
is the read-only store (409). Records pass through as the store has them: card contents,
grades and `numbers` are not touched (PLAN.md 6절 3항).
"""

from __future__ import annotations

import json
from typing import Any, Literal

from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ...agents import (
    AGENTS,
    MockStore,
    NotFoundError,
    ReadOnlyStoreError,
    StoreError,
    sma_live,
    sma_run,
)
from ...auth import AuditKind
from . import (
    AgentStoreDep,
    Auth,
    Login,
    Refusal,
    Sessions,
    command_why,
    server_action_why,
)

router = APIRouter()

AgentName = Literal["microscope", "simulation"]
READ_ONLY_MESSAGE = "Submitting to soft-matter-agents is not connected yet (read-only)"


# -- wire models (the AgentStore records' to_dict() shapes) -------------------------------


class FileInfoOut(BaseModel):
    name: str
    size: int | None


class CardOut(BaseModel):
    name: str
    kind: str
    version: int
    status: str | None
    created_at: str | None
    data: Any = Field(description="the card file's content, untouched")


class DocumentOut(BaseModel):
    name: str
    version: int
    text: str


class QuestionSummaryOut(BaseModel):
    qid: str
    agent: AgentName
    title: str
    status: str | None
    created_at: str | None
    updated_at: str | None
    latest_version: int
    versions: list[int]
    source: str
    purpose: str | None = None
    intent: str | None = None
    observable_name: str | None = None


class ApprovalOut(BaseModel):
    name: str
    agent: AgentName
    id: str | None
    qid: str | None
    revision: int | None
    status: str | None
    plan_id: str | None
    plan_revision: int | None
    plan_hash: str | None
    approved_by: str | None
    approved_at: str | None
    source: str
    plan_found: bool | None = Field(
        description="a plan card of the question hashes to plan_hash; None: no question folder")
    data: Any = Field(default=None, description="the approval card's content, untouched")


class QuestionDetailOut(BaseModel):
    summary: QuestionSummaryOut
    version: int
    goal: CardOut | None
    axes: list[CardOut]
    plan: CardOut | None
    synthesis: CardOut | None
    refusals: list[CardOut]
    results: list[CardOut]
    others: list[CardOut]
    documents: list[DocumentOut]
    files: list[FileInfoOut]
    plan_hash: str | None = Field(
        default=None, description="sha256 of this version's plan card with status removed")
    approvals: list[ApprovalOut] = Field(default_factory=list,
                                         description="every plan_approval naming this qid")


class RunSummaryOut(BaseModel):
    run_id: str
    agent: AgentName
    qid: str | None
    plan_id: str | None
    status: str | None
    created_at: str | None
    finished_at: str | None
    backend: str | None
    source: str
    approval_kind: str | None = None


class RunDetailOut(BaseModel):
    summary: RunSummaryOut
    records: dict[str, Any] = Field(description="file name -> content, untouched")
    files: list[FileInfoOut]
    not_opened: list[str]


class InboxMessageOut(BaseModel):
    name: str
    round: int | None
    kind: str
    card: Any
    text: str | None


class InboxThreadOut(BaseModel):
    thread: str
    agent: AgentName | None
    state: str | None
    turn: str | None
    round: int | None
    updated_at: str | None
    status: Any
    messages: list[InboxMessageOut]
    source: str


class StoreOut(BaseModel):
    store: str = Field(description='"mock" or "soft-matter-agents"')
    writable: bool


class RunStreamOut(BaseModel):
    """A run soft-matter-agents' orchestrator follows: its events.jsonl so far."""

    run_id: str
    agent: AgentName
    followed: bool = Field(description="the run has an events.jsonl that begins with run_started")
    state: Literal["running", "ended", "not_followed"]
    ended_how: str | None = Field(
        description="run_ended's how: completed, aborted_by_monitor, stopped_from_outside, failed")
    plan_id: str | None
    revision: Any = None
    t0_wall: str | None
    can_stop: bool = Field(description="running, with a loopback stop channel announced")
    stop_unavailable: str | None = Field(description="why the console cannot stop it, in words")
    frame_tap: bool = Field(description="running, with a loopback frame tap announced")
    events: list[dict[str, Any]] = Field(description="lines after run_started, from `since` on")
    total: int = Field(description="lines after run_started so far; the next `since`")
    partial_tail: bool
    bad_lines: int


class StopIn(BaseModel):
    reason: str = Field(default="", max_length=600)


class StopOut(BaseModel):
    run_id: str
    outcome: Literal["begun", "refused", "no_answer"]
    message: str


class LiveListOut(BaseModel):
    name: str
    sha256: str = Field(description="of the list file's bytes; the only thing the console sends")
    data: Any = Field(description="the list as the person wrote it, untouched")


class LiveOut(BaseModel):
    """soft-matter-agents' live view (its card 062): whether its host runs, and which
    approved lists the person may switch on."""

    available: bool = Field(description="host reachable and the store is soft-matter-agents")
    why_not: str | None = Field(description="why live view cannot be switched on, in words")
    host: str | None = Field(description="127.0.0.1:<port> when known")
    lists: list[LiveListOut]


class LiveOnIn(BaseModel):
    sha256: str = Field(min_length=64, max_length=64)


class LiveOnOut(BaseModel):
    outcome: Literal["started", "refused"]
    run_id: str | None
    reason: str | None


class QuestionIn(BaseModel):
    text: str
    target: AgentName
    purpose: str | None = None
    observable: str | None = None


# -- refusals -----------------------------------------------------------------------------


def _not_found(e: NotFoundError) -> Refusal:
    return Refusal(404, "not_found", str(e))


def _invalid(e: ValueError) -> Refusal:
    return Refusal(422, "invalid", str(e))


READ_ONLY = Refusal(409, "read_only_store", READ_ONLY_MESSAGE)

ERRORS: dict[int | str, dict[str, Any]] = {
    404: {"description": "no such question, version or run"},
    500: {"description": "the store could not read the files"},
}


def _store_error(e: StoreError) -> Refusal:
    return Refusal(500, "store_error", str(e))


def _newest_first(items: list[Any]) -> list[Any]:
    return sorted(items, key=lambda x: (x.created_at or "", getattr(x, "qid", None) or
                                        getattr(x, "run_id", "")), reverse=True)


def _agents(agent: AgentName | None) -> tuple[str, ...]:
    return AGENTS if agent is None else (agent,)


# -- routes -------------------------------------------------------------------------------


@router.get("/store", response_model=StoreOut)
def store_info(store: AgentStoreDep) -> StoreOut:
    """Which store is behind the console, and whether a question can be submitted to it."""
    if isinstance(store, MockStore):
        name = "mock"
    else:
        name = getattr(store, "source", "soft-matter-agents")
    return StoreOut(store=name, writable=bool(store.writable))


@router.get("/questions", response_model=list[QuestionSummaryOut], responses=ERRORS)
def list_questions(store: AgentStoreDep,
                   agent: AgentName | None = None) -> list[QuestionSummaryOut]:
    """Both agents' questions, newest first, unless `agent` names one."""
    try:
        found = [q for a in _agents(agent) for q in store.list_questions(a)]
    except StoreError as e:
        raise _store_error(e).http() from e
    return [QuestionSummaryOut.model_validate(q.to_dict()) for q in _newest_first(found)]


@router.get("/questions/{qid}", response_model=QuestionDetailOut, responses=ERRORS)
def get_question(qid: str, store: AgentStoreDep, version: int | None = None) -> QuestionDetailOut:
    """One version of a question (the latest unless `version` is given)."""
    try:
        d = store.get_question(qid, version)
    except NotFoundError as e:
        raise _not_found(e).http() from e
    except StoreError as e:
        raise _store_error(e).http() from e
    return QuestionDetailOut.model_validate(d.to_dict())


@router.get("/runs", response_model=list[RunSummaryOut], responses=ERRORS)
def list_runs(store: AgentStoreDep, agent: AgentName | None = None) -> list[RunSummaryOut]:
    try:
        found = [r for a in _agents(agent) for r in store.list_runs(a)]
    except StoreError as e:
        raise _store_error(e).http() from e
    return [RunSummaryOut.model_validate(r.to_dict()) for r in _newest_first(found)]


@router.get("/runs/{agent}/{run_id}", response_model=RunDetailOut, responses=ERRORS)
def get_run(agent: AgentName, run_id: str, store: AgentStoreDep) -> RunDetailOut:
    try:
        r = store.get_run(agent, run_id)
    except NotFoundError as e:
        raise _not_found(e).http() from e
    except StoreError as e:
        raise _store_error(e).http() from e
    return RunDetailOut.model_validate(r.to_dict())


@router.get("/approvals", response_model=list[ApprovalOut], responses=ERRORS)
def list_approvals(store: AgentStoreDep, agent: AgentName | None = None) -> list[ApprovalOut]:
    """The seats' plan_approval cards (approvals/), newest first. Read only: an approval is
    written by the person, never by the console (plan.md 11-25)."""
    reader = getattr(store, "list_approvals", None)
    if reader is None:
        return []
    try:
        found = [a for ag in _agents(agent) for a in reader(ag)]
    except StoreError as e:
        raise _store_error(e).http() from e
    found.sort(key=lambda a: (a.approved_at or "", a.name), reverse=True)
    return [ApprovalOut.model_validate(a.to_dict()) for a in found]


# -- a run soft-matter-agents executes: follow, frame, stop (plan.md 11-25) ------------------

NOT_FOLLOWED_STOP = ("this run is not followed (no events.jsonl), so the console has no stop "
                     "channel for it; stop it at the instrument or in the operator terminal")
SIM_STOP = "the console does not stop simulation runs"


def _stream(store: Any, agent: str, run_id: str) -> sma_run.RunStream:
    """The run's stream, or a refusal: 404 no such run, 409 not followed."""
    reader = getattr(store, "run_stream", None)
    if reader is None:
        raise Refusal(409, "not_followed", "this store does not read followed runs").http()
    try:
        return reader(agent, run_id)
    except NotFoundError as e:
        raise _not_found(e).http() from e
    except sma_run.NotFollowedError as e:
        raise Refusal(409, "not_followed", str(e)).http() from e
    except sma_run.SmaRunError as e:
        raise Refusal(500, "store_error", str(e)).http() from e


@router.get("/runs/{agent}/{run_id}/stream", response_model=RunStreamOut, responses=ERRORS)
def run_stream(agent: AgentName, run_id: str, store: AgentStoreDep,
               since: int = 0) -> RunStreamOut:
    """A followed run's events from line `since` on (poll with the last `total`). A run with
    no events.jsonl answers `state: not_followed` and why the console cannot stop it."""
    reader = getattr(store, "run_stream", None)
    try:
        st = reader(agent, run_id) if reader is not None else None
    except NotFoundError as e:
        raise _not_found(e).http() from e
    except sma_run.NotFollowedError:
        st = None
    except sma_run.SmaRunError as e:
        raise Refusal(500, "store_error", str(e)).http() from e
    if st is None:
        try:
            store.get_run(agent, run_id)  # 404 for no such run
        except NotFoundError as e:
            raise _not_found(e).http() from e
        except StoreError as e:
            raise _store_error(e).http() from e
        return RunStreamOut(
            run_id=run_id, agent=agent, followed=False, state="not_followed", ended_how=None,
            plan_id=None, t0_wall=None, can_stop=False,
            stop_unavailable=SIM_STOP if agent == "simulation" else NOT_FOLLOWED_STOP,
            frame_tap=False, events=[], total=0, partial_tail=False, bad_lines=0)
    if agent != "microscope":
        why = SIM_STOP
    elif not st.running:
        why = f"the run has ended ({st.ended_how})"
    elif st.stop_channel is None:
        why = "the run announced no loopback stop channel; stop it at the instrument"
    else:
        why = None
    since = max(0, since)
    return RunStreamOut(
        run_id=st.run_id, agent=agent, followed=True,
        state="running" if st.running else "ended", ended_how=st.ended_how,
        plan_id=st.plan_id, revision=st.revision, t0_wall=st.t0_wall,
        can_stop=why is None, stop_unavailable=why,
        frame_tap=st.running and st.frame_tap is not None,
        events=st.events[since:], total=len(st.events),
        partial_tail=st.partial_tail, bad_lines=st.bad_lines)


@router.get(
    "/runs/{agent}/{run_id}/frame",
    response_class=Response,
    responses={200: {"content": {"image/jpeg": {}},
                     "description": "the run's latest frame, binned and JPEG'd; header "
                                    "X-DinoAF-Frame holds its metadata as JSON"},
               204: {"description": "no frame yet: the run has acquired nothing"},
               409: {"description": "not followed, ended, or no frame tap"},
               502: {"description": "the frame tap did not answer"}},
)
def run_frame(agent: AgentName, run_id: str, store: AgentStoreDep) -> Response:
    """The run's latest frame from its frame tap, which hands over a copy and commands
    nothing; the console opens no camera of its own (OD-13)."""
    st = _stream(store, agent, run_id)
    try:
        got = sma_run.latest_frame(st)
    except sma_run.RunEndedError as e:
        raise Refusal(409, "run_ended", str(e)).http() from e
    except sma_run.NotFollowedError as e:
        raise Refusal(409, "no_frame_tap", str(e)).http() from e
    except sma_run.SmaRunError as e:
        raise Refusal(502, "frame_tap_unreachable", str(e)).http() from e
    if got is None:
        return Response(status_code=204)
    if got.pixels is None:
        raise Refusal(502, "frame_unreadable",
                      f"the tap sent shape {got.shape} dtype {got.dtype!r}, not a mono frame "
                      "the console can show").http()
    from ..ws import encode_frame  # here, not at import: ws imports this package

    frame, jpeg = encode_frame(got.pixels, {**got.metadata, "t": got.t_mono or 0.0}, 0)
    head = {"run_id": st.run_id, "t_mono": got.t_mono, "shape": got.shape, "dtype": got.dtype,
            "binning": frame.binning, "display_min": frame.display_min,
            "display_max": frame.display_max, "time_base": "software (the run's t_mono)"}
    return Response(jpeg, media_type="image/jpeg",
                    headers={"X-DinoAF-Frame": json.dumps(head, default=str),
                             "Cache-Control": "no-store"})


@router.post(
    "/runs/{agent}/{run_id}/stop",
    response_model=StopOut,
    responses={403: {"description": "remote view with remote abort off, or logged out (D13)"},
               404: {"description": "no such run"},
               409: {"description": "not followed, ended, or a simulation run"},
               502: {"description": "the stop channel did not answer a connection"}},
)
def stop_run(agent: AgentName, run_id: str, body: StopIn, request: Request, store: AgentStoreDep,
             me: Login, seat: Auth) -> StopOut:
    """Abort a run soft-matter-agents executes: one line on the stop channel it announced.
    The run calls the same abort() as its other stop paths and records who asked."""
    remote_abort = getattr(request.app.state, "remote_abort", True)
    if why := command_why(me, "abort", remote_abort=remote_abort):
        raise why.http()
    if agent != "microscope":
        raise Refusal(409, "not_followed", SIM_STOP).http()
    st = _stream(store, agent, run_id)
    who = me.user_id or ("the microscope PC" if me.local else "a remote viewer")
    reason = body.reason.strip() or "Abort pressed"
    try:
        result = sma_run.send_stop(st, f"{reason} (by {who})")
    except sma_run.RunEndedError as e:
        raise Refusal(409, "run_ended", str(e)).http() from e
    except sma_run.NotFollowedError as e:
        raise Refusal(409, "no_stop_channel", str(e)).http() from e
    except sma_run.UnreachableError as e:
        raise Refusal(502, "stop_unreachable", str(e)).http() from e
    if seat.audit is not None:
        seat.audit.append(AuditKind.COMMAND_EXECUTED, me.user_id, origin="console",
                          command="sma_stop", run_id=st.run_id, local=me.local,
                          outcome=result.outcome)
    return StopOut(run_id=st.run_id, outcome=result.outcome,  # type: ignore[arg-type]
                   message=result.message)


# -- live view from the console (soft-matter-agents card 062) ----------------------------------

NOT_SMA = "the console is not connected to the soft-matter-agents files (start it with --store sma)"


def _live_host(request: Request) -> tuple[sma_run.Address | None, str | None]:
    fixed = getattr(request.app.state, "live_host", None)
    if fixed:
        try:
            return sma_live.parse_host(fixed), None
        except ValueError as e:
            return None, str(e)
    return sma_live.host_address(getattr(request.app.state, "live_host_file", None))


def _sma_root(store: Any) -> Any:
    return None if isinstance(store, MockStore) else getattr(store, "root", None)


@router.get("/live", response_model=LiveOut)
def live_state(request: Request, store: AgentStoreDep) -> LiveOut:
    """Whether a live view can be switched on, and the approved live-view lists to name.
    Answers only from the address file and approvals/; it connects to nothing."""
    root = _sma_root(store)
    lists = [] if root is None else sma_live.live_lists(root)
    addr, why = _live_host(request)
    if root is None:
        why = NOT_SMA
    elif why is None and not lists:
        why = "no approved live-view list in microscope_agent/approvals/ (the person writes it)"
    return LiveOut(available=why is None, why_not=why,
                   host=None if addr is None else f"{addr.host}:{addr.port}",
                   lists=[LiveListOut(name=x.name, sha256=x.sha256, data=x.data) for x in lists])


@router.post(
    "/live/on",
    response_model=LiveOnOut,
    responses={403: {"description": "not the microscope PC, or a role that may not operate"},
               409: {"description": "not connected to soft-matter-agents, or no such list"},
               502: {"description": "the live-view host is not running or did not answer"}},
)
def live_switch_on(body: LiveOnIn, request: Request, store: AgentStoreDep, me: Login,
                   seat: Auth) -> LiveOnOut:
    """Ask soft-matter-agents' live-view host to run the approved list named by its sha256.
    It starts an acquisition and may light the sample, so it is an operator action on the
    microscope PC. "Live off" is the run's own stop (`POST .../runs/microscope/{id}/stop`)."""
    if why := server_action_why(me, "live_on"):
        raise why.http()
    root = _sma_root(store)
    if root is None:
        raise Refusal(409, "not_sma", NOT_SMA).http()
    if body.sha256 not in {x.sha256 for x in sma_live.live_lists(root)}:
        raise Refusal(409, "no_such_list",
                      "no approved live-view list in approvals/ has that sha256").http()
    addr, why_not = _live_host(request)
    if addr is None:
        raise Refusal(502, "live_host_not_running", why_not or "no live-view host").http()
    try:
        r = sma_live.live_on(addr, body.sha256)
    except sma_live.LiveError as e:
        raise Refusal(502, "live_host_not_running", str(e)).http() from e
    if seat.audit is not None:
        seat.audit.append(AuditKind.COMMAND_EXECUTED, me.user_id, origin="console",
                          command="sma_live_on", list_sha256=body.sha256, outcome=r.outcome,
                          run_id=r.run_id)
    return LiveOnOut(outcome=r.outcome, run_id=r.run_id, reason=r.reason)  # type: ignore[arg-type]


@router.get("/inbox", response_model=list[InboxThreadOut], responses=ERRORS)
def list_inbox(store: AgentStoreDep) -> list[InboxThreadOut]:
    try:
        threads = store.list_inbox()
    except StoreError as e:
        raise _store_error(e).http() from e
    return [InboxThreadOut.model_validate(t.to_dict()) for t in threads]


@router.post(
    "/questions",
    status_code=201,
    response_model=QuestionSummaryOut,
    responses={403: {"description": "remote view or role (D16)"},
               409: {"description": "the store is read-only"},
               422: {"description": "empty text, unknown purpose"}},
)
def submit_question(body: QuestionIn, store: AgentStoreDep, me: Login, seat: Auth,
                    sessions: Sessions) -> QuestionSummaryOut:
    """Leave a question for a seat. The mock store only; operator on the microscope PC (D16)."""
    if why := server_action_why(me, "submit_question"):
        raise why.http()
    if not store.writable:
        raise READ_ONLY.http()
    try:
        q = store.submit_question(body.text, body.target, purpose=body.purpose,
                                  observable=body.observable)
    except ReadOnlyStoreError as e:
        raise READ_ONLY.http() from e
    except ValueError as e:
        raise _invalid(e).http() from e
    except StoreError as e:
        raise _store_error(e).http() from e
    if seat.audit is not None:
        cur = sessions.current
        seat.audit.append(AuditKind.QUESTION_SUBMITTED, me.user_id,
                          session_id=cur.info.session_id if cur is not None else None,
                          origin="console", target=body.target, qid=q.qid)
    return QuestionSummaryOut.model_validate(q.to_dict())
