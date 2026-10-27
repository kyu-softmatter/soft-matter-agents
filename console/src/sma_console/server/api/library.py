"""The Library screen's server side (console card 016; plan.md 4.3.1, 7.1.1): the librarian's generated pages.

Four routes, all reads. **Nothing of the store is shown but the generated files under `librarian_agent/kb/wiki/`
and the store's version** (`agents/library.py` is the only reader and takes nothing else). The console holds
no caller id, makes no query, keeps nothing and cites no page. There is no route that sends: the librarian's
inbox is open, but the console writes no item into it yet, so Send on every form answers in the browser that
nothing was sent. The answers list is the mock store's example answers, or "No answers yet." from a real tree.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from ...agents import MockStore, NotFoundError
from ...agents.library import Library
from . import AgentStoreDep, Refusal

router = APIRouter()

EXAMPLE_NOTE = ("This is example data: a copy of recorded files kept with the console, not from this "
                "microscope's librarian. Where each file came from is written in mock_data/SOURCE.md.")
EXAMPLE_ANSWERS_NOTE = ("These are example answers written for the console's practice data, not answers from any "
                        "librarian. Their names and numbers are made up.")
NO_ANSWERS = "No answers yet."


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Example(_Out):
    example: bool
    example_note: str | None


class Span(_Out):
    text: str
    code: bool
    page: str | None


class FactOut(_Out):
    label: str
    value: str


class LinkOut(_Out):
    label: str
    page: str
    kind: str
    entries: int | None


class GroupOut(_Out):
    key: str
    title: str
    links: list[LinkOut]


class IndexOut(Example):
    state: Literal["shown", "not_built", "not_generated"]
    message: str | None
    title: str | None
    facts: list[FactOut]
    groups: list[GroupOut]
    registered_unused: list[str]
    footer: str | None
    footer_version: str | None
    current_version: str | None
    behind: bool
    note: str | None


class BlockOut(_Out):
    type: Literal["heading", "paragraph", "quote", "list", "code", "table", "rule"]
    level: int | None = None
    text: str | None = None
    spans: list[Span] | None = None
    items: list[list[Span]] | None = None
    language: str | None = None
    header: list[list[Span]] | None = None
    rows: list[list[list[Span]]] | None = None


class PageOut(Example):
    page_id: str
    title: str
    blocks: list[BlockOut]
    footer: str
    footer_version: str
    current_version: str | None
    behind: bool
    note: str | None


class CoverageOut(_Out):
    E1: int
    E2: int
    E3: int
    E4: int
    E5: int


class SubjectOut(_Out):
    id: str
    kind: str
    page: str
    coverage: CoverageOut
    disputed: int


class MapOut(Example):
    state: Literal["not_built", "not_valid", "built"]
    message: str | None
    kb_version: str | None
    current_version: str | None
    behind: bool
    note: str | None
    footer: str | None
    subjects: list[SubjectOut]
    relations: list[dict[str, str]]
    evidence_page: bool


class NumberOut(_Out):
    name: str
    value: float | int | str
    unit: str
    entry_id: str
    grade: str
    source: str
    covers_conditions: str


class GapOut(_Out):
    asked_for: str
    looked_in: str


class AnswerOut(_Out):
    answer_id: str
    item_id: str
    answered_by: str
    answered_at: str
    outcome: str
    reason: str
    kb_version: str | None
    answer: str | None
    entries_cited: list[str]
    numbers: list[NumberOut]
    gaps: list[GapOut]
    entries_marked: list[str]
    other_side: list[str]
    quantity_name: str | None
    entries_made: list[str]
    example: bool


class AnswersOut(Example):
    answers: list[AnswerOut]
    message: str | None


# -- helpers ----------------------------------------------------------------------------------------


def _example(store: Any) -> tuple[bool, str | None]:
    return (True, EXAMPLE_NOTE) if isinstance(store, MockStore) else (False, None)


def _library(store: Any) -> Library:
    return Library(store.library_root())


def _str_list(x: Any) -> list[str]:
    return [s for s in x if isinstance(s, str)] if isinstance(x, list) else []


def _answer(doc: dict[str, Any], example: bool) -> AnswerOut:
    numbers = [NumberOut(**{k: n.get(k) for k in NumberOut.model_fields})
               for n in doc.get("numbers", []) if isinstance(n, dict)]
    gaps = [GapOut(asked_for=str(g.get("asked_for", "")), looked_in=str(g.get("looked_in", "")))
            for g in doc.get("gaps", []) if isinstance(g, dict)]
    return AnswerOut(
        answer_id=str(doc.get("answer_id", "")), item_id=str(doc.get("item_id", "")),
        answered_by=str(doc.get("answered_by", "")), answered_at=str(doc.get("answered_at", "")),
        outcome=str(doc.get("outcome", "")), reason=str(doc.get("reason", "")),
        kb_version=doc.get("kb_version") if isinstance(doc.get("kb_version"), str) else None,
        answer=doc.get("answer") if isinstance(doc.get("answer"), str) else None,
        entries_cited=_str_list(doc.get("entries_cited")), numbers=numbers, gaps=gaps,
        entries_marked=_str_list(doc.get("entries_marked")), other_side=_str_list(doc.get("other_side")),
        quantity_name=doc.get("quantity_name") if isinstance(doc.get("quantity_name"), str) else None,
        entries_made=_str_list(doc.get("entries_made")), example=example)


# -- routes -----------------------------------------------------------------------------------------


@router.get("/index", response_model=IndexOut)
def index(store: AgentStoreDep) -> IndexOut:
    """The wiki's front page, grouped by the kind of data, as generated. Reads only."""
    example, note = _example(store)
    return IndexOut(example=example, example_note=note, **_library(store).index())


@router.get("/pages/{page_id}", response_model=PageOut, responses={404: {"description": "not a generated page"}})
def page(page_id: str, store: AgentStoreDep) -> PageOut:
    """One generated wiki page as it stands, with a note when it was built from an older version of the store."""
    example, note = _example(store)
    try:
        got = _library(store).page(page_id)
    except NotFoundError as e:
        raise Refusal(404, "page_not_found", str(e)).http() from None
    return PageOut(example=example, example_note=note, **got)


@router.get("/map", response_model=MapOut)
def data_map(store: AgentStoreDep) -> MapOut:
    """The data map the librarian generated, as counts. The console computes nothing from it."""
    example, note = _example(store)
    return MapOut(example=example, example_note=note, **_library(store).map())


@router.get("/answers", response_model=AnswersOut)
def answers(store: AgentStoreDep) -> AnswersOut:
    """The librarian's answers: example answers under the mock store, none from a real tree yet."""
    example, _ = _example(store)
    note = EXAMPLE_ANSWERS_NOTE if example else None
    found = [_answer(d, example) for d in store.library_answers()]
    return AnswersOut(example=example, example_note=note, answers=found, message=None if found else NO_ANSWERS)
