"""The library screen's reader (console card 016): the librarian's generated wiki pages, shown as they stand.

The console may show what the librarian generates under `librarian_agent/kb/wiki/` as data and nothing
else of the store: no entry, no query log, no answers, no export. So this reader opens exactly these files
and no others: `kb/index.json` (for one field, `kb_version`), `kb/wiki/<page>.md` for a page name that
passes `PAGE_ID`, and `kb/wiki/map.json`. It lists no folder, so a file it was not asked for is never seen,
and a page name is checked against a closed pattern before it becomes a path.

It computes nothing about the store. A page is cut into blocks (heading, paragraph, list, code, quote,
table) so the screen can draw it; a link to another wiki page is marked so the screen follows it, and a link
to an entry, a guide or anywhere else becomes plain text. Coverage on the map is the counts the librarian
wrote, in the file's own order: no score, no rank, no one number.

It holds no `caller_id` and calls no service. Nothing it reads is kept.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .sma_files import long_path
from .store import NotFoundError

FOOTER = "Generated from the knowledge store at {version}. Do not edit by hand: correct the store and regenerate."
FOOTER_RE = re.compile(r"Generated from the knowledge store at (kbv-[0-9a-f]{12})\. "
                       r"Do not edit by hand: correct the store and regenerate\.")
VERSION_RE = re.compile(r"kbv-[0-9a-f]{12}")
#: Every page name the wiki has, and no other string: this is what stands between a request and a path.
PAGE_ID = re.compile(r"(?:index|unfiled|evidence|map|(?:device|quantity|observable|sample|configuration)_[a-z0-9_]{1,80})")
GRADES = ("E1", "E2", "E3", "E4", "E5")  # E6 is never in the store's pages
EDGE_TYPES = ("about", "conflict_with", "refutes", "supersedes", "supports", "input_of")
MAX_BYTES = 5_000_000

SECTION_GROUPS = {
    "Device pages": ("devices", "Devices"),
    "Quantity pages": ("quantities", "Quantities"),
    "Observable pages": ("observables", "Observables"),
    "Sample pages": ("samples_and_configurations", "Samples and configurations"),
    "Configuration pages": ("samples_and_configurations", "Samples and configurations"),
    "Unfiled": ("unfiled", "Unfiled"),
}
REGISTERED_UNUSED = "Registered quantities no entry uses"
STORE_FACTS = "The store"
KINDS = ("device", "quantity", "observable", "sample", "configuration")

_INLINE = re.compile(r"`([^`]+)`|\[([^\]]*)\]\(([^)\s]*)\)")
_WIKI_LINK = re.compile(r"(?:\.\./wiki/|\./)?([a-z0-9_]+)\.md")
_LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+(.*)$")
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_RULE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)*\|?\s*$")
_INDEX_LINK = re.compile(r"^-\s+\[([^\]]+)\]\(\.\./wiki/([a-z0-9_]+)\.md\)(?:\s+\((\d+)\s+entr(?:y|ies)\))?\s*$")


def _span(text: str, *, code: bool = False, page: str | None = None) -> dict[str, Any]:
    return {"text": text, "code": code, "page": page}


def inline(text: str) -> list[dict[str, Any]]:
    """Inline markdown to spans. A link to a wiki page is a followed span; every other link is its text."""
    out: list[dict[str, Any]] = []
    pos = 0
    for m in _INLINE.finditer(text):
        if m.start() > pos:
            out.append(_span(text[pos:m.start()]))
        if m.group(1) is not None:
            out.append(_span(m.group(1), code=True))
        else:
            label, target = m.group(2), m.group(3)
            wiki = _WIKI_LINK.fullmatch(target)
            page = wiki.group(1) if wiki and PAGE_ID.fullmatch(wiki.group(1)) else None
            if label:
                out.append(_span(label, page=page))
        pos = m.end()
    if pos < len(text):
        out.append(_span(text[pos:]))
    return [s for s in out if s["text"]]


def plain(text: str) -> str:
    return "".join(s["text"] for s in inline(text))


def _cells(line: str) -> list[str]:
    """A table row's cells: split on `|` that is neither escaped nor inside backticks."""
    s = line.strip()
    cells, cur, ticks, i = [], [], False, 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s) and s[i + 1] == "|":
            cur.append("|")
            i += 2
            continue
        if ch == "`":
            ticks = not ticks
        if ch == "|" and not ticks:
            cells.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1
    cells.append("".join(cur))
    if s.startswith("|"):
        cells = cells[1:]
    if s.endswith("|") and not s.endswith("\\|") and cells:
        cells = cells[:-1]
    return [c.strip() for c in cells]


def blocks_of(lines: list[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if not line.strip():
            i += 1
        elif line.lstrip().startswith("```"):
            language = line.lstrip()[3:].strip()
            body, i = [], i + 1
            while i < n and not lines[i].lstrip().startswith("```"):
                body.append(lines[i])
                i += 1
            i += 1  # the closing fence
            out.append({"type": "code", "language": language, "text": "\n".join(body)})
        elif (h := _HEADING.match(line)):
            out.append({"type": "heading", "level": len(h.group(1)), "text": plain(h.group(2))})
            i += 1
        elif _RULE.match(line):
            out.append({"type": "rule"})
            i += 1
        elif line.lstrip().startswith(">"):
            body = []
            while i < n and lines[i].lstrip().startswith(">"):
                body.append(lines[i].lstrip()[1:].strip())
                i += 1
            out.append({"type": "quote", "spans": inline(" ".join(b for b in body if b))})
        elif line.lstrip().startswith("|") and i + 1 < n and _TABLE_SEP.match(lines[i + 1]):
            header = [inline(c) for c in _cells(line)]
            rows, i = [], i + 2
            while i < n and lines[i].lstrip().startswith("|"):
                rows.append([inline(c) for c in _cells(lines[i])])
                i += 1
            out.append({"type": "table", "header": header, "rows": rows})
        elif _LIST_ITEM.match(line):
            items: list[str] = []
            while i < n and lines[i].strip() and (m := _LIST_ITEM.match(lines[i])):
                items.append(m.group(1))
                i += 1
                while i < n and lines[i].strip() and lines[i].startswith((" ", "\t")) and not _LIST_ITEM.match(lines[i]):
                    items[-1] += " " + lines[i].strip()
                    i += 1
            out.append({"type": "list", "items": [inline(t) for t in items]})
        else:
            body = []
            while i < n and lines[i].strip() and not _special(lines[i], lines[i + 1] if i + 1 < n else ""):
                body.append(lines[i].strip())
                i += 1
            if not body:  # a line that looks special but did not parse as one: show it, never loop
                body.append(lines[i].strip())
                i += 1
            out.append({"type": "paragraph", "spans": inline(" ".join(body))})
    return out


def _special(line: str, nxt: str) -> bool:
    s = line.lstrip()
    return (s.startswith(("```", ">")) or bool(_HEADING.match(line)) or bool(_RULE.match(line))
            or bool(_LIST_ITEM.match(line)) or (s.startswith("|") and bool(_TABLE_SEP.match(nxt))))


def split_footer(text: str) -> tuple[list[str], str] | None:
    """The page's lines without its footer, and the footer line; None when the last line is not the footer."""
    lines = text.splitlines()
    end = len(lines)
    while end and not lines[end - 1].strip():
        end -= 1
    if not end or not FOOTER_RE.fullmatch(lines[end - 1].strip()):
        return None
    footer = lines[end - 1].strip()
    body = lines[:end - 1]
    while body and not body[-1].strip():
        body.pop()
    if body and _RULE.match(body[-1]):  # the rule above the footer belongs to the footer
        body.pop()
    return body, footer


def _older(what: str, footer_version: str, current: str | None) -> tuple[bool, str | None]:
    if current is None:
        return False, f"The store's present version could not be read, so this {what} cannot be compared with it."
    if footer_version == current:
        return False, None
    return True, (f"This {what} was built from an older version of the store ({footer_version}); "
                  f"the store is now at {current}. What it says may have changed since.")


def _no_value(x: Any) -> bool:
    if isinstance(x, dict):
        return "value" not in x and all(_no_value(v) for v in x.values())
    if isinstance(x, list):
        return all(_no_value(v) for v in x)
    return True


def _count(x: Any) -> bool:
    return isinstance(x, int) and not isinstance(x, bool) and x >= 0


class Library:
    """Reads the librarian's generated wiki under `root` (a tree with `librarian_agent/` in it)."""

    def __init__(self, root: str | Path):
        self._kb = long_path(root) / "librarian_agent" / "kb"

    # -- the only reads -----------------------------------------------------------------------

    def _text(self, path: Path) -> str | None:
        try:
            if not path.is_file() or path.stat().st_size > MAX_BYTES:
                return None
            with path.open("rb") as f:
                return f.read().decode("utf-8", errors="replace")
        except OSError:
            return None

    def current_version(self) -> str | None:
        """`kb_version` of `kb/index.json`, the one field taken from it."""
        text = self._text(self._kb / "index.json")
        try:
            v = json.loads(text)["kb_version"] if text is not None else None
        except (ValueError, KeyError, TypeError):
            return None
        return v if isinstance(v, str) and VERSION_RE.fullmatch(v) else None

    def _wiki(self, page: str) -> str | None:
        return self._text(self._kb / "wiki" / f"{page}.md")

    # -- the screens ------------------------------------------------------------------------------

    def index(self) -> dict[str, Any]:
        out: dict[str, Any] = {"state": "not_built", "message": None, "title": None, "facts": [], "groups": [],
                               "registered_unused": [], "footer": None, "footer_version": None,
                               "current_version": None, "behind": False, "note": None}
        text = self._wiki("index")
        if text is None:
            out["message"] = "The library is not built yet: there is no wiki index to show."
            return out
        cut = split_footer(text)
        if cut is None:
            out.update(state="not_generated", message="This is not a generated page, so it is not shown.")
            return out
        lines, footer = cut
        fv = FOOTER_RE.fullmatch(footer).group(1)  # type: ignore[union-attr]
        current = self.current_version()
        behind, note = _older("page", fv, current)
        facts: list[dict[str, str]] = []
        groups: list[dict[str, Any]] = []
        unused: list[str] = []
        title, section = None, None
        for line in lines:
            if (h := _HEADING.match(line)):
                if len(h.group(1)) == 1 and title is None:
                    title = plain(h.group(2))
                section = plain(h.group(2)) if len(h.group(1)) == 2 else None
                continue
            if section is None or not line.strip():
                continue
            if section == STORE_FACTS and line.startswith("- ") and ": " in line:
                label, _, value = line[2:].partition(": ")
                facts.append({"label": label.strip(), "value": value.strip()})
            elif section == REGISTERED_UNUSED and line.startswith("- "):
                unused.append(plain(line[2:].strip()))
            elif (m := _INDEX_LINK.match(line)):
                label, stem, count = m.group(1), m.group(2), m.group(3)
                if not PAGE_ID.fullmatch(stem):
                    continue
                key, name = SECTION_GROUPS.get(section, (re.sub(r"[^a-z0-9]+", "_", section.lower()).strip("_"), section))
                group = next((g for g in groups if g["key"] == key), None)
                if group is None:
                    group = {"key": key, "title": name, "links": []}
                    groups.append(group)
                kind = next((k for k in KINDS if stem.startswith(k + "_")), "unfiled" if stem == "unfiled" else "other")
                group["links"].append({"label": label, "page": stem, "kind": kind,
                                       "entries": int(count) if count is not None else None})
        out.update(state="shown", title=title, facts=facts, groups=groups, registered_unused=unused, footer=footer,
                   footer_version=fv, current_version=current, behind=behind, note=note)
        return out

    def page(self, page_id: str) -> dict[str, Any]:
        if not PAGE_ID.fullmatch(page_id):
            raise NotFoundError(f"not a page name: {page_id[:40]!r}")
        text = self._wiki(page_id)
        if text is None:
            raise NotFoundError(f"no page {page_id} in this copy of the wiki")
        cut = split_footer(text)
        if cut is None:
            raise NotFoundError(f"{page_id} is not a generated page, so it is not shown")
        lines, footer = cut
        fv = FOOTER_RE.fullmatch(footer).group(1)  # type: ignore[union-attr]
        current = self.current_version()
        behind, note = _older("page", fv, current)
        blocks = blocks_of(lines)
        title = next((b["text"] for b in blocks if b["type"] == "heading" and b["level"] == 1), page_id)
        return {"page_id": page_id, "title": title, "blocks": blocks, "footer": footer, "footer_version": fv,
                "current_version": current, "behind": behind, "note": note}

    def map(self) -> dict[str, Any]:
        out: dict[str, Any] = {"state": "not_built", "message": None, "kb_version": None, "current_version": None,
                               "behind": False, "note": None, "footer": None, "subjects": [], "relations": [],
                               "evidence_page": False}
        out["evidence_page"] = (self._kb / "wiki" / "evidence.md").is_file()
        text = self._text(self._kb / "wiki" / "map.json")
        if text is None:
            out["message"] = "The data map is not built yet: the librarian has not generated it."
            return out
        problem, parsed = self._check_map(text)
        if problem:
            out.update(state="not_valid", message=f"The data map is not shown: {problem}.")
            return out
        doc = parsed
        current = self.current_version()
        behind, note = _older("map", doc["kb_version"], current)
        subjects = [{"id": n["id"], "kind": n["kind"], "page": n["page"][:-3],
                     "coverage": {g: n["coverage"][g] for g in GRADES}, "disputed": n["disputed"]}
                    for n in doc["nodes"] if "coverage" in n]
        relations = [{"type": e["type"], "from": e["from"], "to": e["to"], "stated_by": e["stated_by"]}
                     for e in doc["edges"] if e["type"] != "about"]
        out.update(state="built", kb_version=doc["kb_version"], current_version=current, behind=behind, note=note,
                   footer=doc["footer"], subjects=subjects, relations=relations)
        return out

    @staticmethod
    def _check_map(text: str) -> tuple[str | None, dict[str, Any]]:
        try:
            doc = json.loads(text)
        except ValueError:
            return "the file is not JSON", {}
        if not isinstance(doc, dict) or doc.get("artifact") != "kb_map":
            return "the file is not a map of the store", {}
        v = doc.get("kb_version")
        if not isinstance(v, str) or not VERSION_RE.fullmatch(v):
            return "it names no store version", {}
        if doc.get("footer") != FOOTER.format(version=v):
            return "its footer is not the generated one for the version it names", {}
        if not _no_value(doc):
            return "it carries a value, which a map never does", {}
        nodes, edges = doc.get("nodes"), doc.get("edges")
        if not isinstance(nodes, list) or not isinstance(edges, list):
            return "its nodes or edges are missing", {}
        for n in nodes:
            if not isinstance(n, dict) or not isinstance(n.get("id"), str) or not isinstance(n.get("kind"), str):
                return "a node is not shaped like one", {}
            if "coverage" in n:
                c, page = n["coverage"], n.get("page")
                if (not isinstance(c, dict) or set(c) != set(GRADES) or not all(_count(x) for x in c.values())
                        or not _count(n.get("disputed")) or not isinstance(page, str) or not page.endswith(".md")
                        or not PAGE_ID.fullmatch(page[:-3])):
                    return f"the coverage of {n['id'][:60]} is not counts by grade", {}
        for e in edges:
            if (not isinstance(e, dict) or e.get("type") not in EDGE_TYPES
                    or not all(isinstance(e.get(k), str) for k in ("from", "to", "stated_by"))):
                return "a relation is not shaped like one", {}
        return None, doc
