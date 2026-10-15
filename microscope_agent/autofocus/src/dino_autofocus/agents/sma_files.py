"""Read the soft-matter-agents files. Never write them, never import their code.

Layout read (the soft-matter-agents repository, or a copy with the same layout):

    <seat>_agent/questions/<qid>/       goal.json, axis_*.json, plan_*.json, synthesis.json,
                                        refusal_*.json, result_*.json, *.md, and the same
                                        names with a "vN_" prefix for revision N
    <seat>_agent/runs/<run_id>/         log.json, commands.json | config.json, observables.json,
                                        trajectory_meta.json, and large files left unopened;
                                        events.jsonl while the orchestrator follows the run
                                        (read by `sma_run`, plan.md 11-25)
    <seat>_agent/inbox/<thread>/        rN_<kind>.json | .md, what the seat received
    <seat>_agent/approvals/             appr-<qid>-r<N>.json, the person's plan_approval cards
    bridge/threads/<thread>/status.json the bridge's view of the thread

`contracts/schemas/*.schema.json` is what the cards follow; it is not loaded here. A card
is read as it is and kept whole, so a field this module does not know is not lost. JSON is
read as utf-8-sig, as soft-matter-agents' validator reads it: some approvals carry a
byte-order mark.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

from .sma_run import MAX_EVENTS_BYTES, NotFollowedError, RunStream, SmaRunError, read_stream
from .store import (
    AGENTS,
    Agent,
    Approval,
    Card,
    Document,
    FileInfo,
    InboxMessage,
    InboxThread,
    NotFoundError,
    QuestionDetail,
    QuestionSummary,
    ReadOnlyStoreError,
    RunDetail,
    RunSummary,
    agent_of_qid,
    check_agent,
)

DEFAULT_ROOT = Path(r"D:\codes\github\soft-matter-agents")
ROOT_ENV = "DINO_AF_SMA_ROOT"

# Record files a run detail opens. Anything else in a run folder (the trajectory, images,
# partial logs) is listed by name and size only.
RUN_RECORDS: dict[Agent, tuple[str, ...]] = {
    "microscope": ("commands.json", "log.json", "deviations.json"),
    "simulation": ("config.json", "log.json", "observables.json", "trajectory_meta.json"),
}
MAX_READ_BYTES = 2_000_000  # a record over this is listed in RunDetail.not_opened

_VERSION_RE = re.compile(r"^v([0-9]+)_(.+)$")
_ROUND_RE = re.compile(r"^r([0-9]+)_(.+)$")
_PREFIX_KINDS = ("axis", "plan", "refusal", "result", "synthesis", "goal")


def default_root() -> Path:
    """`$DINO_AF_SMA_ROOT` if set, else the soft-matter-agents checkout on this desktop."""
    env = os.environ.get(ROOT_ENV)
    return Path(env) if env else DEFAULT_ROOT


def split_version(name: str) -> tuple[int, str]:
    """`v3_goal.json` -> (3, "goal.json"); `goal.json` -> (1, "goal.json")."""
    m = _VERSION_RE.match(name)
    return (int(m.group(1)), m.group(2)) if m else (1, name)


def guess_kind(base: str) -> str:
    """Card kind from an unversioned file name, for a card without a "card" field."""
    stem = base.rsplit(".", 1)[0]
    for k in _PREFIX_KINDS:
        if stem == k or stem.startswith(k + "_"):
            return k
    return stem


def long_path(p: str | os.PathLike[str]) -> Path:
    """On Windows, the `\\\\?\\` form of `p` made absolute, which the file system does not cut
    at MAX_PATH (260 characters) when long paths are off system-wide; without it a deep
    copy loses files silently, because `is_file()` is then False with no error.
    Unchanged on other systems."""
    if os.name != "nt":
        return Path(p)
    s = os.path.abspath(p)
    if s.startswith("\\\\?\\"):
        return Path(s)
    if s.startswith("\\\\"):  # \\server\share -> \\?\UNC\server\share
        return Path("\\\\?\\UNC\\" + s[2:])
    return Path("\\\\?\\" + s)


def _size(p: Path) -> int | None:
    """Size in bytes, or None when the entry is listed but cannot be stat'ed."""
    try:
        return p.stat().st_size
    except OSError:
        return None


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def plan_hash(card: dict[str, Any]) -> str:
    """What a plan_approval signs: sha256 of the card with `status` removed, keys sorted, no
    spaces (soft-matter-agents contracts/validate.py card_sha / plan_hash, plan.md 5.5)."""
    body = {k: v for k, v in card.items() if k != "status"}
    blob = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(blob.encode()).hexdigest()


def _int_or_none(v: Any) -> int | None:
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def _str_or_none(v: Any) -> str | None:
    return v if isinstance(v, str) else None


class SmaFiles:
    """AgentStore over a soft-matter-agents tree. Read only.

    `source` names where the records came from in every summary, so a console showing
    two stores side by side can tell them apart. An entry that a folder lists but that
    cannot be stat'ed is reported (in `files` with size None, or in `not_opened`), not
    dropped.
    """

    writable = False

    def __init__(self, root: str | os.PathLike[str] | None = None, *,
                 source: str = "soft-matter-agents", max_read_bytes: int = MAX_READ_BYTES):
        self.root = Path(root) if root is not None else default_root()
        self._root = long_path(self.root)  # what the file system is asked about
        self.source = source
        self.max_read_bytes = max_read_bytes

    def __repr__(self) -> str:
        return f"SmaFiles({str(self.root)!r}, source={self.source!r})"

    def available(self) -> bool:
        return any((self._root / f"{a}_agent").is_dir() for a in AGENTS)

    # -- questions -------------------------------------------------------------------------

    def _question_dir(self, qid: str) -> Path:
        return self._root / f"{agent_of_qid(qid)}_agent" / "questions" / qid

    def has_question(self, qid: str) -> bool:
        try:
            return self._question_dir(qid).is_dir()
        except NotFoundError:
            return False

    def list_questions(self, agent: Agent) -> list[QuestionSummary]:
        base = self._root / f"{check_agent(agent)}_agent" / "questions"
        if not base.is_dir():
            return []
        out = []
        for d in base.iterdir():
            if d.is_dir() and _is_qid(d.name) and agent_of_qid(d.name) == agent:
                out.append(self._summary(d, _scan(d)))
        return sorted(out, key=lambda s: s.qid, reverse=True)

    def get_question(self, qid: str, version: int | None = None) -> QuestionDetail:
        d = self._question_dir(qid)
        if not d.is_dir():
            raise NotFoundError(f"no question {qid} in {self.source}")
        paths = _scan(d)
        summary = self._summary(d, paths)
        v = summary.latest_version if version is None else version
        if v not in paths:
            raise NotFoundError(f"{qid} has no version {v}; it has {summary.versions}")
        detail = _detail(summary, v, *self._read_version(paths[v], v))
        plan = detail.plan.data if detail.plan and isinstance(detail.plan.data, dict) else None
        approvals = [a for a in self.list_approvals(summary.agent) if a.qid == qid]
        return replace(detail, plan_hash=plan_hash(plan) if plan is not None else None,
                       approvals=approvals)

    def _summary(self, d: Path, paths: dict[int, list[Path]]) -> QuestionSummary:
        """Opens the first and the latest version only, so a list stays quick: created_at is
        the earliest card of the first version, status and updated_at come from the newest
        card of the latest."""
        qid = d.name
        versions = sorted(paths) or [1]
        first, latest = versions[0], versions[-1]
        read = {v: self._read_version(paths.get(v, []), v) for v in {first, latest}}
        first_times = [c.created_at for c in read[first][0] if c.created_at]
        latest_times = [c.created_at for c in read[latest][0] if c.created_at]
        newest = _newest(read[latest][0])
        docs = [doc for v in sorted(paths, reverse=True)
                for doc in self._read_docs(paths[v], v, only_question=True)]
        heads = _heads([read[latest][0], read[first][0]])
        observable = _first(heads, "observable")
        return QuestionSummary(
            qid=qid,
            agent=agent_of_qid(qid),
            title=_title(qid, docs, heads),
            status=newest.status if newest else None,
            created_at=min(first_times) if first_times else None,
            updated_at=max(latest_times) if latest_times else None,
            latest_version=latest,
            versions=versions,
            source=self.source,
            purpose=_str_or_none(_first(heads, "purpose")),
            intent=_str_or_none(_first(heads, "intent")),
            observable_name=_str_or_none(observable.get("name"))
            if isinstance(observable, dict) else None,
        )

    def _read_version(self, paths: list[Path], version: int
                      ) -> tuple[list[Card], list[Document], list[FileInfo]]:
        cards: list[Card] = []
        files: list[FileInfo] = []
        docs = self._read_docs(paths, version)
        read_docs = {doc.name for doc in docs}
        for p in paths:
            if p.name in read_docs:
                continue
            base = split_version(p.name)[1]
            card = self._read_card(p, version, base) if base.endswith(".json") else None
            if card is None:
                files.append(FileInfo(p.name, _size(p)))
            else:
                cards.append(card)
        return cards, docs, files

    def _read_docs(self, paths: list[Path], version: int, *, only_question: bool = False
                   ) -> list[Document]:
        out = []
        for p in paths:
            base = split_version(p.name)[1]
            if base.endswith(".md") and (not only_question or base.startswith("question")):
                try:
                    out.append(Document(p.name, version, p.read_text(encoding="utf-8")))
                except (OSError, UnicodeDecodeError):
                    continue  # _read_version lists it in files instead
        return out

    def _read_card(self, p: Path, version: int, base: str) -> Card | None:
        size = _size(p)
        if size is None or size > self.max_read_bytes:
            return None
        try:
            data = _read_json(p)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        head = data if isinstance(data, dict) else {}
        kind = head.get("card") if isinstance(head.get("card"), str) else guess_kind(base)
        return Card(
            name=p.name,
            kind=kind,
            version=version,
            status=_str_or_none(head.get("status")),
            created_at=_str_or_none(head.get("created_at")),
            data=data,
        )

    # -- runs ------------------------------------------------------------------------------

    def _run_dir(self, agent: Agent, run_id: str) -> Path:
        if not run_id or "/" in run_id or "\\" in run_id or run_id in (".", ".."):
            raise NotFoundError(f"not a run id: {run_id!r}")
        return self._root / f"{check_agent(agent)}_agent" / "runs" / run_id

    def list_runs(self, agent: Agent) -> list[RunSummary]:
        base = self._root / f"{check_agent(agent)}_agent" / "runs"
        if not base.is_dir():
            return []
        out = [self._run_summary(agent, d) for d in base.iterdir() if d.is_dir()]
        return sorted(out, key=lambda r: (r.created_at or "", r.run_id), reverse=True)

    def get_run(self, agent: Agent, run_id: str) -> RunDetail:
        d = self._run_dir(agent, run_id)
        if not d.is_dir():
            raise NotFoundError(f"no {agent} run {run_id} in {self.source}")
        records: dict[str, Any] = {}
        not_opened: list[str] = []
        entries = [p for p in sorted(d.iterdir()) if not p.is_dir()]
        names = {p.name for p in entries}
        for name in RUN_RECORDS[agent]:
            if name not in names:
                continue
            p = d / name
            size = _size(p)
            if size is None or size > self.max_read_bytes:
                not_opened.append(name)
                continue
            try:
                records[name] = _read_json(p)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                not_opened.append(name)
        files = [FileInfo(p.name, _size(p)) for p in entries]
        return RunDetail(self._run_summary(agent, d), records, files, not_opened)

    def run_stream(self, agent: Agent, run_id: str) -> RunStream:
        """The run's events.jsonl as written so far (`sma_run.read_stream`). Raises
        NotFoundError for no such run, `sma_run.NotFollowedError` for a run not followed."""
        d = self._run_dir(agent, run_id)
        if not d.is_dir():
            raise NotFoundError(f"no {agent} run {run_id} in {self.source}")
        return read_stream(d, max_bytes=max(self.max_read_bytes, MAX_EVENTS_BYTES))

    def _followed(self, d: Path) -> RunStream | None:
        """The events stream of a run its orchestrator follows, or None."""
        try:
            return read_stream(d, max_bytes=max(self.max_read_bytes, MAX_EVENTS_BYTES))
        except (NotFollowedError, SmaRunError):
            return None

    def _run_summary(self, agent: Agent, d: Path) -> RunSummary:
        log = self._small_json(d / "log.json")
        config = self._small_json(d / "config.json")
        meta = self._small_json(d / "trajectory_meta.json")
        # A followed run has events.jsonl from its start and log.json only at its end: until
        # then the stream says what the run is and whether it is still going (plan.md 11-25).
        stream = self._followed(d) if not log and agent == "microscope" else None
        if stream is not None:
            return RunSummary(
                run_id=d.name, agent=agent, qid=_qid_of(None, stream.plan_id),
                plan_id=stream.plan_id,
                status="running" if stream.running else stream.ended_how,
                created_at=stream.t0_wall, finished_at=None, backend=None,
                source=self.source, approval_kind=None,
            )
        plan_id = _str_or_none(log.get("plan_id")) or _str_or_none(config.get("plan_id"))
        qid = _qid_of(_str_or_none(config.get("qid")) or _str_or_none(log.get("qid")), plan_id)
        status = _run_outcome(log) or _str_or_none(meta.get("stop_outcome"))
        if status is None and agent == "microscope":
            # A followed run's log.json states no outcome; run_ended's `how` is only in the
            # stream (soft-matter-agents card 057), so the list reads it there.
            ended = self._followed(d)
            status = ended.ended_how if ended is not None and not ended.running else None
        return RunSummary(
            run_id=d.name,
            agent=agent,
            qid=qid,
            plan_id=plan_id,
            status=status,
            created_at=_str_or_none(log.get("t0_wall")),
            finished_at=_str_or_none(log.get("finished_at")),
            backend=_str_or_none(log.get("backend")) or _str_or_none(config.get("backend")),
            source=self.source,
            approval_kind=_approval_kind(log) or _approval_kind(config),
        )

    def _small_json(self, p: Path) -> dict[str, Any]:
        """A run record's top level for a summary, or {} when absent, too big or unreadable."""
        try:
            if not p.is_file() or p.stat().st_size > self.max_read_bytes:
                return {}
            data = _read_json(p)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    # -- approvals -------------------------------------------------------------------------

    def list_approvals(self, agent: Agent) -> list[Approval]:
        """`<seat>_agent/approvals/*.json`, newest first, each checked against the plan cards
        of its question (`plan_found`). An unreadable file is listed with its name only."""
        base = self._root / f"{check_agent(agent)}_agent" / "approvals"
        if not base.is_dir():
            return []
        hashes: dict[str, set[str]] = {}
        out = []
        for p in sorted(base.iterdir()):
            if p.is_dir() or p.suffix != ".json":
                continue
            data = self._small_json(p)
            qid = _str_or_none(data.get("qid"))
            want = _str_or_none(data.get("plan_hash"))
            found = None
            if qid is not None and want is not None:
                if qid not in hashes:
                    hashes[qid] = self._plan_hashes(qid)
                found = want in hashes[qid] if hashes[qid] is not None else None
            out.append(Approval(
                name=p.name, agent=agent, id=_str_or_none(data.get("id")), qid=qid,
                revision=_int_or_none(data.get("revision")),
                status=_str_or_none(data.get("status")),
                plan_id=_str_or_none(data.get("plan_id")),
                plan_revision=_int_or_none(data.get("plan_revision")), plan_hash=want,
                approved_by=_str_or_none(data.get("approved_by")),
                approved_at=_str_or_none(data.get("approved_at")),
                source=self.source, plan_found=found, data=data or None,
            ))
        return sorted(out, key=lambda a: (a.approved_at or "", a.name), reverse=True)

    def _plan_hashes(self, qid: str) -> set[str] | None:
        """The hash of every plan card of the question, any version; None: no such folder."""
        try:
            d = self._question_dir(qid)
        except NotFoundError:
            return None
        if not d.is_dir():
            return None
        out = set()
        for paths in _scan(d).values():
            for p in paths:
                base = split_version(p.name)[1]
                if base.endswith(".json") and guess_kind(base) == "plan":
                    data = self._small_json(p)
                    if data:
                        out.add(plan_hash(data))
        return out

    # -- inbox -----------------------------------------------------------------------------

    def list_inbox(self) -> list[InboxThread]:
        threads: dict[str, Agent | None] = {}
        for a in AGENTS:
            base = self._root / f"{a}_agent" / "inbox"
            if base.is_dir():
                for d in base.iterdir():
                    if d.is_dir():
                        threads[d.name] = a
        bridge = self._root / "bridge" / "threads"
        if bridge.is_dir():
            for d in bridge.iterdir():
                if d.is_dir():
                    threads.setdefault(d.name, None)
        out = [self._thread(t, a) for t, a in threads.items()]
        return sorted(out, key=lambda t: (t.updated_at or "", t.thread), reverse=True)

    def _thread(self, thread: str, agent: Agent | None) -> InboxThread:
        status = self._small_json(self._root / "bridge" / "threads" / thread / "status.json")
        messages: list[InboxMessage] = []
        if agent is not None:
            for p in sorted((self._root / f"{agent}_agent" / "inbox" / thread).iterdir()):
                if not p.is_dir() and p.suffix in (".json", ".md"):
                    messages.append(self._message(p))
        rnd = status.get("round")
        return InboxThread(
            thread=thread,
            agent=agent,
            state=_str_or_none(status.get("state")),
            turn=_str_or_none(status.get("turn")),
            round=rnd if isinstance(rnd, int) else None,
            updated_at=_str_or_none(status.get("updated_at")),
            status=status or None,
            messages=sorted(messages, key=lambda m: (m.round or 0, m.kind, m.name)),
            source=self.source,
        )

    def _message(self, p: Path) -> InboxMessage:
        m = _ROUND_RE.match(p.stem)
        rnd, kind = (int(m.group(1)), m.group(2)) if m else (None, p.stem)
        # card and text both None: listed by name, the console shows it as unreadable
        size = _size(p)
        if p.suffix == ".json":
            try:
                ok = size is not None and size <= self.max_read_bytes
                card = _read_json(p) if ok else None
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                card = None
            return InboxMessage(p.name, rnd, kind, card=card, text=None)
        try:
            text = p.read_text(encoding="utf-8") if size is not None else None
        except (OSError, UnicodeDecodeError):
            text = None
        return InboxMessage(p.name, rnd, kind, card=None, text=text)

    # -- writing ---------------------------------------------------------------------------

    def submit_question(self, text: str, target: Agent, *, purpose: str | None = None,
                        observable: str | None = None) -> QuestionSummary:
        raise ReadOnlyStoreError(
            f"{self.source} is read only (PLAN.md 6.9); questions go to the mock store "
            "until the integration decides the real path"
        )


def _scan(d: Path) -> dict[int, list[Path]]:
    """The files of a question folder by version, names sorted, nothing opened."""
    out: dict[int, list[Path]] = {}
    for p in sorted(d.iterdir()):
        if not p.is_dir() and not p.name.endswith(".tmp"):
            out.setdefault(split_version(p.name)[0], []).append(p)
    return out


def _qid_of(qid: str | None, plan_id: str | None) -> str | None:
    """The run's qid, else the one its plan id carries."""
    if qid is None and plan_id:
        m = re.search(r"(mic|sim)-[0-9]{8}-[0-9]{3}", plan_id)
        qid = m.group(0) if m else None
    return qid


def _is_qid(name: str) -> bool:
    try:
        agent_of_qid(name)
    except NotFoundError:
        return False
    return True


def _newest(cards: list[Card]) -> Card | None:
    dated = [c for c in cards if c.created_at]
    return max(dated, key=lambda c: c.created_at or "") if dated else (cards[-1] if cards else None)


def _heads(card_groups: list[list[Card]]) -> list[dict[str, Any]]:
    """Goal cards before plan cards, group by group (latest version first)."""
    out = []
    for cs in card_groups:
        for kind in ("goal", "plan"):
            out += [c.data for c in cs if c.kind == kind and isinstance(c.data, dict)]
    return out


def _first(heads: list[dict[str, Any]], key: str) -> Any:
    return next((h[key] for h in heads if h.get(key) is not None), None)


def _approval_kind(record: dict[str, Any]) -> str | None:
    approval = record.get("approval")
    return _str_or_none(approval.get("kind")) if isinstance(approval, dict) else None


def _title(qid: str, docs: list[Document], heads: list[dict[str, Any]]) -> str:
    """The heading of the question's markdown copy, else the question text, else the
    observable a goal or plan names, else its purpose and first target, else the qid.
    `docs` come newest version first, `heads` as `_heads` orders them."""
    for doc in docs:
        lines = doc.text.strip().splitlines()
        if lines and lines[0].startswith("#"):
            head = lines[0].lstrip("#").strip()
            # "# sim-20260923-001 — structural relaxation ..." -> the part after the id
            for sep in (" — ", " - ", ": "):
                if head.startswith(qid) and sep in head:
                    return head.split(sep, 1)[1].strip()
            return head
    for h in heads:
        q = h.get("question")
        if isinstance(q, str) and q.strip():
            return q.strip().splitlines()[0][:120]
    for h in heads:
        obs = h.get("observable")
        if isinstance(obs, dict) and isinstance(obs.get("name"), str):
            return obs["name"]
    for h in heads:
        targets = h.get("targets")
        metric = targets[0].get("metric") if targets and isinstance(targets[0], dict) else None
        if isinstance(h.get("purpose"), str) and isinstance(metric, str):
            return f"{h['purpose']} · {metric}"
    return qid


def _run_outcome(log: dict[str, Any]) -> str | None:
    """The outcome of the log's last event that states one (run_end on the microscope)."""
    events = log.get("events")
    if isinstance(events, list):
        for e in reversed(events):
            if isinstance(e, dict) and isinstance(e.get("outcome"), str):
                return e["outcome"]
    return _str_or_none(log.get("outcome"))


def _detail(summary: QuestionSummary, version: int, cards: list[Card], docs: list[Document],
            files: list[FileInfo]) -> QuestionDetail:
    goal = plan = synthesis = None
    axes: list[Card] = []
    refusals: list[Card] = []
    results: list[Card] = []
    others: list[Card] = []
    for c in cards:
        if c.kind == "goal" and goal is None:
            goal = c
        elif c.kind == "axis":
            axes.append(c)
        elif c.kind == "plan" and plan is None:
            plan = c
        elif c.kind == "synthesis" and synthesis is None:
            synthesis = c
        elif c.kind == "refusal":
            refusals.append(c)
        elif c.kind == "result":
            results.append(c)
        else:
            others.append(c)
    return QuestionDetail(summary, version, goal, axes, plan, synthesis, refusals, results,
                          others, docs, files)
