#!/usr/bin/env python3
"""Rebuild kb/index.json.

Store maintenance, not agent behaviour: until M3 a person curates the store by
hand and runs this. The index exists so that a card citing kb:<entry_id> can be
checked against what the store actually says -- the grade a card claims to have
inherited is verified, not trusted (check 21).

kb_version is a content hash over every entry. A card pins it (check 33) so that
siblings in one fan-out all read the same knowledge, and so that rerunning a
question at the same kb_version gives the same constraints.

    python3 librarian_agent/src/kb_index.py [--check]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

KB = Path(__file__).resolve().parent.parent / "kb"
CONTRACTS = Path(__file__).resolve().parent.parent.parent / "contracts"

# The same closed list the server reads, from the same place, for the same
# reason: a second copy of a registry is a registry that drifts.
ADDRESSABLE = tuple(json.loads((CONTRACTS / "schemas" / "kb_entry.schema.json").read_text(
)).get("addressable_identifiers", {}).get("addressable", ()))


def handles(entry: dict) -> list[tuple[str, str]]:
    """Every name this entry answers to, each with where it came from."""
    out = [(entry["entry_id"], "entry_id")]
    if entry.get("symbol"):
        out.append((entry["symbol"], "symbol"))
    for n in entry.get("numbers") or []:
        if n.get("name"):
            out.append((n["name"], "number"))
    for s in entry.get("subject") or []:
        if s.get("id"):
            out.append((s["id"], f"subject:{s.get('kind')}"))
    for k, v in (entry.get("identifiers") or {}).items():
        if k in ADDRESSABLE and v:
            out.append((str(v), f"identifier:{k}"))
    return out


def collisions(entries: dict[str, dict]) -> list[dict]:
    """Names that more than one entry answers to, and which kind each is.

    The policy is RETURN BOTH, not refuse. kb_query is a set-returning tool --
    `na` has returned six objectives since the day they were entered -- and
    refusing a shared name would break the class handles the ruling admits on
    purpose: `immersion: oil` is supposed to return every oil lens. Refusing
    would also fail closed in the wrong direction, hiding entries that exist.

    What is caught is the collision that crosses KINDS. Several entries
    answering to one name through the same kind of handle is not an accident,
    it is the design: three entries name `camera_red` as their subject because
    three facts are about that camera, and six carry a number called `na`
    because six lenses have one. A name arriving from two DIFFERENT kinds --
    a part number equal to some other entry's id, a model equal to a subject --
    is the accident, because it makes an entry answerable by a name that is not
    about it. That is the defect `subject` was introduced to remove, and
    widening the namespace is exactly when it comes back.

    The first version of this function classified by identifier key rather than
    by kind, and called every shared subject an accident -- nine rows of
    "look at these" of which nine were normal. A report that cries at normal
    structure is one people stop reading, which is the same failure as not
    having it.
    """
    seen: dict[str, list[tuple[str, str]]] = {}
    for eid, e in entries.items():
        for name, origin in handles(e):
            seen.setdefault(name.casefold(), []).append((eid, origin))
    out = []
    for folded, rows in sorted(seen.items()):
        owners = {eid for eid, _ in rows}
        if len(owners) < 2:
            continue
        origins = {origin for _, origin in rows}
        if len(origins) > 1:
            kind = "cross_kind"
        else:
            only = next(iter(origins))
            kind = ("class_handle" if only.startswith("identifier:")
                    else "shared_subject" if only.startswith("subject:")
                    else "shared_quantity" if only == "number"
                    else "shared_" + only)
        out.append({"name": folded, "kind": kind,
                    "entries": sorted(owners), "via": sorted(origins)})
    return out


def entry_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(kb: Path | None = None) -> dict:
    kb = kb or KB
    entries = {}
    for p in sorted((kb / "entries").glob("*.json")):
        data = json.loads(p.read_text())
        entries[data["entry_id"]] = {
            "file": f"entries/{p.name}",
            "kind": data["kind"],
            "grade": data["grade"],
            "grade_tag": data.get("grade_tag"),
            "symbol": data.get("symbol"),
            "formula": data.get("formula"),
            "source_ref": data["source_ref"],
            "sha256": entry_digest(p),
        }
    blob = json.dumps(entries, sort_keys=True, separators=(",", ":"))
    version = "kbv-" + hashlib.sha256(blob.encode()).hexdigest()[:12]
    parsed = {eid: json.loads((kb / meta["file"]).read_text()) for eid, meta in entries.items()}
    found = collisions(parsed)
    return {
        "schema_version": "0.1",
        "note": "Generated by librarian_agent/src/kb_index.py. Do not hand-edit: the entries are authoritative and this is their index.",
        "kb_version": version,
        "entry_count": len(entries),
        "handles": {
            "policy": "return both. kb_query returns sets, and a shared name is usually a class the "
                      "ruling admits -- immersion oil should return every oil lens. A collision is "
                      "reported rather than refused, because refusing would hide entries that exist.",
            "matching": "case-insensitive, and nothing beyond case. Whitespace and punctuation are not "
                        "normalised: case has one obvious mapping and the others are guesses about "
                        "which string the caller meant.",
            "shared_subject": "several entries about one device or quantity. Expected -- it is what "
                              "subject is for.",
            "shared_quantity": "several entries carrying a number of the same name. Expected.",
            "class_handle": "one identifier key shared by several entries, such as immersion oil. "
                            "Expected, and the ruling predicted it.",
            "cross_kind": "one name arriving from two DIFFERENT kinds of handle. This is the accident: "
                          "it makes an entry answerable by a name that is not about it. Look at these, "
                          "and only these.",
            "collisions": found,
        },
        "entries": entries,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="fail if index.json is stale instead of rewriting it")
    args = ap.parse_args(argv)
    fresh = build()
    target = KB / "index.json"
    if args.check:
        if not target.exists():
            print("index.json is missing")
            return 1
        current = json.loads(target.read_text())
        if current.get("kb_version") != fresh["kb_version"]:
            print(f"index.json is stale: {current.get('kb_version')} but entries hash to {fresh['kb_version']}")
            return 1
        # kb_version hashes the entry table only, so a derived field -- the
        # handle collisions -- can go stale while the version still matches.
        # Comparing the whole document is what makes that visible.
        if current != fresh:
            differing = sorted(k for k in set(current) | set(fresh) if current.get(k) != fresh.get(k))
            print(f"index.json matches at {fresh['kb_version']} but its derived fields are stale: {differing}")
            return 1
        print(f"index.json is current at {fresh['kb_version']} ({fresh['entry_count']} entries), "
              f"{len(fresh['handles']['collisions'])} handle collisions")
        return 0
    target.write_text(json.dumps(fresh, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {target.name}: {fresh['kb_version']} ({fresh['entry_count']} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
