"""AgentStore: what the agent console (F1) reads, and the one thing it may write.

The console shows the questions, runs and inbox threads of the two soft-matter-agents seats,
microscope and simulation. Two stores implement the protocol: `SmaFiles` reads the
soft-matter-agents files and never writes, and `MockStore` reads a copied sample and writes
submitted questions to a folder of its own.

Every record here is a plain dataclass that `to_dict` turns into JSON-ready data and
`from_dict` turns back, so a server can send it as it is. A card's file content is kept whole
in `Card.data`: grades, `numbers` and anything else the console does not understand pass
through untouched, and the UI picks the fields it shows. Only status and times are lifted
out, so that a list can be drawn without opening the cards.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

Agent = Literal["microscope", "simulation"]
AGENTS: tuple[Agent, ...] = ("microscope", "simulation")

QID_PREFIX: dict[Agent, str] = {"microscope": "mic", "simulation": "sim"}
QID_RE = re.compile(r"^(mic|sim)-[0-9]{8}-[0-9]{3}$")


class StoreError(Exception):
    """Base for errors raised by a store."""


class ReadOnlyStoreError(StoreError):
    """The store reads files that belong to someone else and writes nothing."""


class NotFoundError(StoreError, KeyError):
    """No question, run or version by that name."""

    def __str__(self) -> str:  # KeyError would print the repr of the message
        return str(self.args[0]) if self.args else ""


def agent_of_qid(qid: str) -> Agent:
    """`mic-...` -> microscope, `sim-...` -> simulation."""
    m = QID_RE.match(qid)
    if not m:
        raise NotFoundError(f"not a question id: {qid!r}")
    return "microscope" if m.group(1) == "mic" else "simulation"


def check_agent(agent: str) -> Agent:
    if agent not in AGENTS:
        raise ValueError(f"agent must be one of {AGENTS}, got {agent!r}")
    return agent  # type: ignore[return-value]


@dataclass(frozen=True)
class FileInfo:
    name: str
    size: int | None  # None: the folder lists it but the file system cannot stat it

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FileInfo:
        return cls(name=d["name"], size=d.get("size"))


@dataclass(frozen=True)
class Card:
    """One JSON card file of a question, as written by its seat."""

    name: str  # file name, e.g. "v3_goal.json"
    kind: str  # the card's own "card" field, else guessed from the file name
    version: int  # 1 for an unprefixed file, N for a "vN_" prefix
    status: str | None
    created_at: str | None
    data: Any  # the file's content, untouched

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Card:
        return cls(
            name=d["name"],
            kind=d["kind"],
            version=d["version"],
            status=d.get("status"),
            created_at=d.get("created_at"),
            data=d.get("data"),
        )


@dataclass(frozen=True)
class Document:
    """A text file beside the cards (the seats write a markdown copy for people)."""

    name: str
    version: int
    text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Document:
        return cls(name=d["name"], version=d["version"], text=d["text"])


@dataclass(frozen=True)
class QuestionSummary:
    qid: str
    agent: Agent
    title: str
    status: str | None  # of the newest card in the latest version
    created_at: str | None  # earliest card
    updated_at: str | None  # newest card
    latest_version: int
    versions: list[int]
    source: str  # "soft-matter-agents", "mock", "mock-submitted"
    # read from the goal (else the plan) of the latest version, else the first; None if absent
    purpose: str | None = None
    intent: str | None = None
    observable_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> QuestionSummary:
        return cls(
            qid=d["qid"],
            agent=d["agent"],
            title=d["title"],
            status=d.get("status"),
            created_at=d.get("created_at"),
            updated_at=d.get("updated_at"),
            latest_version=d["latest_version"],
            versions=list(d["versions"]),
            source=d["source"],
            purpose=d.get("purpose"),
            intent=d.get("intent"),
            observable_name=d.get("observable_name"),
        )


@dataclass(frozen=True)
class Approval:
    """One `plan_approval` card of a seat's `approvals/` folder, as the person wrote it.

    `plan_found` says whether a plan card of the question hashes to the approval's
    `plan_hash` (the hash of the plan with `status` removed, as the seats and the validator
    compute it): True, False, or None when the question folder is not there.
    """

    name: str  # file name, e.g. "appr-mic-20260925-002-r2.json"
    agent: Agent
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
    plan_found: bool | None = None
    data: Any = None  # the file's content, untouched

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Approval:
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__})


@dataclass(frozen=True)
class QuestionDetail:
    """The cards of one version of a question.

    A version holds only the files written under its prefix: when a seat revised the axes
    alone, that version has no goal, and the goal is read from the version that has it.
    Nothing is carried forward, because a card left out of a revision may have been
    withdrawn rather than kept (a refusal of version 1 does not stand in version 2).
    """

    summary: QuestionSummary
    version: int
    goal: Card | None
    axes: list[Card]
    plan: Card | None
    synthesis: Card | None
    refusals: list[Card]
    results: list[Card]
    others: list[Card]  # cards of any other kind, and a second plan or synthesis
    documents: list[Document]
    files: list[FileInfo]  # what is not a card or a document (images, jsonl), not opened
    plan_hash: str | None = None  # of this version's plan card, status removed
    approvals: list[Approval] = field(default_factory=list)  # every approval naming the qid

    @property
    def refusal(self) -> Card | None:
        return self.refusals[-1] if self.refusals else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary.to_dict(),
            "version": self.version,
            "goal": _opt(self.goal),
            "axes": [c.to_dict() for c in self.axes],
            "plan": _opt(self.plan),
            "synthesis": _opt(self.synthesis),
            "refusals": [c.to_dict() for c in self.refusals],
            "results": [c.to_dict() for c in self.results],
            "others": [c.to_dict() for c in self.others],
            "documents": [x.to_dict() for x in self.documents],
            "files": [x.to_dict() for x in self.files],
            "plan_hash": self.plan_hash,
            "approvals": [a.to_dict() for a in self.approvals],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> QuestionDetail:
        def card(x: dict[str, Any] | None) -> Card | None:
            return None if x is None else Card.from_dict(x)

        return cls(
            summary=QuestionSummary.from_dict(d["summary"]),
            version=d["version"],
            goal=card(d.get("goal")),
            axes=[Card.from_dict(x) for x in d["axes"]],
            plan=card(d.get("plan")),
            synthesis=card(d.get("synthesis")),
            refusals=[Card.from_dict(x) for x in d["refusals"]],
            results=[Card.from_dict(x) for x in d["results"]],
            others=[Card.from_dict(x) for x in d["others"]],
            documents=[Document.from_dict(x) for x in d["documents"]],
            files=[FileInfo.from_dict(x) for x in d["files"]],
            plan_hash=d.get("plan_hash"),
            approvals=[Approval.from_dict(x) for x in d.get("approvals", [])],
        )


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    agent: Agent
    qid: str | None
    plan_id: str | None
    status: str | None  # the log's outcome
    created_at: str | None  # the log's t0_wall
    finished_at: str | None
    backend: str | None
    source: str
    approval_kind: str | None = None  # the log's (else the config's) approval.kind

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RunSummary:
        return cls(
            run_id=d["run_id"],
            agent=d["agent"],
            qid=d.get("qid"),
            plan_id=d.get("plan_id"),
            status=d.get("status"),
            created_at=d.get("created_at"),
            finished_at=d.get("finished_at"),
            backend=d.get("backend"),
            source=d["source"],
            approval_kind=d.get("approval_kind"),
        )


@dataclass(frozen=True)
class RunDetail:
    """A run's record files.

    microscope: commands.json, log.json (and deviations.json when present);
    simulation: config.json, log.json, observables.json, trajectory_meta.json.
    The trajectory itself and any file over the store's size limit are listed, not opened.
    """

    summary: RunSummary
    records: dict[str, Any]  # file name -> content, untouched
    files: list[FileInfo]  # every file in the run folder
    not_opened: list[str] = field(default_factory=list)  # records over the limit or unreadable

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary.to_dict(),
            "records": dict(self.records),
            "files": [x.to_dict() for x in self.files],
            "not_opened": list(self.not_opened),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RunDetail:
        return cls(
            summary=RunSummary.from_dict(d["summary"]),
            records=dict(d["records"]),
            files=[FileInfo.from_dict(x) for x in d["files"]],
            not_opened=list(d.get("not_opened", [])),
        )


@dataclass(frozen=True)
class InboxMessage:
    """One round file in a seat's inbox, e.g. `r2_ask_experiment.json`."""

    name: str
    round: int | None
    kind: str  # "ask_experiment" from "r2_ask_experiment.json"
    card: Any  # JSON content, or None for a text file
    text: str | None  # markdown content, or None for a JSON file

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> InboxMessage:
        return cls(
            name=d["name"],
            round=d.get("round"),
            kind=d["kind"],
            card=d.get("card"),
            text=d.get("text"),
        )


@dataclass(frozen=True)
class InboxThread:
    """A bridge thread: the bridge's status and the messages a seat received on it."""

    thread: str
    agent: Agent | None  # whose inbox holds it; None when only the bridge has it
    state: str | None  # from the bridge's status.json
    turn: str | None
    round: int | None
    updated_at: str | None
    status: Any  # the bridge's status.json, untouched, or None
    messages: list[InboxMessage]
    source: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["messages"] = [m.to_dict() for m in self.messages]
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> InboxThread:
        return cls(
            thread=d["thread"],
            agent=d.get("agent"),
            state=d.get("state"),
            turn=d.get("turn"),
            round=d.get("round"),
            updated_at=d.get("updated_at"),
            status=d.get("status"),
            messages=[InboxMessage.from_dict(m) for m in d["messages"]],
            source=d["source"],
        )


def _opt(c: Card | None) -> dict[str, Any] | None:
    return None if c is None else c.to_dict()


@runtime_checkable
class AgentStore(Protocol):
    """What the console reads. Lists are newest first.

    `writable` says whether `submit_question` can succeed, so a caller need not test the
    class: MockStore True, SmaFiles False.
    """

    writable: bool

    def list_questions(self, agent: Agent) -> list[QuestionSummary]: ...

    def get_question(self, qid: str, version: int | None = None) -> QuestionDetail:
        """The latest version unless `version` is given; the summary lists the others."""
        ...

    def list_runs(self, agent: Agent) -> list[RunSummary]: ...

    def get_run(self, agent: Agent, run_id: str) -> RunDetail: ...

    def list_inbox(self) -> list[InboxThread]: ...

    def list_approvals(self, agent: Agent) -> list[Approval]:
        """The seat's `approvals/` cards, newest first. Read only, like everything here."""
        ...

    def submit_question(
        self,
        text: str,
        target: Agent,
        *,
        purpose: str | None = None,
        observable: str | None = None,
    ) -> QuestionSummary:
        """Leave a question for a seat. A read-only store raises ReadOnlyStoreError."""
        ...
