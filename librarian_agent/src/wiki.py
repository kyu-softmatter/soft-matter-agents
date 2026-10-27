#!/usr/bin/env python3
"""Render the wiki from the store: one page per subject, under kb/wiki/ (task 054).

The pages are GENERATED, like the safety guides. The entries are the authority
(P3); a page is how they are read. A page is read and never cited -- `kb:` cites
entries and nothing else -- so a hand edit is drift the next run overwrites, and
--check says so.

The page set:

    kb/wiki/index.md                    the store: version, counts, every page
    kb/wiki/device_<id>.md              each device id an entry names as subject
    kb/wiki/quantity_<id>.md            each registered quantity an entry uses,
                                        as subject or as a numbers[] name
    kb/wiki/observable_<id>.md          EVERY registered observable, entries or not
    kb/wiki/sample_<id>.md              each sample id named as subject
    kb/wiki/configuration_<id>.md       each configuration id named as subject

FLAT, not one folder per section: check 13 caps a path inside an agent at three
levels below it, and kb/wiki/<section>/<id>.md is four (e275ab39).
    kb/wiki/unfiled.md                  the entries that name no subject
    kb/wiki/evidence.md                 every entry, by grade (task 060)
    kb/wiki/map.md                      each subject's coverage and the pages it shares entries with
    kb/wiki/map.json                    the same relations as nodes and typed edges, for the console
                                        to draw; it carries no number taken from an entry (task 060)

Every page carries the same eight sections in the same order, and an empty one
says "None.". What binds the renderer:

  - ONLY FIELDS AND FIXED SENTENCES. No summary, no best value, no average, no
    ranking but the server's own sort (grade, rank inside E3, entry_id). Every
    other sentence on a page is quoted from an entry or a registry.
  - DETERMINISTIC. The same store gives the same bytes: sorted throughout, no
    timestamps, LF line endings.
  - STATUS AS THE SERVER REPORTS IT (048), from mcp_server's own Store.standing.
  - THE GRADE IN WORDS for the person, beside the grade code and the source
    exactly as recorded, for a seat that needs them.
  - NO RAW OR INLINE HTML. validity_conditions is a Markdown blockquote; text
    quoted from the store has '<' and '>' escaped so it cannot become a tag.
  - ASCII ids as file names, and every link a relative path that stays inside kb/.

    python3 librarian_agent/src/wiki.py              # write the pages
    python3 librarian_agent/src/wiki.py --check      # fail if any page differs
    python3 librarian_agent/src/wiki.py --self-test  # the rules, on a synthetic store
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
AGENT = SRC.parent
KB = AGENT / "kb"
WIKI = KB / "wiki"
CONTRACTS = AGENT.parent / "contracts"
sys.path.insert(0, str(SRC))
import kb_index  # noqa: E402
import mcp_server  # noqa: E402

SECTIONS = ("device", "quantity", "observable", "sample", "configuration")
CITE = "Generated from the store; cite the entries, as `kb:<entry_id>`, not this page."
NONE = "None."
MIDDOT = " " + chr(183) + " "        # the separator the task's example uses: `E3 . spec:Kinetix22`
GRADE_WORDS = {
    "E1": "measured on this instrument",
    "E2": "calibrated on this instrument",
    "E3": "from a document, a reading off the instrument, or another project's record",
    "E4": "computed",
    "E5": "recalled or assumed",
    "E6": "made up by a model, and never in the store",
}
SOURCE_WORDS = {
    "measured": "a recorded run of this system",
    "calibration": "a calibration on this instrument",
    "spec": "manufacturer's specification",
    "prior_run": "another project's record",
    "literature": "published literature",
    "operator_read": "the person read it off the instrument",
    "operator_recall": "the person's recollection",
    "computed": "computed from other values",
    "simulated": "a simulation",
    "assumed": "an assumption",
    "kb": "another store entry",
}
STATUS_WORDS = {"refuted": "refuted", "superseded": "superseded", "conflict": "in conflict", "current": "current"}
GRADES = ("E1", "E2", "E3", "E4", "E5")    # E6 never enters, so evidence.md and the map have no section for it
ASCII_ID = re.compile(r"^[a-z0-9_]+$")     # what ALLOWED_PATHS admits in a page name (e275ab39)


def footer(version: str) -> str:
    return f"Generated from the knowledge store at {version}. Do not edit by hand: correct the store and regenerate."


# -- quoting ------------------------------------------------------------------------------------

def quote(text) -> str:
    """Text quoted from the store, made inert: no tag can form, nothing breaks a line."""
    s = "" if text is None else str(text)
    return s.replace("\\", "\\\\").replace("<", "\\<").replace(">", "\\>").replace("\r", " ").replace("\n", " ")


def cell(text) -> str:
    return quote(text).replace("|", "\\|")


def fmt(v) -> str:
    if isinstance(v, bool) or v is None:
        return json.dumps(v)
    if isinstance(v, float):
        return repr(v)
    return str(v)


# -- the store and its registries ---------------------------------------------------------------

class Data:
    def __init__(self, store, quantities: list, observables: list, devices: dict, samples: dict,
                 distilled: dict, guides: set, version: str):
        self.store, self.version = store, version
        self.entries = store.entries
        self.quantities = {q["id"]: q for q in quantities}
        self.observables = {o["id"]: o for o in observables}
        self.devices, self.samples = devices, samples
        self.distilled, self.guides = distilled, guides


def load() -> Data:
    version = kb_index.build(KB)["kb_version"]
    store = mcp_server.Store(log=Path("unused-no-query-is-made.jsonl"))
    q = json.loads((CONTRACTS / "quantities.json").read_text(encoding="utf-8"))["quantities"]
    o = json.loads((CONTRACTS / "observables.json").read_text(encoding="utf-8"))["observables"]
    dev = json.loads((KB / "staging" / "devices.v0.json").read_text(encoding="utf-8"))
    smp = json.loads((KB / "staging" / "samples.v0.json").read_text(encoding="utf-8"))
    distilled = {p.name: p.read_text(encoding="utf-8") for p in sorted((KB / "distilled").glob("*.md"))}
    guides = {p.name for p in (KB / "guides").glob("safety_*.md")}
    return Data(store, q, o, dev, smp, distilled, guides, version)


def device_row(devices: dict, did: str):
    for c in devices.get("channels") or []:
        if c.get("id") == did:
            return "the device table, kb/staging/devices.v0.json, channel", c
        for e in c.get("elements") or []:
            if e.get("id") == did:
                return f"the device table, kb/staging/devices.v0.json, element of channel {c['id']}", e
    for r in devices.get("retired_rows") or []:
        if r.get("id") == did:
            return "the device table, kb/staging/devices.v0.json, retired row", r
    return None, None


def sample_row(samples: dict, sid: str):
    for i in samples.get("instances") or []:
        if i.get("id") == sid:
            return "the sample table, kb/staging/samples.v0.json", i
    return None, None


# -- which entry is on which page ---------------------------------------------------------------

def pages_of(d: Data) -> dict[tuple[str, str], list[str]]:
    """(section, id) -> entry ids on that page, in the server's order. Plus ('unfiled', '')."""
    on: dict[tuple[str, str], set[str]] = {}
    for eid, e in d.entries.items():
        for s in e.get("subject") or []:
            kind, sid = s.get("kind"), s.get("id")
            if kind in SECTIONS and sid:
                if kind == "quantity" and sid not in d.quantities:
                    continue
                if kind == "observable" and sid not in d.observables:
                    continue
                on.setdefault((kind, sid), set()).add(eid)
        for n in e.get("numbers") or []:
            name = n.get("name")
            if name in d.quantities:
                on.setdefault(("quantity", name), set()).add(eid)
            if name in d.observables:
                on.setdefault(("observable", name), set()).add(eid)
        if not e.get("subject"):
            on.setdefault(("unfiled", ""), set()).add(eid)
    for oid in d.observables:
        on.setdefault(("observable", oid), set())
    on.setdefault(("unfiled", ""), set())
    for key in on:
        if key[0] != "unfiled" and not ASCII_ID.match(key[1]):
            raise SystemExit(f"{key[0]} id {key[1]!r} is not lowercase ASCII snake case and cannot be a page name; fix the id at its source")
    return {k: sorted(v, key=d.store.sort_key) for k, v in on.items()}


def page_path(section: str, pid: str) -> str:
    return "unfiled.md" if section == "unfiled" else f"{section}_{pid}.md"


def rel(from_page: str, target_in_kb: str) -> str:
    """A relative link from a page under kb/wiki/ to a path under kb/."""
    depth = from_page.count("/") + 1          # +1 for wiki/ itself
    return "../" * depth + target_in_kb


# -- one page ------------------------------------------------------------------------------------

def status(d: Data, eid: str) -> tuple[str, dict]:
    st = d.store.standing(eid)
    e = d.entries[eid]
    if st["status"] == "current" and e.get("conflict_with"):
        return "conflict", st
    return st["status"], st


def conditions(e: dict) -> str:
    v = e.get("validity") or {}
    if not v:
        return "none stated"
    parts = []
    for k in sorted(v):
        r = v[k]
        if isinstance(r, dict):
            lo, hi, u = r.get("min"), r.get("max"), r.get("unit", "")
            parts.append(f"{k} {fmt(lo)} {u}" if lo == hi else f"{k} {fmt(lo)} to {fmt(hi)} {u}")
        else:
            parts.append(f"{k} {fmt(r)}")
    return "; ".join(p.strip() for p in parts)


def how_known(n: dict, e: dict) -> str:
    grade = n.get("grade") or e.get("grade")
    src = str(n.get("source") or e.get("source") or "")
    kind = src.split(":", 1)[0]
    return f"{GRADE_WORDS.get(grade, 'not graded')}; {SOURCE_WORDS.get(kind, 'source kind not recognised')}"


def identifiers_text(e: dict) -> str:
    """The entry's identifiers as `key: value`, verbatim, in key order, without applies_to (055)."""
    ids = e.get("identifiers") or {}
    pairs = [f"{k}: {fmt(ids[k]) if not isinstance(ids[k], str) else ids[k]}" for k in sorted(ids) if k != "applies_to"]
    return "; ".join(pairs) if pairs else "none"


def subjects_text(e: dict) -> str:
    s = e.get("subject") or []
    return ", ".join(f"{x.get('kind')} {x.get('id')}" for x in s) if s else "none named"


def what_it_is(d: Data, section: str, pid: str) -> list[str]:
    if section == "quantity":
        q = d.quantities[pid]
        return [f"From the managers' registry, contracts/quantities.json:", "",
                f"> {quote(q.get('definition'))}", "",
                f"- unit: `{cell(q.get('unit'))}`", f"- kind: {quote(q.get('kind'))}"]
    if section == "observable":
        o = d.observables[pid]
        return [f"From the managers' registry, contracts/observables.json:", "",
                f"> {quote(o.get('definition'))}", "",
                f"- units: {quote(json.dumps(o.get('units'), ensure_ascii=False))}",
                f"- estimator: {quote(o.get('estimator'))}"]
    if section in ("device", "sample"):
        where, row = (device_row if section == "device" else sample_row)(
            d.devices if section == "device" else d.samples, pid)
        if row is None:
            return [f"No registry text: this id has no row in the {'device' if section == 'device' else 'sample'} table."]
        return [f"From {where}, verbatim:", "", "```json",
                json.dumps(row, indent=2, ensure_ascii=False).replace("```", "'''"), "```"]
    return ["No registry text: configurations have no table of their own in the store."]


def render(d: Data, section: str, pid: str, on: dict) -> str:
    me = page_path(section, pid)
    eids = on[(section, pid)]
    title = "Unfiled entries" if section == "unfiled" else f"{section.capitalize()}: {pid}"
    line = ("Every entry in the store that names no subject, so that none is invisible."
            if section == "unfiled" else f"Every entry in the store about the {section} {pid}.")
    out = [f"# {title}", "", line, "", CITE, ""]

    out += ["## What it is", ""]
    out += (["Not a registry subject: these entries carry no subject field."] if section == "unfiled"
            else what_it_is(d, section, pid))
    out.append("")

    out += ["## Values", ""]
    rows = []
    for eid in eids:
        e = d.entries[eid]
        for n in e.get("numbers") or []:
            rows.append("| " + " | ".join([
                cell(n.get("name")), cell(fmt(n.get("value"))), cell(n.get("unit")),
                cell(how_known(n, e)),
                cell(f"{n.get('grade') or e.get('grade')}{MIDDOT}{n.get('source') or e.get('source')}"),
                cell(conditions(e)), cell(identifiers_text(e)), cell(subjects_text(e)),
                f"[{cell(eid)}]({rel(me, 'entries/' + eid + '.json')})"]) + " |")
    if rows:
        out += ["| quantity | value | unit | how it is known | grade and source as recorded | conditions | identifiers | subject | entry |",
                "|---|---|---|---|---|---|---|---|---|"] + rows
        applies = [eid for eid in eids if d.entries[eid].get("numbers")
                   and (d.entries[eid].get("identifiers") or {}).get("applies_to")]
        if applies:
            out += ["", "Applies to, verbatim, for the entries above that say:", ""]
            out += [f"- [{cell(eid)}]({rel(me, 'entries/' + eid + '.json')}): "
                    f"{quote(d.entries[eid]['identifiers']['applies_to'])}" for eid in applies]
    else:
        out.append(NONE)
    out.append("")

    out += ["## Claims", ""]
    claims = [eid for eid in eids if not d.entries[eid].get("numbers")]
    if claims:
        for eid in claims:
            e = d.entries[eid]
            out += [f"### [{cell(eid)}]({rel(me, 'entries/' + eid + '.json')})", "",
                    quote(e.get("claim")), ""]
            if (e.get("identifiers") or {}).get("applies_to"):
                out += [f"Applies to: {quote(e['identifiers']['applies_to'])}", ""]
            out += [f"Identifiers: {quote(identifiers_text(e))}", "",
                    f"How it is known: {quote(GRADE_WORDS.get(e.get('grade'), 'not graded'))}; "
                    f"{quote(SOURCE_WORDS.get(str(e.get('source', '')).split(':', 1)[0], 'source kind not recognised'))} "
                    f"({quote(e.get('grade'))}{MIDDOT}{quote(e.get('source'))}).", "",
                    "Conditions, verbatim:", "", f"> {quote(e.get('validity_conditions'))}", ""]
    else:
        out += [NONE, ""]

    out += ["## Disputed and withdrawn", ""]
    disputed = []
    for eid in eids:
        stt, st = status(d, eid)
        if stt == "current":
            continue
        others = sorted(set(st["refuted_by"]) | set(st["superseded_by"]) | set(d.entries[eid].get("conflict_with") or []))
        links = ", ".join(f"[{cell(o)}]({rel(me, 'entries/' + o + '.json')})" for o in others) or "none named"
        disputed.append(f"- [{cell(eid)}]({rel(me, 'entries/' + eid + '.json')}): {STATUS_WORDS[stt]}; the other side: {links}")
    out += (disputed if disputed else [NONE]) + [""]

    out += ["## Reading", ""]
    word = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(pid)}(?![A-Za-z0-9_])") if pid else None
    reading = [n for n in sorted(d.distilled) if word and word.search(d.distilled[n])]
    out += ([f"- [{cell(n)}]({rel(me, 'distilled/' + n)})" for n in reading] if reading else [NONE]) + [""]

    out += ["## Related", ""]
    mine = set(eids)
    related = sorted(k for k, v in on.items() if k != (section, pid) and mine & set(v))
    lines = [f"- [{k[0]} {k[1]}]({rel(me, 'wiki/' + page_path(*k))})" if k[0] != "unfiled"
             else f"- [unfiled entries]({rel(me, 'wiki/unfiled.md')})" for k in related]
    if section == "device" and f"safety_{pid}.md" in d.guides:
        lines.append(f"- [safety guide]({rel(me, 'guides/safety_' + pid + '.md')})")
    out += (lines if lines else [NONE]) + [""]

    out += ["---", "", footer(d.version), ""]
    return "\n".join(out)


def render_index(d: Data, on: dict) -> str:
    me = "index.md"
    out = ["# The knowledge store", "", "Every page the wiki holds, by section.", "", CITE, ""]
    out += ["## The store", "", f"- version: {d.version}", f"- entries: {len(d.entries)}"]
    for s in SECTIONS:
        out.append(f"- {s} pages: {sum(1 for k in on if k[0] == s)}")
    out.append(f"- entries with no subject: {len(on[('unfiled', '')])}")
    out.append("")
    out += ["## Other views", "",
            f"- [the store by kind of evidence]({rel(me, 'wiki/evidence.md')})",
            f"- [the map: coverage and shared entries, per subject]({rel(me, 'wiki/map.md')})", ""]
    for s in SECTIONS:
        out += [f"## {s.capitalize()} pages", ""]
        ks = sorted(k for k in on if k[0] == s)
        out += ([f"- [{cell(k[1])}]({rel(me, 'wiki/' + page_path(*k))}) ({len(on[k])} entries)" for k in ks]
                if ks else [NONE]) + [""]
    unused = sorted(q for q in d.quantities if ("quantity", q) not in on)
    out += ["## Registered quantities no entry uses", ""]
    out += ([f"- {cell(q)}" for q in unused] if unused else [NONE]) + [""]
    out += ["## Unfiled", "", f"- [unfiled entries]({rel(me, 'wiki/unfiled.md')}) ({len(on[('unfiled', '')])} entries)", ""]
    out += ["---", "", footer(d.version), ""]
    return "\n".join(out)


# -- the store by kind of evidence, and the map (task 060) ------------------------------------------

def subject_pages(on: dict, eid: str) -> list[tuple[str, str]]:
    return sorted(k for k, v in on.items() if k[0] != "unfiled" and eid in v)


def grade_of(d: Data, eid: str) -> str:
    g = d.entries[eid].get("grade")
    if g not in GRADES:
        raise SystemExit(f"entry {eid} carries grade {g!r}, which has no section; fix the entry")
    return g


def render_evidence(d: Data, on: dict) -> str:
    me = "evidence.md"
    out = ["# The store by kind of evidence", "",
           "Every entry in the store, under how it is known, in the server's order.", "", CITE, ""]
    by = {g: [] for g in GRADES}
    for eid in sorted(d.entries, key=d.store.sort_key):
        by[grade_of(d, eid)].append(eid)
    for g in GRADES:
        n = len(by[g])
        out += [f"## {GRADE_WORDS[g].capitalize()} ({g}): {n} {'entry' if n == 1 else 'entries'}", ""]
        if not by[g]:
            out += [NONE, ""]
            continue
        out += ["| entry | source kind | grade and source as recorded | status | subject pages |",
                "|---|---|---|---|---|"]
        for eid in by[g]:
            e = d.entries[eid]
            kind = str(e.get("source") or "").split(":", 1)[0]
            pages = subject_pages(on, eid)
            where = (", ".join(f"[{k[0]} {cell(k[1])}]({rel(me, 'wiki/' + page_path(*k))})" for k in pages)
                     if pages else f"none; [unfiled entries]({rel(me, 'wiki/unfiled.md')})")
            out.append("| " + " | ".join([
                f"[{cell(eid)}]({rel(me, 'entries/' + eid + '.json')})",
                cell(SOURCE_WORDS.get(kind, "source kind not recognised")),
                cell(f"{e.get('grade')}{MIDDOT}{e.get('source')}"),
                cell(STATUS_WORDS[d.store.standing(eid)["status"]]), where]) + " |")
        out.append("")
    out += ["---", "", footer(d.version), ""]
    return "\n".join(out)


def coverage(d: Data, on: dict, key) -> tuple[dict, int]:
    """Counts of entries on a page by grade, zeros written, and how many are refuted, superseded or in conflict."""
    c = {g: 0 for g in GRADES}
    for eid in on[key]:
        c[grade_of(d, eid)] += 1
    return c, sum(1 for eid in on[key] if status(d, eid)[0] != "current")


def map_doc(d: Data, on: dict) -> dict:
    """Nodes and typed edges, every edge naming the entry whose own field states it. No value from an entry."""
    held = d.entries
    subjects = sorted(k for k in on if k[0] != "unfiled")
    nodes = []
    for k in subjects:
        c, disputed = coverage(d, on, k)
        nodes.append({"id": "page:" + page_path(*k)[:-3], "kind": k[0], "page": page_path(*k),
                      "coverage": c, "disputed": disputed})
    for eid in held:
        e = held[eid]
        nodes.append({"id": "entry:" + eid, "kind": "entry", "grade": e.get("grade"), "source": e.get("source"),
                      "status": d.store.standing(eid)["status"]})
    edges, dangling = set(), set()
    for k in subjects:
        for eid in on[k]:
            edges.add(("about", "entry:" + eid, "page:" + page_path(*k)[:-3], eid))
    # entry-to-entry relations, each drawn once: (type, from, to) -> the entries whose fields state it.
    # conflict_with is one relation per pair whichever side states it; refuted_by and superseded_by are
    # the other side's statement of refutes and supersedes, so they join the same edge.
    stated: dict[tuple[str, str, str], set[str]] = {}
    def state(t, a, b, by, field, names):
        if names not in held:
            dangling.add((by, field, names))
        else:
            stated.setdefault((t, a, b), set()).add(by)
    for eid in sorted(held):
        e = held[eid]
        for o in e.get("conflict_with") or []:
            a, b = sorted((eid, o)) if o in held else (eid, o)
            state("conflict_with", a, b, eid, "conflict_with", o)
        for o in e.get("refutes") or []:
            state("refutes", eid, o, eid, "refutes", o)
        for o in e.get("refuted_by") or []:
            state("refutes", o, eid, eid, "refuted_by", o)
        sup = e.get("supersedes")
        for o in ([sup] if isinstance(sup, str) else sup or []):
            state("supersedes", eid, o, eid, "supersedes", o)
        for o in e.get("superseded_by") or []:
            state("supersedes", o, eid, eid, "superseded_by", o)
        # `supports` and `inputs` name what this entry rests on, so the edge runs from that entry to this one
        for s in e.get("supports") or []:
            if isinstance(s, dict) and s.get("entry"):
                state("supports", s["entry"], eid, eid, "supports", s["entry"])
        for o in e.get("inputs") or []:
            if o in held:                   # an input is a quantity name unless it names an entry; never dangling
                state("input_of", o, eid, eid, "inputs", o)
    for (t, a, b), bys in stated.items():
        if t == "conflict_with" and a not in bys:
            a, b = b, a                     # a one-way conflict is drawn from the side that states it
        edges.add((t, "entry:" + a, "entry:" + b, a if a in bys else min(bys)))
    return {"artifact": "kb_map", "schema_version": "0.1", "kb_version": d.version, "footer": footer(d.version),
            "nodes": sorted(nodes, key=lambda n: n["id"]),
            "edges": [{"type": t, "from": a, "to": b, "stated_by": s} for t, a, b, s in sorted(edges)],
            "dangling": [{"stated_by": s, "field": f, "names": n} for s, f, n in sorted(dangling)]}


def render_map_json(doc: dict) -> str:
    return json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n"


def render_map_md(d: Data, on: dict) -> str:
    me = "map.md"
    out = ["# The map of the store", "",
           "For each subject page: how many of its entries are known each way, how many are disputed, "
           "and which pages share entries with it.", "", CITE, "",
           f"The same relations, as data for the console to draw: [map.json]({rel(me, 'wiki/map.json')}).", "",
           "## Kinds of evidence", ""]
    out += [f"- {g}: {GRADE_WORDS[g]}" for g in GRADES]
    out += ["- disputed: refuted, superseded or in conflict", ""]
    for s in SECTIONS:
        out += [f"## {s.capitalize()} pages", ""]
        ks = sorted(k for k in on if k[0] == s)
        if not ks:
            out += [NONE, ""]
            continue
        out += ["| page | " + " | ".join(GRADES) + " | disputed | shares entries with |",
                "|---|" + "---|" * len(GRADES) + "---|---|"]
        for k in ks:
            c, disputed = coverage(d, on, k)
            mine = set(on[k])
            shares = sorted(o for o in on if o[0] != "unfiled" and o != k and mine & set(on[o]))
            out.append("| " + " | ".join(
                [f"[{cell(k[1])}]({rel(me, 'wiki/' + page_path(*k))})"] + [str(c[g]) for g in GRADES]
                + [str(disputed), ", ".join(f"[{o[0]} {cell(o[1])}]({rel(me, 'wiki/' + page_path(*o))})"
                                            for o in shares) or "none"]) + " |")
        out.append("")
    out += ["---", "", footer(d.version), ""]
    return "\n".join(out)


def render_all(d: Data) -> dict[str, str]:
    on = pages_of(d)
    pages = {"index.md": render_index(d, on)}
    for (section, pid) in sorted(on):
        pages[page_path(section, pid)] = render(d, section, pid, on)
    pages["evidence.md"] = render_evidence(d, on)
    pages["map.md"] = render_map_md(d, on)
    pages["map.json"] = render_map_json(map_doc(d, on))
    return pages


def raw_html(text: str) -> bool:
    """A '<' that could open a tag, outside code blocks and code spans, and not escaped."""
    prose = re.sub(r"```.*?```", "", text, flags=re.S)
    prose = re.sub(r"`[^`\n]*`", "", prose)
    return re.search(r"(?<!\\)<[A-Za-z/!?]", prose) is not None


# -- the self-test -------------------------------------------------------------------------------

def _synthetic() -> Data:
    def entry(eid, subjects=(), numbers=None, **kw):
        e = {"entry_id": eid, "kind": "claim", "claim": f"claim of {eid} with a <tag> and a | bar",
             "validity_conditions": f"conditions of {eid}, line one\nline two", "grade": "E3",
             "source": "spec:x", "grade_tag": "vendor_spec",
             "subject": [{"kind": k, "id": i} for k, i in subjects]}
        if numbers:
            e["numbers"] = numbers
        e.update(kw)
        return e
    ents = {e["entry_id"]: e for e in [
        entry("e_current", [("device", "dev_a")], [{"name": "q_used", "value": 1.5, "unit": "um",
                                                     "source": "calibration:c1", "grade": "E2"}]),
        entry("e_two", [("device", "dev_a"), ("device", "dev_b")]),
        entry("e_conflict_a", [("device", "dev_b")], conflict_with=["e_conflict_b"]),
        entry("e_conflict_b", [("device", "dev_b")], conflict_with=["e_conflict_a"]),
        entry("e_refuted", [("device", "dev_c")], refuted_by=["e_refuter"]),
        entry("e_refuter", [("device", "dev_c")], refutes=["e_refuted"], grade="E1", source="measured:run-1"),
        entry("e_old", [("device", "dev_c")]),
        entry("e_new", [("device", "dev_c")], supersedes="e_old"),
        entry("e_unfiled", []),
        entry("e_pix_10x", [("quantity", "q_used")], [{"name": "q_used", "value": 0.65, "unit": "um",
                                                         "source": "calibration:c1", "grade": "E2"}],
              identifiers={"nominal_magnification": "10x", "intermediate_magnification": "1x",
                           "applies_to": "only the bottle in use"}),
        entry("e_pix_20x", [("quantity", "q_used")], [{"name": "q_used", "value": 0.65, "unit": "um",
                                                         "source": "calibration:c1", "grade": "E2"}],
              identifiers={"nominal_magnification": "20x", "intermediate_magnification": "1x"}),
        # 060: an E2 entry for evidence.md; an edge to an entry the store lacks; a coverage page
        entry("e_calib", [("device", "dev_d")], grade="E2", source="calibration:c2"),
        entry("e_dangling", [("device", "dev_d")], conflict_with=["e_missing"]),
        entry("e_cov_e1", [("device", "dev_e")], grade="E1", source="measured:run-2", refutes=["e_cov_e3"]),
        entry("e_cov_e3", [("device", "dev_e")]),
    ]}
    for e in ents.values():
        if not e["subject"]:
            del e["subject"]
    store = mcp_server.Store(log=Path("unused.jsonl"), _index={"kb_version": "kbv-000000000000"}, _entries=ents)
    return Data(store, [{"id": "q_used", "definition": "used <q>", "unit": "um", "kind": "physical"},
                        {"id": "q_unused", "definition": "unused", "unit": "1", "kind": "physical"}],
                [{"id": "obs_empty", "definition": "an observable nothing measures", "units": ["1"], "estimator": "none"}],
                {"channels": [{"id": "dev_a", "role": "a device"}]}, {"instances": []},
                {"note_dev_a.md": "mentions dev_a here"}, {"safety_dev_a.md"}, "kbv-000000000000")


def _self_test() -> int:
    bad = []
    d = _synthetic()
    p = render_all(d)
    def has(page, text, why):
        if page not in p:
            bad.append(f"{page} missing ({why})")
        elif text not in p[page]:
            bad.append(f"{page} lacks {text!r} ({why})")
    # an entry with two subjects is on both pages
    has("device_dev_a.md", "e_two", "two subjects: first page")
    has("device_dev_b.md", "e_two", "two subjects: second page")
    # one entry per status, on its page, with the other side named
    has("device_dev_b.md", "e_conflict_a.json): in conflict; the other side: [e_conflict_b]", "conflict")
    has("device_dev_c.md", "e_refuted.json): refuted; the other side: [e_refuter]", "refuted")
    has("device_dev_c.md", "e_old.json): superseded; the other side: [e_new]", "superseded")
    if "e_current.json): " in p.get("device_dev_a.md", "").split("## Disputed and withdrawn")[-1].split("## Reading")[0]:
        bad.append("a current entry was listed as disputed")
    # an observable with no entries still has its page; an unused quantity does not
    has("observable_obs_empty.md", "## Values", "observable with no entries")
    if "quantity_q_unused.md" in p:
        bad.append("an unused quantity got an empty page")
    has("index.md", "- q_unused", "unused quantity listed on the index")
    has("unfiled.md", "e_unfiled", "entry with no subject")
    # revision (1): the grade in words AND the grade and source as recorded
    has("device_dev_a.md", "calibrated on this instrument; a calibration on this instrument", "grade in words")
    has("device_dev_a.md", "| E2" + MIDDOT + "calibration:c1 |", "grade code and source as recorded")
    # revision (2): the footer, one fixed line, no <sub>
    line = footer(d.version)
    md = {n: t for n, t in p.items() if n.endswith(".md")}
    for name, text in md.items():
        if text.rstrip("\n").splitlines()[-1] != line:
            bad.append(f"{name}: last line is not the fixed footer")
        if "<sub>" in text:
            bad.append(f"{name}: carries <sub>")
    # revision (3): no raw or inline HTML; conditions as a blockquote
    for name, text in md.items():
        if raw_html(text):
            bad.append(f"{name}: raw HTML")
    has("device_dev_c.md", "> conditions of e_refuted, line one line two", "conditions as a blockquote")
    # revision (4): ASCII file names, and every link stays inside kb/
    for name, text in md.items():
        if not all(ord(ch) < 128 for ch in name):
            bad.append(f"{name}: not an ASCII file name")
        depth = name.count("/") + 1
        for target in re.findall(r"\]\(([^)]+)\)", text):
            ups = target.split("/").count("..")
            if target.startswith(("/", "http:", "https:")) or ":" in target.split("/")[0] or ups > depth:
                bad.append(f"{name}: link {target} leaves kb/")
    # 055: two entries that differ only in an identifier render two rows that differ in that column;
    # applies_to stays out of the column and is shown verbatim beside the entry
    qrows = [l for l in p.get("quantity_q_used.md", "").splitlines() if l.startswith("| q_used ")]
    r10 = [l for l in qrows if "e_pix_10x" in l]
    r20 = [l for l in qrows if "e_pix_20x" in l]
    if not (r10 and r20 and "| intermediate_magnification: 1x; nominal_magnification: 10x |" in r10[0]
            and "| intermediate_magnification: 1x; nominal_magnification: 20x |" in r20[0]):
        bad.append("rows differing only in an identifier do not show it in an identifiers column")
    if any("only the bottle in use" in l for l in qrows):
        bad.append("applies_to was put in the identifiers column")
    has("quantity_q_used.md", "only the bottle in use", "applies_to shown beside the entry")
    has("device_dev_a.md", "| none |", "an entry with no identifiers shows none")
    odd = _synthetic()
    odd.entries["e_current"]["subject"] = [{"kind": "device", "id": "dev_" + chr(233)}]
    try:
        render_all(odd)
        bad.append("a non-ASCII subject id was rendered to a file name instead of refused")
    except SystemExit:
        pass
    has("device_dev_a.md", "(../guides/safety_dev_a.md)", "the device's guide, inside kb/")
    has("device_dev_a.md", "(../distilled/note_dev_a.md)", "reading, inside kb/")
    # 060: the map and the evidence page
    m = json.loads(p.get("map.json", "{}"))
    edges = m.get("edges") or []
    pair = [x for x in edges if x.get("type") == "conflict_with"
            and {x.get("from"), x.get("to")} == {"entry:e_conflict_a", "entry:e_conflict_b"}]
    if len(pair) != 1:
        bad.append(f"a two-way conflict drew {len(pair)} conflict_with edges, not one")
    if any("e_missing" in (x.get("from"), x.get("to")) or "entry:e_missing" in (x.get("from"), x.get("to"))
           for x in edges):
        bad.append("an edge to an entry the store lacks was drawn")
    if {"stated_by": "e_dangling", "field": "conflict_with", "names": "e_missing"} not in (m.get("dangling") or []):
        bad.append("an edge to an entry the store lacks is not listed under dangling")
    ev = p.get("evidence.md", "")
    e2 = ev.split("## Calibrated on this instrument (E2)")[-1].split("\n## ")[0] if "(E2)" in ev else ""
    if not re.search(r"\| \[e_calib\]\([^)]*\) \| [^|]+ \| E2" + re.escape(MIDDOT) + r"calibration:c2 \| current \|", e2):
        bad.append("evidence.md does not put the E2 entry under the calibrated section with its status")
    stack, valued = [m], False
    while stack:
        x = stack.pop()
        if isinstance(x, dict):
            valued = valued or bool({"value", "values"} & set(x))
            stack.extend(x.values())
        elif isinstance(x, list):
            stack.extend(x)
    if valued or not m:
        bad.append("the map holds a key named value or values, or did not parse")
    node = next((x for x in m.get("nodes") or [] if x.get("id") == "page:device_dev_e"), {})
    if node.get("coverage") != {"E1": 1, "E2": 0, "E3": 1, "E4": 0, "E5": 0} or node.get("disputed") != 1:
        bad.append(f"coverage of a page with one E1 and one refuted E3 reads {node.get('coverage')}, "
                   f"disputed {node.get('disputed')}")
    if p.get("map.json", "").endswith("\n\n") or not p.get("map.json", "").endswith("}\n"):
        bad.append("map.json is not one JSON document and one LF")
    # deterministic
    if render_all(_synthetic()) != p:
        bad.append("two renders of one store differ")
    for b in bad:
        print("FAIL:", b)
    print("self-test: ok" if not bad else f"self-test: FAILED ({len(bad)})")
    return 1 if bad else 0


# -- main ----------------------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="fail if any page differs from what the store renders")
    ap.add_argument("--self-test", action="store_true", help="exercise the rules on a synthetic store")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()
    d = load()
    pages = render_all(d)
    on_disk = {str(p.relative_to(WIKI)).replace("\\", "/") for p in WIKI.rglob("*.md")} if WIKI.exists() else set()
    if a.check:
        stale = sorted(n for n, t in pages.items()
                       if not (WIKI / n).exists() or (WIKI / n).read_text(encoding="utf-8").replace("\r\n", "\n") != t)
        extra = sorted(on_disk - set(pages))
        ok = len(pages) - len(stale)
        print(f"{ok} of {len(pages)} pages current" + (f"; stale: {stale[:10]}" if stale else "")
              + (f"; not rendered by the store, remove: {extra}" if extra else ""))
        return 1 if stale or extra else 0
    for n, t in pages.items():
        f = WIKI / n
        f.parent.mkdir(parents=True, exist_ok=True)
        with open(f, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(t)
    for n in sorted(on_disk - set(pages)):
        (WIKI / n).unlink()
    counts = {s: sum(1 for n in pages if n.startswith(s + "_")) for s in SECTIONS}
    print(f"wrote {len(pages)} pages to {WIKI} from {d.version}: {counts}, index, unfiled")
    return 0


if __name__ == "__main__":
    sys.exit(main())
