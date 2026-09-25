#!/usr/bin/env python3
"""Render one safety guide per device from the store: kb/guides/safety_<device_id>.md.

The guides are GENERATED. The entries, the source records and the device
table's gaps are the authority (P3); a guide is how the person reads them. A
correction goes into an entry and the guide is regenerated -- editing a guide
by hand has no effect beyond the next run, and --check says so.

What a guide holds, for every device in the device table, including those the
archive has nothing for:

  1. what the manufacturer warns about, in plain words, each line with the
     document and page it came from;
  2. the manufacturer's figures, labelled as theirs and not measured here;
  3. what is missing -- manuals the archive does not hold, parts not read,
     and where two of the manufacturer's documents disagree;
  4. a closing line saying the page is not the lab's safety limits.

Which entries are safety statements is recorded where the reading was done:
each document's source record lists them under `safety_entries`, with the
printed and PDF page, and may carry `guide_notes` in plain words for the
devices named in `guide_devices`. An entry about a device that no source lists there is
not a manufacturer's safety statement and does not appear. A gap appears when
it names the device under `device`.

THE READER IS THE PERSON, so the body carries no internal codes: no entry or
gap ids, no grades, no section or check numbers, no seat names. Identifiers
in parentheses are removed from gap text, device ids are replaced by plain
names, and the renderer REFUSES to write a guide in which a snake_case
identifier survives -- a leak is a failure to fix at the source, not to hide.

    python3 librarian_agent/src/safety_guides.py          # write the guides
    python3 librarian_agent/src/safety_guides.py --check  # fail if any is stale
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

AGENT = Path(__file__).resolve().parent.parent
KB = AGENT / "kb"
GUIDES = KB / "guides"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import kb_index  # noqa: E402

#: Plain names for the person. The model is given only where the store holds it.
DEVICE_NAMES = {
    "optical_tweezers": "Optical tweezers (Aresis Tweez 300)",
    "piezo_stage": "Piezo stage and its controller (Queensgate)",
    "stand_ti2e": "Microscope stand (Nikon Ti2-E)",
    "laser_combiner": "Confocal laser combiner (Nikon LUN-F, four lines)",
    "confocal_csuw1": "Spinning-disk confocal unit (Yokogawa CSU-W1)",
    "widefield_source_a": "Widefield light engine A (a Lumencor Spectra III or Aura III -- which one is not yet known)",
    "widefield_source_b": "Widefield light engine B (a Lumencor Spectra III or Aura III -- which one is not yet known)",
    "camera_red": "Camera on the red arm (Photometrics Kinetix)",
    "camera_blue": "Camera on the blue arm (Photometrics Kinetix)",
    "dmd": "Patterned illumination (Mightex Polygon1000)",
}
ELEMENT_NAMES = {
    "light_path_port": "the stand's light-path selector", "nosepiece": "the nosepiece",
    "z_drive": "the focus drive", "filter_turret_1": "filter turret 1", "filter_turret_2": "filter turret 2",
    "lapp_branch": "the Lapp branch mirror", "line_select": "the combiner's line blanking",
}
LEAK = re.compile(r"\b[a-z][a-z0-9]*_[a-z0-9_]+\b")


def plain(text: str) -> str:
    """Strip identifiers from text written for the record, for the person."""
    text = re.sub(r"\s*\((?:[a-z][a-z0-9]*_[a-z0-9_]+(?:,\s*)?)+\)", "", text)
    for k, v in {**DEVICE_NAMES, **ELEMENT_NAMES}.items():
        text = re.sub(rf"\b{k}\b", v.split(" (")[0].lower() if k in DEVICE_NAMES else v, text)
    return text


def figure(n: dict) -> str:
    v, u = n["value"], n["unit"]
    if u == "K":
        return f"{v - 273.15:g} °C"
    if u == "1" and "humidity" in n["name"]:
        return f"{v * 100:g} % relative humidity"
    if u == "1":
        return f"{v:g} (a number with no unit)"
    return f"{v:g} {u}"


def where(refs: list[dict]) -> str:
    by_doc: dict[str, list] = {}
    for r in refs:
        pages = by_doc.setdefault(r["document"], [])
        if (r["printed_page"], r["pdf_page"]) not in pages:
            pages.append((r["printed_page"], r["pdf_page"]))
    parts = []
    for doc, pages in by_doc.items():
        word = "page" if len(pages) == 1 else "pages"
        parts.append(f"{doc}, {word} " + ", ".join(str(p) for p, _ in pages)
                     + " (PDF " + ", ".join(str(q) for _, q in pages) + ")")
    return "; ".join(parts)


def load() -> tuple[dict, dict, dict, str]:
    entries = {}
    for p in sorted((KB / "entries").glob("*.json")):
        e = json.loads(p.read_text(encoding="utf-8"))
        entries[e["entry_id"]] = e
    sources = {}
    for p in sorted((KB / "sources").glob("*.json")):
        s = json.loads(p.read_text(encoding="utf-8"))
        sources[s["source_id"]] = s
    table = json.loads((KB / "staging" / "devices.v0.json").read_text(encoding="utf-8"))
    return entries, sources, table, kb_index.build(KB)["kb_version"]


def render(dev: str, entries: dict, sources: dict, table: dict, version: str) -> str:
    listed: dict[str, list] = {}
    for s in sources.values():
        for eid, refs in (s.get("safety_entries") or {}).items():
            listed.setdefault(eid, []).extend(refs)
    mine = sorted((eid for eid in listed if eid in entries
                   and dev in {x["id"] for x in entries[eid].get("subject") or []}),
                  key=lambda eid: (listed[eid][0]["document"], listed[eid][0]["printed_page"], eid))
    gaps = [g for g in table.get("gaps", []) if dev in (g.get("device") or [])]
    notes = [n for sid in sorted(sources) for n in (sources[sid].get("guide_notes") or [])
             if dev in (sources[sid].get("guide_devices") or [])]

    out = [f"# Safety guide: {DEVICE_NAMES.get(dev, dev)}", ""]
    out += ["What the manufacturer's own documents on this computer say about this device's hazards, "
            "and where they say it. Everything here is the manufacturer's statement; nothing on this "
            "page was measured on this bench.", ""]

    out += ["## What the manufacturer warns about", ""]
    if mine:
        for eid in mine:
            out.append(f"- {plain(entries[eid]['claim'])}  ")
            out.append(f"  *Source: {where(listed[eid])}.*")
        out.append("")
    else:
        out += ["**Nothing.** No manufacturer's manual for this device is on this computer, so this page "
                "has no warnings to give. That is not the same as the device having none.", ""]

    figs = [(eid, n) for eid in mine for n in entries[eid].get("numbers") or []]
    out += ["## The manufacturer's figures", ""]
    if figs:
        out += ["These are the manufacturer's printed figures. None has been measured or confirmed here, "
                "and none is a limit anyone on this bench has set.", ""]
        for eid, n in figs:
            label = re.sub(r"^(tweez|npcd|nanobench)_", "", n["name"]).replace("_", " ")
            label = label[0].upper() + label[1:]
            note = n.get("note") or ""
            note = "" if note == "the manufacturer's figure" else f" -- {plain(note)}"
            out.append(f"- {label}: {figure(n)}{note} *({where(listed[eid][:1])})*")
        out.append("")
    else:
        out += ["None.", ""]

    out += ["## What is missing", ""]
    if gaps or notes:
        for g in gaps:
            line = f"- **{plain(g['what'][0].upper() + g['what'][1:])}.** {plain(g['why_it_matters'])[0].upper() + plain(g['why_it_matters'])[1:]}."
            if g.get("what_would_close_it"):
                line += f" What would close it: {plain(g['what_would_close_it'])}."
            if g.get("do_not"):
                dn = plain(g["do_not"]); line += f" {dn[0].upper() + dn[1:]}"
            out.append(line)
        for n in notes:
            out.append(f"- {n}")
    else:
        out.append("- Nothing known to be missing.")
    disagree = [eid for eid in mine if entries[eid].get("conflict_with")]
    if disagree:
        out.append("- **The manufacturer's documents disagree here**, and both readings are kept:")
        for eid in disagree:
            out.append(f"  - {plain(entries[eid]['claim'])} *({where(listed[eid][:1])})*")
    out.append("")

    out += ["---", "",
            "**This page is not the lab's safety limits.** It says what the manufacturer warns about. "
            "What may be done on this bench, and every limit anyone acts on, is written by the person "
            "into the instrument's safety file after confirming it on the instrument.", "",
            f"<sub>Generated from the knowledge store at {version}. Do not edit by hand: correct the "
            "store and regenerate.</sub>", ""]
    text = "\n".join(out)
    body = text.rsplit("<sub>", 1)[0]
    leaked = sorted(set(LEAK.findall(body)))
    if leaked:
        raise SystemExit(f"safety_{dev}.md would carry internal identifiers: {leaked}. "
                         "Fix the wording at its source (the entry, the gap or the source record).")
    return text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="fail if any guide differs from what the store renders")
    a = ap.parse_args(argv)
    entries, sources, table, version = load()
    devices = [c["id"] for c in table["channels"]]
    GUIDES.mkdir(exist_ok=True)
    stale = []
    for dev in devices:
        text = render(dev, entries, sources, table, version)
        p = GUIDES / f"safety_{dev}.md"
        if a.check:
            if not p.exists() or p.read_text(encoding="utf-8").replace("\r\n", "\n") != text:
                stale.append(p.name)
        else:
            p.write_text(text, encoding="utf-8", newline="\n")
    if a.check:
        print(f"{len(devices) - len(stale)} of {len(devices)} guides current" + (f"; stale: {stale}" if stale else ""))
        return 1 if stale else 0
    print(f"wrote {len(devices)} guides to {GUIDES} from {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
