"""A test registry that gives registry names Micro-Manager labels (card 091), for tests only.

The real snapshot carries no `mm_label` rows yet, so every test that needs a camera tap or a name
resolved to a label reads one of these instead, patched in as `orch.REGISTRY_LOOKUP`. It is the real
device table of `microscope_agent/envelope/snapshot.json` with labels added on `camera_red`,
`camera_blue` and the element `dia_lamp`, plus synthetic entries the labels cite. Nothing here is a
fact about the instrument: the labels, grades and digests are the test's own.

    path = mm_label_registry.write(folder)                                   # all three labelled, E1
    path = mm_label_registry.write(folder, grade={"camera_red": "E3"})       # one entry graded E3
    path = mm_label_registry.write(folder, labels={"camera_blue": None})     # one row without a label

Card 095 adds three more things a test may put in the file: `bindings` (a row's `mm_bindings` with the
entries they cite), `states` (a row's `mm_states`) and `calibrations` (entries of `kind: calibration`).
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
          drop_entries: tuple = (), filename: str = "snapshot.json",
          bindings: dict | None = None, states: dict | None = None,
          calibrations: list | None = None) -> Path:
    """Write the test registry under `folder` and return its path.

    `labels` overrides DEFAULT_LABELS per name (None removes that name's label), `grade` and
    `entry_digest` override per name the cited entry's grade ("E1") and digest (CONFIG_A; None leaves
    the entry with no digest), `row_digest` puts a copy of a digest on a row, and `drop_entries`
    leaves the named entries out of the file altogether.

    `bindings` is `{name: [{"quantity", "property", "unit"[, "grade", "digest", "label"]}]}` and
    `states` is `{name: [{"word", "state_label"[, "grade", "digest"]}]}`: each item goes on the row as
    a list entry citing a synthetic entry written beside the labels, E1 under CONFIG_A unless it says
    otherwise (`digest: None` writes the entry with no digest). `calibrations` is a list of
    `{"label", "property", "quantity", "validity", "valid_until"[, "grade", "conversion"]}`, each a
    `kind: calibration` entry graded E2. A binding item may carry `step` ({"value", "unit"}; card 098):
    it goes on the row, one in the binding's own unit when the item says nothing, and `"step": None`
    leaves the row without one.
    """
    real = json.loads(REAL_SNAPSHOT.read_text(encoding="utf-8"))
    table = json.loads(real["tables"]["devices"]["text"])
    wanted = {**DEFAULT_LABELS, **(labels or {})}
    grade = grade or {}
    entry_digest = entry_digest or {}
    row_digest = row_digest or {}
    entries: dict = {}
    row_lists: dict[str, dict[str, list]] = {}
    for name, items in (bindings or {}).items():
        for item in items:
            ref = f"mm_binding_{name}_{item['quantity']}"
            ids = {"mm_label": item.get("label", wanted.get(name)), "mm_property": item["property"],
                   "quantity": item["quantity"], "unit": item["unit"]}
            if item.get("digest", CONFIG_A) is not None:
                ids["mm_config_sha256"] = item.get("digest", CONFIG_A)
            entries[ref] = {"text": json.dumps({"entry_id": ref, "grade": item.get("grade", "E1"),
                                                "identifiers": ids, "source": "a test's own synthetic entry"})}
            row_item = {"quantity": item["quantity"], "property": item["property"], "unit": item["unit"],
                        "entry_ref": ref}
            step = item["step"] if "step" in item else {"value": 1, "unit": item["unit"]}
            if step is not None:
                row_item["step"] = step
            row_lists.setdefault(name, {}).setdefault("mm_bindings", []).append(row_item)
    for name, items in (states or {}).items():
        for item in items:
            ref = f"mm_state_{name}_{item['word']}"
            ids = {"mm_label": item.get("label", wanted.get(name)), "path_word": item["word"],
                   "mm_state_label": item["state_label"]}
            if item.get("digest", CONFIG_A) is not None:
                ids["mm_config_sha256"] = item.get("digest", CONFIG_A)
            entries[ref] = {"text": json.dumps({"entry_id": ref, "grade": item.get("grade", "E1"),
                                                "identifiers": ids, "source": "a test's own synthetic entry"})}
            row_lists.setdefault(name, {}).setdefault("mm_states", []).append(
                {"word": item["word"], "state_label": item["state_label"], "entry_ref": ref})
    for i, cal in enumerate(calibrations or []):
        ref = f"mm_calibration_{i}"
        entries[ref] = {"text": json.dumps({
            "entry_id": ref, "kind": "calibration", "grade": cal.get("grade", "E2"),
            "identifiers": {"mm_label": cal["label"], "mm_property": cal["property"],
                            "quantity": cal["quantity"]},
            "valid_until": cal["valid_until"], "validity": cal["validity"],
            **({"conversion": cal["conversion"]} if "conversion" in cal else {}),
            "source": "a test's own synthetic entry"})}
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
        for key, items in row_lists.get(name, {}).items():
            row[key] = items

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
