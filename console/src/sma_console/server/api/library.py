"""The Library screen's server side (console cards 016 and 020; plan.md 4.3.1, 7.1.1): the librarian's generated
pages, and the requests sent to its inbox with the answers read back.

**Of the store, the pages shown are the generated files under `librarian_agent/kb/wiki/` and the store's version**
(`agents/library.py` is the only reader and takes nothing else). The console holds no caller id, makes no query,
keeps nothing and cites no page. Four routes read: the index, a page, the map and the answers. Two more carry
requests: `POST /requests` writes one item into the librarian's `console_inbox/` (with the one file it may
attach, travelling inside the JSON body), and `GET /requests` lists what is in that inbox with the answers that
name each, read from `librarian_agent/answers/`. Nothing else of the librarian's tree is written, and an
attached file is never opened, served or read back. Under the mock store the answers and requests listed are
the sample's examples and are marked as such; a request made there lands in the practice folder.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from ...agents import MockStore, NotFoundError
from ...agents import requests as question_requests
from ...agents.library import Library
from . import AgentStoreDep, Auth, Login, Refusal
from ._store_requests import (
    NO_REQUESTS,
    AnswerOut,
    FileIn,
    RequestViewOut,
    StoreRequestOut,
    UnreadableOut,
    answer_out,
    deliver_store_request,
    request_views,
)

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


class AnswersOut(Example):
    answers: list[AnswerOut]
    message: str | None


class RequestIn(BaseModel):
    """The words as typed, the request as the form builds it (without the field that holds the words), and the
    one file it may carry. Nothing else is accepted."""

    model_config = ConfigDict(extra="forbid")
    words: str = Field(max_length=question_requests.MAX_WORDS)
    request: dict[str, Any]
    file: FileIn | None = None


class RequestsOut(Example):
    requests: list[RequestViewOut]
    orphans: list[UnreadableOut]
    message: str | None


# -- helpers ----------------------------------------------------------------------------------------


def _example(store: Any) -> tuple[bool, str | None]:
    return (True, EXAMPLE_NOTE) if isinstance(store, MockStore) else (False, None)


def _library(store: Any) -> Library:
    return Library(store.library_root())


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
    """The librarian's answers that can be read: the sample's examples under the mock store, else those in
    `librarian_agent/answers/` that name a request in the inbox and match it."""
    example, _ = _example(store)
    note = EXAMPLE_ANSWERS_NOTE if example else None
    found = [answer_out(d, example) for d in store.library_answers()]
    return AnswersOut(example=example, example_note=note, answers=found, message=None if found else NO_ANSWERS)


@router.get("/requests", response_model=RequestsOut)
def requests_list(store: AgentStoreDep) -> RequestsOut:
    """The requests in the librarian's inbox, newest first, each with its answers and a state in words; and the
    answers on disk that name no request there. Reads only: a file attached to a request is shown as a name."""
    example, _ = _example(store)
    views, orphans = request_views(store)
    return RequestsOut(example=example, example_note=EXAMPLE_ANSWERS_NOTE if example else None,
                       requests=views, orphans=orphans, message=None if views or orphans else NO_REQUESTS)


@router.post(
    "/requests",
    status_code=201,
    response_model=StoreRequestOut,
    responses={403: {"description": "remote view or role (D16)"},
               409: {"description": "the librarian's inbox is not there, or the id was taken five times"},
               422: {"description": "words, request or file that cannot be sent"}},
)
def send_request(body: RequestIn, store: AgentStoreDep, me: Login, seat: Auth) -> StoreRequestOut:
    """Write one request into the librarian's inbox, with the file it names beside it, and return the item
    written. The form's words are sent once, as `words`; the server puts them in the request's own field."""
    return deliver_store_request(store, me, seat, words=body.words, request=body.request, file=body.file)
