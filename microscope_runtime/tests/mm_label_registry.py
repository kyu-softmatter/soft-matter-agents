"""A test registry that gives registry names Micro-Manager labels (card 091), for tests only.

The real snapshot carries no `mm_label` rows yet, so every test that needs a camera tap or a name
resolved to a label reads one of these instead, patched in as `orch.REGISTRY_LOOKUP`. It is the real
device table of `microscope_agent/envelope/snapshot.json` with labels added on `camera_red`,
`camera_blue` and the element `dia_lamp`, plus synthetic entries the labels cite. Nothing here is a
fact about the instrument: the labels, grades and digests are the test's own.

    path = mm_label_registry.write(folder)                                   # all three labelled, E1
    path = mm_label_registry.write(folder, grade={"camera_red": "E3"})       # one entry graded E3
    path = mm_label_registry.write(folder, labels={"camera_blue": None})     # one row without a label
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REAL_SNAPSHOT = REPO / "microscope_agent" / "envelope" / "snapshot.json"

#: the labels the test registry gives, by registry name, and the entry each cites
DEFAULT_LABELS = {"camera_red": "Kinetix_red", "camera_blue": "Kinetix_blue", "dia_lamp": "DiaLamp"}


def digest(text: str) -> str:
    """A test's stand-in for an approved configuration's sha256: the sha256 of a string it names."""
    return hashlib.sha256(text.encode()).hexdigest()


CONFIG_A = digest("configuration A, as the test names it")
CONFIG_B = digest("configuration B, as the test names it")


def entry_ref(name: str) -> str:
    return f"mm_label_{name}"


def write(folder, *, labels: dict | None = None, grade: dict | None = None,
          entry_digest: dict | None = None, row_digest: dict | None = None,
          drop_entries: tuple = (), filename: str = "snapshot.json") -> Path:
    """Write the test registry under `folder` and return its path.

    `labels` overrides DEFAULT_LABELS per name (None removes that name's label), `grade` and
    `entry_digest` override per name the cited entry's grade ("E1") and digest (CONFIG_A; None leaves
    the entry with no digest), `row_digest` puts a copy of a digest on a row, and `drop_entries`
    leaves the named entries out of the file altogether.
    """
    real = json.loads(REAL_SNAPSHOT.read_text(encoding="utf-8"))
    table = json.loads(real["tables"]["devices"]["text"])
    wanted = {**DEFAULT_LABELS, **(labels or {})}
    grade = grade or {}
    entry_digest = entry_digest or {}
    row_digest = row_digest or {}
    entries: dict = {}
    for name, label in wanted.items():
        if label is None:
            continue
        ref = entry_ref(name)
        identifiers = {"mm_label": label}
        found = entry_digest.get(name, CONFIG_A)
        if found is not None:
            identifiers["mm_config_sha256"] = found
        if ref not in drop_entries:
            entries[ref] = {"text": json.dumps({"entry_id": ref, "grade": grade.get(name, "E1"),
                                                "identifiers": identifiers,
                                                "source": "a test's own synthetic entry"})}

    def labelled(row: dict) -> None:
        name = row["id"]
        if wanted.get(name):
            field = {"label": wanted[name], "entry_ref": entry_ref(name)}
            if name in row_digest:
                field["config_sha256"] = row_digest[name]
            row["mm_label"] = field

    for channel in table["channels"]:
        labelled(channel)
        for element in channel.get("elements", []) or []:
            labelled(element)
    out = {"snapshot_version": real.get("snapshot_version"), "kb_version": "test",
           "built_from_commit": "test",
           "tables": {"devices": {"text": json.dumps(copy.deepcopy(table)), "from": "a test"}},
           "entries": entries}
    path = Path(folder) / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out), encoding="utf-8")
    return path
