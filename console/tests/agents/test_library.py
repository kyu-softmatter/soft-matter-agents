"""The library reader (console card 016): the librarian's generated wiki pages, shown and nothing else.

The reader reads `librarian_agent/kb/wiki/<page>.md`, the map files beside them, and the one field
`kb_version` of `librarian_agent/kb/index.json`. It lists no folder, so what else lies under
`librarian_agent/` (entries, the query log, answers, exports) is never opened, named or counted.
"""

from __future__ import annotations

import builtins
import io
import json
import os
from pathlib import Path

import pytest

from sma_console.agents import NotFoundError
from sma_console.agents.library import FOOTER, Library
from sma_console.agents.mock_store import MOCK_DATA

LONG = chr(92) * 2 + "?" + chr(92)  # the long-path prefix
V1 = "kbv-0123456789ab"
V2 = "kbv-ba9876543210"


def footer(v: str = V1) -> str:
    return f"Generated from the knowledge store at {v}. Do not edit by hand: correct the store and regenerate."


INDEX_MD = f"""# The knowledge store

Every page the wiki holds, by section.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## The store

- version: {V1}
- entries: 12
- device pages: 2

## Device pages

- [dia_lamp](../wiki/device_dia_lamp.md) (1 entries)
- [camera_blue](../wiki/device_camera_blue.md) (5 entries)

## Quantity pages

- [na](../wiki/quantity_na.md) (3 entries)

## Observable pages

- [bleaching_rate](../wiki/observable_bleaching_rate.md) (1 entries)

## Sample pages

- [particle_suspension_a](../wiki/sample_particle_suspension_a.md) (2 entries)

## Configuration pages

- [trapping](../wiki/configuration_trapping.md) (1 entries)

## Registered quantities no entry uses

- unused_one
- unused_two

## Unfiled

- [unfiled entries](../wiki/unfiled.md) (55 entries)

---

{footer()}
"""

PAGE_MD = f"""# Device: dia_lamp

Every entry in the store about the device dia_lamp.

## What it is

```json
{{
  "id": "dia_lamp"
}}
```

## Claims

### [dia_lamp_reports_state](../entries/dia_lamp_reports_state.json)

The lamp reports `State` and `Intensity`. See [camera_blue](../wiki/device_camera_blue.md), the
[handling guide](../guides/handling.md) and [the maker](https://example.org/maker).

> A quoted condition, verbatim.

| quantity | value | entry |
|---|---|---|
| na | 0.2 | [objective_mrd70040](../entries/objective_mrd70040.json) |

- one
- two with [a page](../wiki/quantity_na.md)

---

{footer()}
"""


def make(tmp_path: Path, *, version: str | None = V1, pages: dict[str, str] | None = None,
         extra: dict[str, str] | None = None) -> Path:
    root = tmp_path / "tree"
    kb = root / "librarian_agent" / "kb"
    (kb / "wiki").mkdir(parents=True)
    if version is not None:
        (kb / "index.json").write_text(json.dumps({"kb_version": version, "entry_count": 12}), encoding="utf-8")
    for name, text in {"index.md": INDEX_MD, "device_dia_lamp.md": PAGE_MD, **(pages or {})}.items():
        (kb / "wiki" / name).write_text(text, encoding="utf-8")
    for rel, text in (extra or {}).items():
        p = root / "librarian_agent" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return root


def spans(blocks, kind):
    return [b for b in blocks if b["type"] == kind]


def all_spans(block):
    if block["type"] in ("paragraph", "quote"):
        return block["spans"]
    if block["type"] == "list":
        return [s for item in block["items"] for s in item]
    if block["type"] == "table":
        return [s for row in [block["header"], *block["rows"]] for cell in row for s in cell]
    return []


# -- the index: the division by data type ----------------------------------------------------------------


def test_the_index_is_divided_by_data_type(tmp_path):
    out = Library(make(tmp_path)).index()
    assert out["state"] == "shown"
    assert [g["key"] for g in out["groups"]] == ["devices", "quantities", "observables",
                                                  "samples_and_configurations", "unfiled"]
    devices = out["groups"][0]
    assert [(l["label"], l["page"], l["entries"]) for l in devices["links"]] == [
        ("dia_lamp", "device_dia_lamp", 1), ("camera_blue", "device_camera_blue", 5)]
    mixed = out["groups"][3]["links"]
    assert [(l["page"], l["kind"]) for l in mixed] == [("sample_particle_suspension_a", "sample"),
                                                       ("configuration_trapping", "configuration")]
    assert out["groups"][4]["links"][0]["page"] == "unfiled"
    assert out["registered_unused"] == ["unused_one", "unused_two"]
    assert {"label": "entries", "value": "12"} in out["facts"]


def test_the_index_says_which_version_it_was_built_from_and_the_present_one(tmp_path):
    out = Library(make(tmp_path)).index()
    assert (out["footer_version"], out["current_version"], out["behind"]) == (V1, V1, False)
    assert out["note"] is None
    assert out["footer"] == footer()


def test_an_index_with_no_librarian_folder_is_not_built(tmp_path):
    out = Library(tmp_path).index()
    assert out["state"] == "not_built"
    assert "not built yet" in out["message"].lower()
    assert out["groups"] == []


def test_an_index_without_the_exact_footer_is_not_shown(tmp_path):
    bad = INDEX_MD.replace("Do not edit by hand", "Edit as you like")
    out = Library(make(tmp_path, pages={"index.md": bad})).index()
    assert out["state"] == "not_generated"
    assert out["groups"] == []


# -- a page, shown as it stands --------------------------------------------------------------------------


def test_a_page_comes_as_blocks_and_its_footer(tmp_path):
    page = Library(make(tmp_path)).page("device_dia_lamp")
    assert page["title"] == "Device: dia_lamp"
    types = [b["type"] for b in page["blocks"]]
    assert {"heading", "paragraph", "code", "quote", "table", "list"} <= set(types)
    assert page["footer"] == footer()
    assert "rule" not in types[-1:]  # the rule above the footer belongs to the footer
    assert spans(page["blocks"], "code")[0]["text"].strip().startswith("{")
    assert spans(page["blocks"], "code")[0]["language"] == "json"
    assert spans(page["blocks"], "quote")[0]["spans"][0]["text"] == "A quoted condition, verbatim."
    table = spans(page["blocks"], "table")[0]
    assert [c[0]["text"] for c in table["header"]] == ["quantity", "value", "entry"]
    assert [c[0]["text"] for c in table["rows"][0]] == ["na", "0.2", "objective_mrd70040"]


def test_a_link_to_another_wiki_page_is_followed(tmp_path):
    page = Library(make(tmp_path)).page("device_dia_lamp")
    pages = {s["page"] for b in page["blocks"] for s in all_spans(b) if s["page"]}
    assert pages == {"device_camera_blue", "quantity_na"}


def test_a_link_to_an_entry_or_a_guide_is_shown_as_text_and_never_followed(tmp_path):
    page = Library(make(tmp_path)).page("device_dia_lamp")
    everything = [s for b in page["blocks"] for s in all_spans(b)]
    entry = [s for s in everything if s["text"] == "objective_mrd70040"]
    guide = [s for s in everything if s["text"] == "handling guide"]
    outside = [s for s in everything if s["text"] == "the maker"]
    assert entry and guide and outside
    for s in entry + guide + outside:
        assert s["page"] is None
    # no span anywhere carries a path, a url or an entry file: the wire shape has only text, code, page
    assert all(set(s) == {"text", "code", "page"} for s in everything)
    assert not any("entries/" in json.dumps(b) or "guides/" in json.dumps(b) or "example.org" in json.dumps(b)
                   for b in page["blocks"])
    heading = [b for b in page["blocks"] if b["type"] == "heading" and b["level"] == 3][0]
    assert heading["text"] == "dia_lamp_reports_state"  # an entry heading is text too


def test_inline_code_is_marked(tmp_path):
    page = Library(make(tmp_path)).page("device_dia_lamp")
    para = [b for b in page["blocks"] if b["type"] == "paragraph" and any(s["code"] for s in b["spans"])][0]
    assert [s["text"] for s in para["spans"] if s["code"]] == ["State", "Intensity"]


def test_a_page_built_from_an_older_version_says_so_in_plain_words(tmp_path):
    root = make(tmp_path, version=V2)
    page = Library(root).page("device_dia_lamp")
    assert (page["footer_version"], page["current_version"], page["behind"]) == (V1, V2, True)
    assert "older version of the store" in page["note"]
    assert V1 in page["note"] and V2 in page["note"]
    assert page["blocks"], "an older page is still shown, as it stands"


def test_a_page_at_the_present_version_says_nothing_of_it(tmp_path):
    page = Library(make(tmp_path)).page("device_dia_lamp")
    assert page["behind"] is False and page["note"] is None


def test_when_the_present_version_cannot_be_read_the_page_says_it_cannot_compare(tmp_path):
    page = Library(make(tmp_path, version=None)).page("device_dia_lamp")
    assert page["current_version"] is None and page["behind"] is False
    assert "cannot be compared" in page["note"]


def test_a_page_without_the_exact_footer_is_refused_as_not_generated(tmp_path):
    bad = PAGE_MD.replace("regenerate.", "regenerate!")
    with pytest.raises(NotFoundError, match="not a generated page"):
        Library(make(tmp_path, pages={"device_dia_lamp.md": bad})).page("device_dia_lamp")


def test_a_page_that_is_not_there_is_not_found(tmp_path):
    with pytest.raises(NotFoundError, match="no page"):
        Library(make(tmp_path)).page("device_camera_blue")


@pytest.mark.parametrize("bad", ["../index", "..\\index", "kb/wiki/index", "index.md", "Device_X", "device_",
                                 "entries/x", "answers", "", "device_x/../../index", "map.json", "x" * 200,
                                 "unfiled\n", "device_a b"])
def test_a_page_name_that_is_not_a_page_name_is_never_looked_up(tmp_path, bad):
    root = make(tmp_path, extra={"answers/secret.json": "{}", "entries/x.json": "{}"})
    with pytest.raises(NotFoundError, match="not a page name"):
        Library(root).page(bad)


def test_a_page_with_no_librarian_folder_is_not_found(tmp_path):
    with pytest.raises(NotFoundError):
        Library(tmp_path).page("index")


def test_crlf_files_read_the_same_as_lf_ones(tmp_path):
    root = make(tmp_path, pages={"device_dia_lamp.md": PAGE_MD.replace("\n", "\r\n")})
    (root / "librarian_agent" / "kb" / "wiki" / "device_dia_lamp.md").write_bytes(PAGE_MD.replace("\n", "\r\n").encode())
    a = Library(root).page("device_dia_lamp")
    assert a["footer"] == footer() and a["behind"] is False
    b = Library(make(tmp_path / "lf")).page("device_dia_lamp")
    assert a["blocks"] == b["blocks"]


# -- what is read ----------------------------------------------------------------------------------------


class Recorder:
    def __init__(self, monkeypatch):
        self.opened: list[Path] = []
        self.listed: list[str] = []
        real_open = builtins.open

        def spy_open(file, *a, **k):
            if isinstance(file, (str, os.PathLike)):
                self.opened.append(Path(os.fspath(file)))
            return real_open(file, *a, **k)

        real_io_open = io.open

        def spy_io_open(file, *a, **k):
            if isinstance(file, (str, os.PathLike)):
                self.opened.append(Path(os.fspath(file)))
            return real_io_open(file, *a, **k)

        real_scandir, real_listdir = os.scandir, os.listdir
        monkeypatch.setattr(builtins, "open", spy_open)
        monkeypatch.setattr(io, "open", spy_io_open)
        monkeypatch.setattr(os, "scandir", lambda p=".": (self.listed.append(str(p)), real_scandir(p))[1])
        monkeypatch.setattr(os, "listdir", lambda p=".": (self.listed.append(str(p)), real_listdir(p))[1])

    def under(self, root: Path) -> set[str]:
        out = set()
        base = os.path.normcase(str(root / "librarian_agent"))
        for p in self.opened:
            s = os.path.normcase(os.path.abspath(str(p)))
            s = s[4:] if s.startswith(LONG) else s  # the long-path prefix the reader uses on Windows
            if s.startswith(base + os.sep):
                out.add(s[len(base) + 1:].replace(os.sep, "/"))
        return out


def test_the_only_files_read_under_the_librarian_folder_are_generated_wiki_files_and_the_version(
        tmp_path, monkeypatch):
    root = make(tmp_path, extra={
        "answers/ca-1.json": "{}", "queries/log.jsonl": "{}", "entries/x.json": "{}", "kb/exports/e.json": "{}",
        "kb/staging/devices.v0.json": "{}", "console_inbox/ci-1.json": "{}", "kb/wiki/notes.txt": "x",
        "kb/wiki/evidence.md": "# Evidence\n\n---\n\n" + footer() + "\n"})
    seen = Recorder(monkeypatch)
    lib = Library(root)
    lib.index()
    lib.page("index")
    lib.page("device_dia_lamp")
    lib.map()
    read = seen.under(root)
    assert read, "the spy saw no read at all"
    allowed = {"kb/index.json"} | {f"kb/wiki/{n}" for n in ("index.md", "device_dia_lamp.md", "evidence.md",
                                                           "map.md", "map.json")}
    assert read <= allowed, sorted(read - allowed)
    assert not [l for l in seen.listed if "librarian_agent" in l.replace("\\", "/")], seen.listed


def test_the_version_is_the_only_field_taken_from_the_index(tmp_path):
    root = make(tmp_path)
    (root / "librarian_agent" / "kb" / "index.json").write_text(json.dumps({
        "kb_version": V1, "entry_count": 339, "entries": [{"id": "x", "claim": "a secret value"}]}), encoding="utf-8")
    out = Library(root).index()
    assert "a secret value" not in json.dumps(out) and "339" not in json.dumps(out)


def test_an_index_that_is_not_json_is_a_version_that_cannot_be_read(tmp_path):
    root = make(tmp_path)
    (root / "librarian_agent" / "kb" / "index.json").write_text("{not json", encoding="utf-8")
    page = Library(root).page("device_dia_lamp")
    assert page["current_version"] is None and "cannot be compared" in page["note"]


# -- the data map -----------------------------------------------------------------------------------------


def map_doc(**over) -> dict:
    doc = {
        "artifact": "kb_map", "schema_version": "0.1", "kb_version": V1, "footer": footer(),
        "nodes": [
            {"id": "page:device_dia_lamp", "kind": "device", "page": "device_dia_lamp.md",
             "coverage": {"E1": 1, "E2": 0, "E3": 0, "E4": 0, "E5": 0}, "disputed": 0},
            {"id": "page:quantity_na", "kind": "quantity", "page": "quantity_na.md",
             "coverage": {"E1": 0, "E2": 0, "E3": 3, "E4": 0, "E5": 0}, "disputed": 1},
            {"id": "entry:objective_mrd70040", "kind": "entry", "grade": "E3", "source": "spec:MRD70040",
             "status": "active"},
        ],
        "edges": [
            {"type": "about", "from": "entry:objective_mrd70040", "to": "page:quantity_na", "stated_by": "subject"},
            {"type": "conflict_with", "from": "entry:objective_mrd70040", "to": "entry:other",
             "stated_by": "entry:objective_mrd70040"},
        ],
        "dangling": [],
    }
    doc.update(over)
    return doc


def with_map(tmp_path, doc, **kw) -> Path:
    text = doc if isinstance(doc, str) else json.dumps(doc)
    return make(tmp_path, extra={"kb/wiki/map.json": text, **kw.get("extra", {})})


def test_a_map_that_is_not_built_says_so(tmp_path):
    out = Library(make(tmp_path)).map()
    assert out["state"] == "not_built" and "not built yet" in out["message"].lower()
    assert out["subjects"] == [] and out["relations"] == []


def test_a_built_map_shows_coverage_as_counts_by_grade(tmp_path):
    out = Library(with_map(tmp_path, map_doc())).map()
    assert out["state"] == "built"
    assert [s["id"] for s in out["subjects"]] == ["page:device_dia_lamp", "page:quantity_na"]
    na = out["subjects"][1]
    assert na["coverage"] == {"E1": 0, "E2": 0, "E3": 3, "E4": 0, "E5": 0}
    assert na["disputed"] == 1 and na["page"] == "quantity_na"
    assert (out["kb_version"], out["current_version"], out["behind"]) == (V1, V1, False)


def test_a_map_never_carries_a_score_a_rank_or_one_number(tmp_path):
    out = Library(with_map(tmp_path, map_doc())).map()

    def keys(x):
        if isinstance(x, dict):
            for k, v in x.items():
                yield k
                yield from keys(v)
        elif isinstance(x, list):
            for v in x:
                yield from keys(v)

    assert not {k.lower() for k in keys(out)} & {"score", "rank", "total", "sum", "mean", "average", "percent",
                                                  "best", "worst", "coverage_total", "weight"}
    assert set(out["subjects"][0]) == {"id", "kind", "page", "coverage", "disputed"}
    assert all(isinstance(v, int) for s in out["subjects"] for v in s["coverage"].values())


def test_subjects_keep_the_files_order_and_are_not_sorted_by_coverage(tmp_path):
    doc = map_doc()
    doc["nodes"][0]["coverage"]["E1"] = 1
    doc["nodes"][1]["coverage"]["E3"] = 99
    out = Library(with_map(tmp_path, doc)).map()
    assert [s["id"] for s in out["subjects"]] == ["page:device_dia_lamp", "page:quantity_na"]
    doc["nodes"][0], doc["nodes"][1] = doc["nodes"][1], doc["nodes"][0]
    out = Library(with_map(tmp_path / "b", doc)).map()
    assert [s["id"] for s in out["subjects"]] == ["page:quantity_na", "page:device_dia_lamp"]


def test_relations_other_than_about_are_listed_with_who_stated_them(tmp_path):
    out = Library(with_map(tmp_path, map_doc())).map()
    assert out["relations"] == [{"type": "conflict_with", "from": "entry:objective_mrd70040", "to": "entry:other",
                                 "stated_by": "entry:objective_mrd70040"}]


def test_a_map_built_from_an_older_version_says_so(tmp_path):
    root = with_map(tmp_path / "old", map_doc(kb_version=V2, footer=footer(V2)))
    out = Library(root).map()
    assert out["state"] == "built" and out["behind"] is True
    assert "older version of the store" in out["note"]


@pytest.mark.parametrize("name, doc", [
    ("not json", "{not json"),
    ("a list", "[]"),
    ("wrong artifact", map_doc(artifact="something_else")),
    ("footer of another version", map_doc(footer=footer(V2))),
    ("footer reworded", map_doc(footer="Generated, probably.")),
    ("a value key", {**map_doc(), "value": 3}),
    ("a value in a node", {**map_doc(), "nodes": [{"id": "page:x", "kind": "device", "page": "x.md",
                                                 "coverage": {"E1": 0, "E2": 0, "E3": 0, "E4": 0, "E5": 0}, "disputed": 0, "value": 1.5}]}),
    ("coverage not a count", {**map_doc(), "nodes": [{"id": "page:x", "kind": "device", "page": "device_x.md",
                                                    "coverage": {"E2": 0, "E3": 0, "E4": 0, "E5": 0, "E1": 0.5}, "disputed": 0}]}),
    ("coverage negative", {**map_doc(), "nodes": [{"id": "page:x", "kind": "device", "page": "device_x.md",
                                                 "coverage": {"E2": 0, "E3": 0, "E4": 0, "E5": 0, "E1": -1}, "disputed": 0}]}),
    ("coverage of a grade that is not one", {**map_doc(), "nodes": [{"id": "page:x", "kind": "device",
                                                                    "page": "device_x.md",
                                                                    "coverage": {"E1": 0, "E2": 0, "E3": 0, "E4": 0, "E5": 0, "E6": 1}, "disputed": 0}]}),
    ("an edge type nobody knows", {**map_doc(), "edges": [{"type": "likes", "from": "a", "to": "b",
                                                          "stated_by": "c"}]}),
])
def test_a_map_that_is_not_valid_is_not_shown(tmp_path, name, doc):
    out = Library(with_map(tmp_path, doc)).map()
    assert out["state"] == "not_valid", name
    assert out["subjects"] == [] and out["relations"] == []
    assert out["message"]


def test_the_evidence_page_is_offered_only_when_it_is_there(tmp_path):
    assert Library(with_map(tmp_path, map_doc())).map()["evidence_page"] is False
    ev = {"kb/wiki/evidence.md": "# Evidence\n\n---\n\n" + footer() + "\n"}
    lib = Library(with_map(tmp_path / "b", map_doc(), extra=ev))
    assert lib.map()["evidence_page"] is True
    assert lib.page("evidence")["title"] == "Evidence"


# -- the sample that ships --------------------------------------------------------------------------------


def test_the_shipped_sample_reads_as_the_real_pages_do():
    lib = Library(MOCK_DATA)
    out = lib.index()
    assert out["state"] == "shown" and out["behind"] is False
    page = lib.page("device_dia_lamp")
    assert page["behind"] is False and spans(page["blocks"], "code")
    assert lib.page("quantity_na")["blocks"]
    assert FOOTER.format(version=out["footer_version"]) == out["footer"]
    assert lib.map()["state"] == "not_built"
