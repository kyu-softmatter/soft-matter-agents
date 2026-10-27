"""Console area (PLAN.md F1, ui-spec 7.1, docs/screens/console.md): the agents' questions, runs
and inbox, read from the AgentStore, and the one write, a question request into the console's own
folder (card 010; `agents/requests.py`) or, for a question to the microscope or the simulation, an
item into that agent's `console_inbox/` (card 019; `agents/inbox_items.py`). A request in the
console's folder is not delivered: the librarian's inbox and "let the agents decide" have no place
the console may write into yet.

A run that soft-matter-agents' orchestrator is executing is followed through what it offers a
console (its plan.md 11-25; `agents/sma_run.py`): `GET .../stream` reads its events.jsonl,
`GET .../frame` asks its frame tap for the latest frame (it holds no core and never snaps;
OD-13), `POST .../stop` is the console's Abort for that run, sent on the run's own loopback
stop channel, and `POST /runs/stop` is "Stop all runs": the same stop to every running run, for
a screen with no login (card 004). The stop is a stop: the access middleware treats it as `abort` (from
the microscope PC always, from a logged-in remote viewer when remote abort is on, D13), and
it is sent only when a person presses it. Closing the page stops nothing (OD-30). Nothing is
written in the soft-matter-agents tree except the signed approval and an agent's inbox item.

Whether someone may ask is not decided here: the access middleware already refuses a remote or
logged-out write, and the route asks `server_action_why` for the T-018 permission `SUBMIT_QUESTION`
(operator on the microscope PC, D16) and puts a refusal in words. Records pass through as the store
has them: card contents, grades and `numbers` are not touched (PLAN.md §6 item 3).
"""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Literal

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from ...agents import (
    AGENTS,
    MockStore,
    NotFoundError,
    RunsFolderNotFoundError,
    StoreError,
    sma_live,
    sma_run,
)
from ...agents import inbox_items
from ...agents import requests as question_requests
from ...agents.schema_lite import Schemas
from ...agents.sma_files import RootNotFoundError, repository_root
from ...auth import AuditKind, TooManyAttempts
from ...signing.approval_writer import NO_APPROVALS_FOLDER, WRITTEN_MESSAGE, SigningRefused, write_approval
from . import (
    AgentStoreDep,
    Auth,
    Login,
    Refusal,
    command_why,
    logged_in_refusal,
    remote_view,
    server_action_why,
)

log = logging.getLogger("dino_autofocus.server.api.console")
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
        description="run_ended's how: completed, aborted_by_monitor, stopped_from_outside, failed, "
                    "refused")
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


class StopAllRunOut(BaseModel):
    run_id: str
    outcome: Literal["begun", "refused", "no_answer", "unreachable", "no_channel"] = Field(
        description="the stop channel's answer; `unreachable`: nothing answered a connection "
                    "(a run that crashed leaves a file that still says running); `no_channel`: "
                    "running, but announced no stop channel, so nothing was sent")
    message: str


class StopAllOut(BaseModel):
    message: str = Field(description="what happened, in words, for the lock screen")
    runs: list[StopAllRunOut]
    audited: bool = Field(description="every stop of this press was written to the audit log")


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


Addressee = Literal["agents_decide", "microscope", "simulation", "librarian"]


class QuestionRequestIn(BaseModel):
    """The words as typed and the Ask choice. Nothing else: the login, role and time are the
    server's, and no other key is accepted."""

    model_config = ConfigDict(extra="forbid")
    words: str = Field(max_length=question_requests.MAX_WORDS)
    addressed_to: Addressee


class ConsoleRoleOut(BaseModel):
    may_ask: bool
    may_draft: bool
    agents: list[Literal["microscope", "simulation", "librarian"]]
    may_ask_model_run: bool


class AskedByOut(BaseModel):
    login: str
    console_role: ConsoleRoleOut


class QuestionRequestOut(BaseModel):
    """`contracts/schemas/question_request.schema.json`, exactly: what was written."""

    artifact: Literal["question_request"]
    schema_version: Literal["0.1"]
    id: str
    words: str
    asked_by: AskedByOut
    asked_at: str
    addressed_to: Addressee


class AskerMarkOut(BaseModel):
    kind: Literal["other_login"]


class ConsoleQuestionOut(BaseModel):
    """`contracts/schemas/console_inbox_item.schema.json`'s `console_question`, exactly: the item that
    was written into the agent's inbox."""

    artifact: Literal["console_question"]
    schema_version: Literal["0.1"]
    item_id: str
    question_id: str
    words: str
    asked_by: AskedByOut
    asked_at: str
    asker_mark: AskerMarkOut
    attachments: list[Any]


class RequestCardOut(BaseModel):
    """A request written in the console's own folder, as a card. It is not delivered: the librarian
    and "let the agents decide" have no inbox the console writes into."""

    id: str
    words: str
    login: str
    asked_at: str
    addressed_to: Addressee
    state: str
    runs_wait_for_signature: bool


class ItemCardOut(BaseModel):
    """An item delivered to the microscope's or the simulation's inbox, as a card, with what its
    `console_answer` files say became of it."""

    item_id: str
    question_id: str
    agent: AgentName
    words: str
    login: str
    asked_at: str
    state: str
    runs_wait_for_signature: bool


class StepsOut(BaseModel):
    """The five steps of an agents' question, each from the file that says it is done."""

    asked: bool = Field(description="a goal card exists")
    designed: bool = Field(description="a plan card exists")
    signed: bool = Field(description="an approval for that plan's hash exists")
    run: bool = Field(description="a run log names the question")
    result: bool = Field(description="a result card exists")
    run_known: bool = Field(description="false when the runs folder could not be read: run is then not known")


class QuestionProgressOut(BaseModel):
    qid: str
    agent: AgentName
    title: str
    status: str | None
    created_at: str | None
    steps: StepsOut


class QuestionCardsOut(BaseModel):
    requests: list[RequestCardOut]
    items: list[ItemCardOut]
    questions: list[QuestionProgressOut]


class SigningStateOut(BaseModel):
    """What the sign dialog may offer to this login (console card 011). It decides the screen only."""

    person_named: bool = Field(description="the settings name the person's login (person_login)")
    is_person: bool = Field(description="this login is that login")
    practice: bool = Field(description="the mock store: a practice login is shown as signed, nothing is written")
    approvals_folder: bool = Field(description="microscope_runtime/approvals/ is in the tree this console reads")


class SignCheckIn(BaseModel):
    """The plan whose fingerprint was shown, and the password typed again. Nothing else."""

    model_config = ConfigDict(extra="forbid")
    qid: str
    plan_hash: str
    password: str


class SignCheckOut(BaseModel):
    outcome: Literal["written", "practice_signed"]
    message: str
    file_name: str | None = Field(default=None, description="the approval file written; none for practice")


class SuggestionOut(BaseModel):
    text: str
    kind: Literal["earlier question", "registered name"]


# -- refusals -----------------------------------------------------------------------------


def _not_found(e: NotFoundError) -> Refusal:
    return Refusal(404, "not_found", str(e))


def _invalid(e: ValueError) -> Refusal:
    return Refusal(422, "invalid", str(e))


READ_ONLY = Refusal(409, "read_only_store", READ_ONLY_MESSAGE)
REMOTE_ASK = ("Questions can be asked from the microscope computer only. This browser is "
              "viewing from another computer.")
VIEWER_ASK = "This login can only look: it cannot ask a question. An administrator can give it more."


def _ask_refusal(me: Any) -> Refusal | None:
    """`server_action_why` for asking, with the refusal said in words for the person."""
    why = server_action_why(me, "submit_question")
    if why is None:
        return None
    if why.code == "remote_view":
        return Refusal(403, "remote_view", REMOTE_ASK)
    if why.code == "role":
        return Refusal(403, "role", VIEWER_ASK)
    return why

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
    except RunsFolderNotFoundError as e:  # the runs cannot be seen: not an empty list (card 005)
        raise Refusal(404, "runs_not_found", str(e)).http() from e
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
               401: {"description": "logged out"},
               403: {"description": "not the person's login, or no login is named as the person's"},
               409: {"description": "not followed, ended, or no frame tap"},
               502: {"description": "the frame tap did not answer"}},
)
def run_frame(agent: AgentName, run_id: str, store: AgentStoreDep, me: Login,
              seat: Auth) -> Response:
    """The run's latest frame from its frame tap, which hands over a copy and commands
    nothing; the console opens no camera of its own (OD-13). A frame is the person's to see:
    any other login is refused here, before the tap is asked or the run is looked at
    (logged out and locked are refused for every route before this one is reached)."""
    state = _signing_state(store, me, seat)
    if not state.person_named:
        raise Refusal(403, "person_not_named",
                      "The person's login is not named yet, so no one is shown the camera.").http()
    if not state.is_person:
        raise Refusal(403, "not_person", "Only the person's own login is shown the camera.").http()
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


STOP_ALL_REASON = "Stop all runs pressed"
STOP_ALL_TAKES_NOTHING = ("stopping all runs takes no body and no query: the console decides "
                          "what to send, so nothing the request carries reaches a run")
STOP_ALL_WORKERS = 8
STOP_ALL_NO_RUNS_FOLDER = ("This project's runs folder was not found, so nothing was sent and it is "
                           "not known whether a run is running. Stop the run at the instrument or "
                           "in the operator terminal.")


def _stop_one(stream: sma_run.RunStream, reason: str) -> StopAllRunOut:
    """One run's outcome. Never raises: a run that cannot be stopped is reported, not hidden."""
    if stream.stop_channel is None:
        return StopAllRunOut(
            run_id=stream.run_id, outcome="no_channel",
            message=f"run {stream.run_id} is running but announced no stop channel: nothing was "
                    "sent; stop it at the instrument or in the operator terminal")
    try:
        result = sma_run.send_stop(stream, reason)
    except sma_run.SmaRunError as e:
        return StopAllRunOut(run_id=stream.run_id, outcome="unreachable", message=str(e))
    return StopAllRunOut(run_id=stream.run_id, outcome=result.outcome,  # type: ignore[arg-type]
                         message=result.message)


def _stop_all(store: Any, reason: str) -> list[StopAllRunOut]:
    """Every running microscope run gets the one line `send_stop` composes, all at once: a run
    that crashed and answers nobody must not make a live run wait for its timeout."""
    streams = store.running_microscope_runs()
    if not streams:
        return []
    with ThreadPoolExecutor(max_workers=min(STOP_ALL_WORKERS, len(streams))) as pool:
        return list(pool.map(lambda s: _stop_one(s, reason), streams))


def _stop_all_message(runs: list[StopAllRunOut]) -> str:
    if not runs:
        return "No run is running. Nothing was sent."
    begun = sum(r.outcome == "begun" for r in runs)
    rest = len(runs) - begun
    head = f"{len(runs)} running run{'s' if len(runs) != 1 else ''} found: {begun} began to abort"
    return head + (f", {rest} did not (see each run)." if rest else ".")


@router.post(
    "/runs/stop",
    response_model=StopAllOut,
    responses={400: {"description": "the request carried a body or a query"},
               401: {"description": "remote, or a remote viewer who is logged out"},
               403: {"description": "remote view with remote abort off (D13)"},
               404: {"description": "this project's runs folder was not found: not \"nothing running\""},
               409: {"description": "the console is not connected to the agents' files"}},
)
async def stop_all_runs(request: Request, store: AgentStoreDep, me: Login, seat: Auth) -> StopAllOut:
    """Stop every run soft-matter-agents is executing: the one stop line, on each running
    microscope run's own stop channel (card 004). From the microscope PC it needs no login, so a
    locked or logged-out console can stop; a remote viewer keeps D13. It takes nothing from the
    request: no body, no query, no run id and no reason, because the reason is composed here, and
    it opens no read. Every stop is written to the audit log."""
    remote_abort = getattr(request.app.state, "remote_abort", True)
    if why := command_why(me, "abort", remote_abort=remote_abort):
        raise why.http()
    if request.url.query or await request.body():
        raise Refusal(400, "stop_takes_nothing", STOP_ALL_TAKES_NOTHING).http()
    if getattr(store, "running_microscope_runs", None) is None:
        raise Refusal(409, "not_connected", NOT_SMA).http()
    who = me.user_id or "the microscope PC (no login)"
    try:
        runs = await run_in_threadpool(_stop_all, store, f"{STOP_ALL_REASON} (by {who})")
    except RunsFolderNotFoundError as e:
        # The one answer a stop must never give is "nothing is running" when the runs cannot be
        # seen (card 005). It is its own outcome, in words, and the press is still written down.
        _audit_stop_all(seat, me, who, [(None, "runs_folder_not_found")])
        raise Refusal(404, "runs_not_found", STOP_ALL_NO_RUNS_FOLDER).http() from e
    audited = _audit_stop_all(seat, me, who, [(r.run_id, r.outcome) for r in runs]
                              or [(None, "none_running")])
    return StopAllOut(message=_stop_all_message(runs), runs=runs, audited=audited)


def _audit_stop_all(seat: Any, me: Any, who: str, rows: list[tuple[str | None, str]]) -> bool:
    """One `sma_stop_all` line per row. False when the log did not take them; that never holds
    a stop back."""
    if seat.audit is None:
        return True
    try:
        for run_id, outcome in rows:
            seat.audit.append(AuditKind.COMMAND_EXECUTED, me.user_id, origin="console",
                              command="sma_stop_all", run_id=run_id, local=me.local, who=who,
                              outcome=outcome)
    except Exception:
        log.exception("the audit log did not take a stop-all entry")
        return False
    return True


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
        why = "no approved live-view list in the microscope's approvals/ folder (the person writes it)"
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
    "/question-requests",
    status_code=201,
    response_model=ConsoleQuestionOut | QuestionRequestOut,
    responses={403: {"description": "remote view or role (D16)"},
               409: {"description": "the agent's inbox is not there or is full for the day, or the id was taken five times"},
               422: {"description": "blank or too long words, an addressee that is not one of four"}},
)
def write_question_request(body: QuestionRequestIn, store: AgentStoreDep, me: Login,
                           seat: Auth) -> ConsoleQuestionOut | QuestionRequestOut:
    """A question to the microscope or the simulation is written as an item into that agent's
    inbox (`artifact` is `console_question`); one to the librarian or "let the agents decide" is
    written as a request into the console's own folder and is not delivered (`question_request`)."""
    if why := _ask_refusal(me):
        raise why.http()
    if not getattr(store, "writable", False) or not hasattr(store, "request_write_folder"):
        raise READ_ONLY.http()
    if body.addressed_to in inbox_items.INBOX_AGENTS:
        return _deliver(body, store, me, seat)
    folder = store.request_write_folder()
    doc: dict[str, Any] | None = None
    for _ in range(5):  # an id that is taken is never rewritten: ask for another
        try:
            doc = question_requests.build_request(
                words=body.words, login=me.info.user_id, role=str(me.info.role),
                addressed_to=body.addressed_to, now=question_requests.utc_now(),
                suffix=question_requests.random_suffix())
        except question_requests.RequestError as e:
            raise _invalid(e).http() from e
        try:
            question_requests.write_request(folder, doc)
            break
        except question_requests.RequestIdTaken:
            doc = None
        except StoreError as e:
            raise _store_error(e).http() from e
    if doc is None:
        raise Refusal(409, "request_exists", "A request with that id exists already. Try again.").http()
    if seat.audit is not None:  # the id and the addressee, never the words
        seat.audit.append(AuditKind.QUESTION_SUBMITTED, me.user_id, origin="console",
                          target=doc["addressed_to"], request=doc["id"])
    return QuestionRequestOut.model_validate(doc)


def _schemas(store: Any) -> Schemas:
    """The tree's own schemas, found as the instrument routes find them."""
    root = store.runtime_root() if hasattr(store, "runtime_root") else None
    if root is None:
        try:
            root = repository_root()
        except RootNotFoundError:
            root = None
    return Schemas(root / "contracts" / "schemas" if root is not None else "contracts/schemas")


def _has_inbox(store: Any) -> bool:
    return all(hasattr(store, n) for n in ("inbox_write_folder", "inbox_folders", "answers_folders",
                                           "outgoing_folder"))


def _deliver(body: QuestionRequestIn, store: Any, me: Any, seat: Any) -> ConsoleQuestionOut:
    if not _has_inbox(store):
        raise READ_ONLY.http()
    agent = body.addressed_to
    try:
        item = inbox_items.deliver(
            agent=agent, words=body.words, login=me.info.user_id, role=str(me.info.role),
            inbox=store.inbox_write_folder(agent), outgoing=store.outgoing_folder(),
            schemas=_schemas(store))
    except question_requests.RequestError as e:
        raise _invalid(e).http() from e
    except inbox_items.InboxError as e:
        raise Refusal(e.status, e.code, str(e)).http() from e
    except StoreError as e:
        raise _store_error(e).http() from e
    if seat.audit is not None:  # the agent and the ids, never the words
        seat.audit.append(AuditKind.QUESTION_SUBMITTED, me.user_id, origin="console", target=agent,
                          item_id=item["item_id"], question_id=item["question_id"])
    return ConsoleQuestionOut.model_validate(item)


@router.get("/suggestions", response_model=list[SuggestionOut], responses=ERRORS)
def suggestions(store: AgentStoreDep) -> list[SuggestionOut]:
    """What autocomplete may offer: the words of earlier requests and the registered quantity names,
    each labelled. Strings already on disk; never a model's completion, never the store's contents."""
    folders = store.request_folders() if hasattr(store, "request_folders") else []
    names = store.registered_names() if hasattr(store, "registered_names") else []
    found = question_requests.suggestions(question_requests.read_requests(folders), names)
    return [SuggestionOut(**s) for s in found]


def _steps(store: Any, agent: str, s: Any, qids_with_runs: set[str], run_known: bool) -> StepsOut:
    d = store.get_question(s.qid, s.latest_version)
    signed = d.plan is not None and d.plan_hash is not None and any(
        a.plan_hash == d.plan_hash and str(a.status or "").upper() == "APPROVED" for a in d.approvals)
    return StepsOut(asked=d.goal is not None, designed=d.plan is not None, signed=signed,
                    run=s.qid in qids_with_runs, result=bool(d.results), run_known=run_known)


@router.get("/question-cards", response_model=QuestionCardsOut, responses=ERRORS)
def question_cards(store: AgentStoreDep) -> QuestionCardsOut:
    """The cards below the question field: the items in the two inboxes, newest first, each with what
    the agent's answers say became of it; requests written in the console's own folder, newest first
    (each "written in the console · not delivered"); and the agents' questions on disk with their five
    steps. Reads only."""
    folders = store.request_folders() if hasattr(store, "request_folders") else []
    requests = [RequestCardOut(
        id=r["id"], words=r["words"], login=r["asked_by"]["login"], asked_at=r["asked_at"],
        addressed_to=r["addressed_to"], state=question_requests.NOT_DELIVERED,
        runs_wait_for_signature=True) for r in question_requests.read_requests(folders)]
    items = _item_cards(store)
    cards: list[QuestionProgressOut] = []
    try:
        for agent in AGENTS:
            try:
                with_runs = {r.qid for r in store.list_runs(agent) if r.qid}
                known = True
            except RunsFolderNotFoundError:  # the runs cannot be seen: not "no run"
                with_runs, known = set(), False
            for s in store.list_questions(agent):
                cards.append(QuestionProgressOut(
                    qid=s.qid, agent=s.agent, title=s.title, status=s.status, created_at=s.created_at,
                    steps=_steps(store, agent, s, with_runs, known)))
    except StoreError as e:
        raise _store_error(e).http() from e
    return QuestionCardsOut(requests=requests, items=items, questions=_newest_first(cards))


def _item_cards(store: Any) -> list[ItemCardOut]:
    if not _has_inbox(store):
        return []
    schemas = _schemas(store)
    found: list[tuple[str, dict[str, Any]]] = []
    for agent in inbox_items.INBOX_AGENTS:
        seen: set[str] = set()
        for folder in store.inbox_folders(agent):
            for item in inbox_items.read_items(folder, agent):
                if item["item_id"] not in seen:  # an earlier folder keeps its item over a later one's
                    seen.add(item["item_id"])
                    found.append((agent, item))
    return [ItemCardOut(
        item_id=item["item_id"], question_id=item["question_id"], agent=agent,  # type: ignore[arg-type]
        words=item["words"], login=item["asked_by"]["login"], asked_at=item["asked_at"],
        state=inbox_items.state_of(item, store.answers_folders(agent), schemas),
        runs_wait_for_signature=True) for agent, item in inbox_items.items_newest_first(found)]


# -- the sign dialog: practice writes nothing; a real tree goes through the approval writer (cards 011, 013) --

PRACTICE_MESSAGE = "Practice: this login is shown as signed. Nothing was written."


def _signing_state(store: Any, me: Any, seat: Any) -> SigningStateOut:
    named = seat.accounts.person_login()
    return SigningStateOut(
        person_named=named is not None,
        is_person=named is not None and me.info is not None and me.info.user_id == named,
        practice=isinstance(store, MockStore),
        approvals_folder=bool(store.approvals_target_present()) if hasattr(store, "approvals_target_present") else False)


@router.get("/signing", response_model=SigningStateOut)
def signing_state(store: AgentStoreDep, me: Login, seat: Auth) -> SigningStateOut:
    """Who may see Sign, and whether anything could be signed here. The screen only; the runtime
    decides from the person's own file (plan.md 6.1)."""
    if me.info is None:
        raise Refusal(401, "login_required", "log in first").http()
    return _signing_state(store, me, seat)


@router.post(
    "/sign-check",
    response_model=SignCheckOut,
    responses={401: {"description": "wrong password"}, 403: {"description": "not the person's login"},
               409: {"description": "the plan changed, or there is no approvals folder"},
               429: {"description": "too many wrong passwords"}},
)
def sign_check(body: SignCheckIn, request: Request, store: AgentStoreDep, me: Login,
               seat: Auth) -> SignCheckOut:
    """Sign the plan whose fingerprint the dialog showed, with the password typed again.

    Under the mock store a practice login is shown as signed and **nothing is written**. Under a real tree
    `signing.approval_writer` writes one approval into `microscope_runtime/approvals/` when every condition
    holds in this request, and otherwise refuses in words and writes nothing. The route keeps the name
    `sign-check` it was built under (card 011); it writes now."""
    if why := logged_in_refusal(me):
        raise why.http()
    if not me.local:
        raise remote_view("Signing is done at the microscope computer only.").http()
    state = _signing_state(store, me, seat)
    try:
        detail = store.get_question(body.qid)
    except NotFoundError as e:
        raise _not_found(e).http() from e
    except StoreError as e:
        raise _store_error(e).http() from e
    plan_card = detail.plan.data if detail.plan is not None and isinstance(detail.plan.data, dict) else None
    tree = store.runtime_root() if hasattr(store, "runtime_root") else None
    client = request.client.host if request.client else None
    login = me.info.user_id

    def password_is_right() -> bool:  # the login's own throttle: it raises TooManyAttempts, answered below
        return bool(seat.logins.check_password(login, body.password, client))

    try:
        if tree is None and not state.practice:
            raise SigningRefused(409, "no_approvals_folder", NO_APPROVALS_FOLDER)
        if state.practice:
            # same refusals as a real signing, then the password; nothing is written and nothing is looked up
            if not state.person_named:
                raise SigningRefused(403, "person_not_named", "The person's login is not named yet, so no one can sign.")
            if not state.is_person:
                raise SigningRefused(403, "not_person", "Only the person's own login signs.")
            if detail.plan_hash is None or detail.plan_hash != body.plan_hash:
                raise SigningRefused(409, "plan_changed", "The plan changed; review it again.")
            if not password_is_right():
                raise SigningRefused(401, "bad_credentials", "Wrong password.")
            written = None
        else:
            written = write_approval(
                tree=tree, practice=False, session_login=login, person_login=seat.accounts.person_login(),
                qid=body.qid, shown_plan_hash=body.plan_hash, plan_card=plan_card, check_password=password_is_right)
    except TooManyAttempts as e:
        return JSONResponse(  # type: ignore[return-value]  # same words and Retry-After as login and unlock
            {"detail": {"code": "too_many_attempts", "message": str(e)}}, status_code=429,
            headers={"X-DinoAF-Refusal": "too_many_attempts", "Retry-After": str(e.retry_after_s)})
    except SigningRefused as e:
        raise Refusal(e.status, e.code, e.message).http() from e
    if written is None:
        if seat.audit is not None:
            seat.audit.append(AuditKind.SIGN_CHECKED, login, origin="console", qid=body.qid,
                              plan_hash=body.plan_hash, outcome="practice_signed")
        return SignCheckOut(outcome="practice_signed", message=PRACTICE_MESSAGE)
    if seat.audit is not None:  # who, which plan and revision, which file: never a password or a hash of one
        seat.audit.append(AuditKind.APPROVAL_WRITTEN, login, origin="console", qid=written.qid,
                          plan_id=written.plan_id, plan_revision=written.plan_revision,
                          plan_hash=written.plan_hash, file_name=written.file_name)
    return SignCheckOut(outcome="written", message=WRITTEN_MESSAGE, file_name=written.file_name)
