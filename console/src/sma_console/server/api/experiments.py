"""The Experiments screens' server side (console card 014; plan.md 15, 15.1): show, and offer one request.

Everything here is read from the tree's files through the store: the plan cards, the approvals, the runs and
their hand-step sheets. **It starts nothing and writes nothing.** The one write route, `POST /run`, builds the
request a Run button would send (the sha256 of the approval file's raw bytes, the schema's `run_request`) and
answers that it is not built yet: the runtime has no part that receives it. Under the mock store every answer
says it is example data and where the files came from. This module reads nothing of the librarian's and holds
no caller id.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from ...agents import MockStore, StoreError, experiments, instruments
from ...agents.sma_files import plan_hash
from . import AgentStoreDep, Auth, Login, Refusal, logged_in_refusal, remote_view

router = APIRouter()

EXAMPLE_NOTE = ("This is example data: a copy of recorded files kept with the console, not from any "
                "run at this microscope. Where each file came from is written in mock_data/SOURCE.md.")
DRAFTS_NOTE = ("Drafts are not saved yet: where a console draft lives is still to be designed. "
               "A draft you make below is shown and then gone.")
SAMPLE_MESSAGE = "No sample record yet: where a sample's record lives is still being designed."
MAP_MESSAGE = ("The sample map is not built yet: it needs parts the runtime does not have. "
               "Nothing is drawn, flagged or confirmed here.")
RUN_NOT_BUILT = ("Run is not built yet: the runtime has no part that receives this request, "
                 "so nothing is sent.")
EXAMPLE_RUN = " This is example data: nothing here can start anything."
_LOADING = re.compile(r"(?<![a-z])load", re.IGNORECASE)


# -- what the screens receive ----------------------------------------------------------------------


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlanApprovalOut(_Out):
    name: str
    id: str | None
    approved_by: str | None
    approved_at: str | None
    signed_through: dict[str, str] | None
    signed_words: str


class VoidApprovalOut(_Out):
    name: str
    why: str


class RunOfferOut(_Out):
    offered: bool
    why_not: str | None
    approval_name: str | None
    approval_sha256: str | None
    built: Literal[False] = False
    message: str


class PlanOut(_Out):
    plan_id: str
    revision: int | None
    qid: str
    version: int
    card_name: str
    status: str | None
    state: Literal["draft", "waiting_for_signature", "approved", "running", "ended"]
    state_words: str
    plan_hash: str
    approval: PlanApprovalOut | None
    void_approvals: list[VoidApprovalOut]
    run_ids: list[str]
    run_offer: RunOfferOut


class RunApprovalOut(_Out):
    id: str | None
    kind: str | None
    sha256: str | None
    signed_through: dict[str, str] | None
    signed_words: str


class EventsOut(_Out):
    count: int
    words: str


class HandStepOut(_Out):
    sheet_id: str
    channel: str
    element: str | None
    instruction: str
    opened_at: str | None
    confirmed: bool
    confirmed_at: str | None
    confirmed_by: str | None
    observed: str | None


class RunOut(_Out):
    run_id: str
    plan_id: str | None
    qid: str | None
    plan_on_disk: bool
    state: Literal["running", "ended"]
    how: str | None
    how_words: str | None
    started_at: str | None
    finished_at: str | None
    approval: RunApprovalOut | None
    refusal: str | None
    events: EventsOut
    hand_steps: list[HandStepOut]
    waiting_line: str | None
    tweezers_note: str | None


class PlansOut(_Out):
    example: bool
    example_note: str | None
    drafts_note: str
    plans: list[PlanOut]
    runs: list[RunOut]
    problems: list[str]


class LoadingCheckOut(_Out):
    run_id: str
    sheet_id: str
    confirmed_at: str | None
    confirmed_by: str | None
    words: str


class SampleOut(_Out):
    example: bool
    example_note: str | None
    record: None
    message: str
    loading_checks: list[LoadingCheckOut]


class SampleMapOut(_Out):
    example: bool
    example_note: str | None
    parts: list[dict[str, str]]
    example_map: None
    moves: list[Any]
    flags: list[Any]
    candidates: list[Any]
    message: str


class RunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_id: str
    plan_revision: int


class RunNotBuiltOut(_Out):
    outcome: Literal["not_built"]
    message: str
    would_send: dict[str, str]


# -- reading the tree ---------------------------------------------------------------------------------


@dataclass
class _Found:
    """What the tree holds, as the screens need it. Built per request; nothing is kept."""

    plans: list[PlanOut] = field(default_factory=list)
    runs: list[RunOut] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def _example(store: Any) -> tuple[bool, str | None]:
    return (True, EXAMPLE_NOTE) if isinstance(store, MockStore) else (False, None)


def _signed_mark(raw: Any) -> dict[str, str] | None:
    if isinstance(raw, dict) and raw.get("via") == "console" and isinstance(raw.get("login"), str):
        return {"via": "console", "login": raw["login"]}
    return None


def _run_row(store: Any, summary: Any, plan_ids: set[str]) -> RunOut:
    detail = store.get_run("microscope", summary.run_id)
    log = detail.records.get("log.json")
    log = log if isinstance(log, dict) else {}
    stream = instruments._followed_stream(store, summary.run_id)
    if log:
        events = [e for e in log.get("events", []) if isinstance(e, dict)]
    else:
        events = list(stream.events) if stream is not None else []
    running = summary.status == "running"
    how: str | None = None
    if not running:
        if isinstance(log.get("ended"), str):
            how = log["ended"]
        elif stream is not None and stream.ended_how is not None:
            how = stream.ended_how
        else:
            how = summary.status
    approval = _run_approval(log.get("approval"))
    steps = _hand_steps(store, summary.run_id)
    waiting = experiments.WAITING_LINE if any(not s.confirmed for s in steps) and how is None else None
    n = len(events)
    return RunOut(
        run_id=summary.run_id, plan_id=summary.plan_id, qid=summary.qid,
        plan_on_disk=summary.plan_id in plan_ids, state="running" if running else "ended",
        how=how, how_words=experiments.ended_words(how), started_at=summary.created_at,
        finished_at=summary.finished_at, approval=approval,
        refusal=log["refusal"] if isinstance(log.get("refusal"), str) else None,
        events=EventsOut(count=n, words=f"{n} event{'' if n == 1 else 's'} recorded"),
        hand_steps=[HandStepOut(**s.as_dict()) for s in steps], waiting_line=waiting,
        tweezers_note=experiments.tweezers_note(how, events))


def _run_approval(raw: Any) -> RunApprovalOut | None:
    if not isinstance(raw, dict) or raw.get("id") is None:
        return None
    file = raw.get("file") if isinstance(raw.get("file"), dict) else None
    if file is None:
        return RunApprovalOut(id=raw["id"], kind=raw.get("kind"), sha256=None, signed_through=None,
                              signed_words=f"approval {raw['id']} (how it was signed is not in this "
                                           "run's record)")
    mark = _signed_mark(file.get("signed_through"))
    sha = file.get("sha256")
    return RunApprovalOut(id=raw["id"], kind=raw.get("kind"), sha256=sha if isinstance(sha, str) else None,
                          signed_through=mark, signed_words=experiments.signed_words(mark))


def _hand_steps(store: Any, run_id: str) -> list[experiments.ManualStep]:
    reader = getattr(store, "read_run_text", None)
    if reader is None:
        return []
    try:
        text = reader("microscope", run_id, "manual_steps.md")
    except StoreError:
        return []
    return experiments.parse_manual_steps(text) if text else []


def _gather(store: Any, me: Any, seat: Any) -> _Found:
    found = _Found()
    cards: list[tuple[Any, dict[str, Any], str, int]] = []
    seen: set[str] = set()
    try:
        questions = store.list_questions("microscope")
    except StoreError as e:
        found.problems.append(f"The questions could not be read: {e}")
        questions = []
    for q in questions:
        for v in sorted(q.versions, reverse=True):
            try:
                plan = store.get_question(q.qid, v).plan
            except StoreError as e:
                found.problems.append(f"{q.qid} version {v} could not be read: {e}")
                continue
            if plan is None or not isinstance(plan.data, dict) or not isinstance(plan.data.get("id"), str):
                continue
            if plan.data["id"] in seen:
                continue
            seen.add(plan.data["id"])
            cards.append((plan, plan.data, q.qid, v))
    try:
        approvals = [a for a in store.list_approvals("microscope") if isinstance(a.data, dict)]
    except StoreError as e:
        found.problems.append(f"The approvals could not be read: {e}")
        approvals = []
    try:
        summaries = store.list_runs("microscope")
    except StoreError as e:
        found.problems.append(f"The runs could not be read: {e}")
        summaries = []
    for s in summaries:
        try:
            found.runs.append(_run_row(store, s, seen))
        except StoreError as e:
            found.problems.append(f"{s.run_id} could not be read: {e}")
    for card, data, qid, version in cards:
        found.plans.append(_plan_row(store, me, seat, card, data, qid, version, approvals, found.runs))
    found.plans.sort(key=lambda p: (p.qid, p.version, p.plan_id), reverse=True)
    return found


def _plan_row(store: Any, me: Any, seat: Any, card: Any, data: dict[str, Any], qid: str, version: int,
              approvals: list[Any], runs: list[RunOut]) -> PlanOut:
    covering = None
    void: list[VoidApprovalOut] = []
    for a in approvals:  # newest first
        judged = experiments.judge_approval(data, a.data)
        if judged.covers:
            covering = covering or (a, judged)
        elif judged.relevant:
            void.append(VoidApprovalOut(name=a.name, why=judged.why_void or "it does not cover this plan"))
    mine = [r for r in runs if r.plan_id == data["id"]]
    if any(r.state == "running" for r in mine):
        state = "running"
    elif any(r.how != "refused" for r in mine):
        state = "ended"
    elif covering:
        state = "approved"
    elif card.status == "VALIDATED" or data.get("status") == "VALIDATED":
        state = "waiting_for_signature"
    else:
        state = "draft"
    approval = None
    if covering:
        a, judged = covering
        approval = PlanApprovalOut(name=a.name, id=a.id, approved_by=a.approved_by, approved_at=a.approved_at,
                               signed_through=judged.signed_through,
                               signed_words=experiments.signed_words(judged.signed_through))
    return PlanOut(
        plan_id=data["id"], revision=data.get("revision") if isinstance(data.get("revision"), int) else None,
        qid=qid, version=version, card_name=card.name, status=card.status or data.get("status"),
        state=state, state_words=experiments.STATE_WORDS[state], plan_hash=plan_hash(data),
        approval=approval, void_approvals=void, run_ids=[r.run_id for r in mine],
        run_offer=_offer(store, me, seat, state, approval))


def _offer(store: Any, me: Any, seat: Any, state: str, approval: PlanApprovalOut | None) -> RunOfferOut:
    """Whether the Run button is shown: an approved plan, its approval file on disk, the person at the
    microscope computer. It is shown and sends nothing: the runtime has no part that receives it."""
    sha = None
    if approval is not None and hasattr(store, "approval_file_sha256"):
        sha = store.approval_file_sha256("microscope", approval.name)
    message = RUN_NOT_BUILT + (EXAMPLE_RUN if isinstance(store, MockStore) else "")
    why = None
    if state != "approved":
        why = f"Only an approved plan can be run; this one is {experiments.STATE_WORDS[state]}."
    elif sha is None:
        why = "The approval file is not on disk, so there is nothing to point a run at."
    elif me.info is None:
        why = "Log in first."
    elif not me.local:
        why = "Run is offered at the microscope computer only; this browser is viewing from another computer."
    else:
        named = seat.accounts.person_login()
        if named is None:
            why = "The person's login is not named yet, so no one can run."
        elif me.info.user_id != named:
            why = "Only the person's own login runs a plan."
    return RunOfferOut(offered=why is None, why_not=why, approval_name=approval.name if approval else None,
                       approval_sha256=sha, message=message)


# -- routes ----------------------------------------------------------------------------------------------


@router.get("/plans", response_model=PlansOut)
def plans(store: AgentStoreDep, me: Login, seat: Auth) -> PlansOut:
    """Every plan on disk with where it stands, and every run with how it ended. Reads only."""
    example, note = _example(store)
    found = _gather(store, me, seat)
    return PlansOut(example=example, example_note=note, drafts_note=DRAFTS_NOTE, plans=found.plans,
                    runs=found.runs, problems=found.problems)


@router.post("/run", response_model=RunNotBuiltOut,
             responses={403: {"description": "not the person's login, or not at the microscope"},
                        404: {"description": "no such plan"}, 409: {"description": "the plan is not approved"}})
def run(body: RunIn, store: AgentStoreDep, me: Login, seat: Auth) -> RunNotBuiltOut:
    """What the Run button would send for this plan, and that it is not built yet. **Sends nothing and
    writes nothing**: there is no live-view host request in the console until the runtime receives it."""
    if why := logged_in_refusal(me):
        raise why.http()
    if not me.local:
        raise remote_view("Run is offered at the microscope computer only.").http()
    named = seat.accounts.person_login()
    if named is None:
        raise Refusal(403, "person_not_named", "The person's login is not named yet, so no one can run.").http()
    if me.info.user_id != named:
        raise Refusal(403, "not_person", "Only the person's own login runs a plan.").http()
    found = _gather(store, me, seat)
    plan = next((p for p in found.plans if p.plan_id == body.plan_id and p.revision == body.plan_revision), None)
    if plan is None:
        raise Refusal(404, "plan_not_found", "No plan on disk has that id and revision.").http()
    offer = plan.run_offer
    if not offer.offered or offer.approval_sha256 is None:
        raise Refusal(409, "not_approved", offer.why_not or "The plan is not approved.").http()
    return RunNotBuiltOut(outcome="not_built", message=offer.message,
                          would_send=experiments.run_request(offer.approval_sha256))


@router.get("/sample", response_model=SampleOut)
def sample(store: AgentStoreDep, me: Login) -> SampleOut:
    """The sample's record view: there is no record yet, and where one lives is still being designed. A
    loading check a run's hand-step sheet holds (a confirmed step that mentions loading: a guess at what
    the sheet's wording means) is shown with the run it came from."""
    example, note = _example(store)
    checks: list[LoadingCheckOut] = []
    try:
        summaries = store.list_runs("microscope")
    except StoreError:
        summaries = []
    for s in summaries:
        for step in _hand_steps(store, s.run_id):
            if step.confirmed and _LOADING.search(f"{step.channel} {step.instruction}"):
                checks.append(LoadingCheckOut(
                    run_id=s.run_id, sheet_id=step.sheet_id, confirmed_at=step.confirmed_at,
                    confirmed_by=step.confirmed_by,
                    words=f"done at the microscope, from {s.run_id}'s hand-step sheet"))
    return SampleOut(example=example, example_note=note, record=None, message=SAMPLE_MESSAGE,
                     loading_checks=checks)


@router.get("/sample-map", response_model=SampleMapOut)
def sample_map(store: AgentStoreDep, me: Login) -> SampleMapOut:
    """The sample map: every part says it is not built and why. Nothing is drawn: no move, no flag, no
    candidate, and a model's guess is never shown as one."""
    example, note = _example(store)
    return SampleMapOut(example=example, example_note=note, parts=experiments.SAMPLE_MAP_PARTS,
                        example_map=None, moves=[], flags=[], candidates=[], message=MAP_MESSAGE)
