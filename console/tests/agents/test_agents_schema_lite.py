"""The small JSON Schema checker (console card 012), held to the repository's own schemas, examples and
rejected fixtures: it must accept what the contracts accept and refuse what they refuse, and it must raise
on a keyword it cannot judge rather than pass over it."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from sma_console.agents.schema_lite import SchemaError, Schemas
from sma_console.agents.sma_files import repository_root

REPO = repository_root()
SCHEMAS = REPO / "contracts" / "schemas"
EXAMPLES = REPO / "contracts" / "examples"
S = Schemas(SCHEMAS)


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8-sig"))


def kind_of(doc) -> str | None:
    return (doc.get("card") or doc.get("artifact")) if isinstance(doc, dict) else None


def examples():
    for f in sorted(EXAMPLES.glob("*.json")):
        try:
            doc = load(f)
        except ValueError:
            continue
        k = kind_of(doc)
        if k and (SCHEMAS / f"{k}.schema.json").exists():
            yield pytest.param(f, doc, f"{k}.schema.json", id=f.name)


@pytest.mark.parametrize(("path", "doc", "schema"), list(examples()))
def test_every_example_the_contracts_accept_is_accepted(path, doc, schema):
    assert S.validate(doc, schema) == []


def rejected():
    for d in sorted((EXAMPLES / "rejected").glob("check01_*")):
        for f in sorted(d.glob("*.json")):
            try:
                doc = load(f)
            except ValueError:
                continue
            k = kind_of(doc)
            # the harness proposals are judged by a ledger walk, not by their own schema alone
            if k and not k.startswith("harness") and (SCHEMAS / f"{k}.schema.json").exists():
                yield pytest.param(doc, f"{k}.schema.json", id=f"{d.name}/{f.name}")


@pytest.mark.parametrize(("doc", "schema"), list(rejected()))
def test_every_fixture_check_one_rejects_is_rejected(doc, schema):
    assert S.validate(doc, schema) != []


def test_the_fixture_walk_is_not_empty():
    assert len(list(rejected())) >= 40 and len(list(examples())) >= 20


# -- the plan schema, by changing one thing in an accepted plan --------------------------------------


PLAN = load(EXAMPLES / "plan_trap_steps_place_and_hold.json")


def changed(mutate):
    d = copy.deepcopy(PLAN)
    mutate(d)
    return S.validate(d, "plan.schema.json")


def test_a_plan_without_a_required_field_is_refused():
    assert changed(lambda d: d.pop("actions"))
    assert changed(lambda d: d.pop("stop_criteria"))


def test_a_plan_with_a_key_the_schema_does_not_name_is_refused():
    assert changed(lambda d: d["trap_steps"].update(invented=1))
    assert changed(lambda d: d["trap_steps"]["steps"][0].update(invented=1))


def test_a_trap_step_of_a_kind_the_schema_does_not_know_or_without_its_steps_is_refused():
    assert changed(lambda d: d["trap_steps"]["steps"][0].update(kind="teleport"))
    assert changed(lambda d: d["trap_steps"].pop("steps"))
    assert changed(lambda d: d["trap_steps"].pop("device"))


def test_the_operation_branch_refuses_what_it_forbids():
    op = load(EXAMPLES / "plan_operation_piezo_x_step.json")
    assert S.validate(op, "plan.schema.json") == []
    bad = copy.deepcopy(op)
    bad["observable"] = {"name": "tracer_diffusivity"}
    assert S.validate(bad, "plan.schema.json")  # an operation plan names no observable
    bad = copy.deepcopy(op)
    bad["actions"][0]["reversible"] = False
    assert S.validate(bad, "plan.schema.json")  # and holds no irreversible action
    bad = copy.deepcopy(op)
    bad["operation"]["moves"][0]["axis"] = "w"
    assert S.validate(bad, "plan.schema.json")


def test_a_measuring_plan_needs_the_whole_set_a_light_or_exposure_draft_does_not_have():
    """What a console draft of a light or an exposure runs into: no `operation` and no `trap_steps`, so the
    schema takes the measuring branch and asks for a goal, an observable, conditions and the rest."""
    card = {"card": "plan", "schema_version": "0.1", "id": "plan-x-r1", "qid": "mic-20261024-001",
            "thread": "solo-mic-20261024-001", "round": 0, "revision": 1, "author": "human",
            "created_at": "2026-10-24T10:00:00Z", "status": "PROPOSED", "purpose": "verify", "intent": "explore",
            "actions": [{"id": "a1", "device": "Kinetix_red", "action": "set_exposure", "reversible": True,
                         "parameters": [], "tier": 1}],
            "envelope_check": {"checked_against": [], "status": "unavailable", "note": "none"},
            "stop_criteria": [], "success_criteria": [], "open_risks": [], "numbers": [], "degraded": []}
    problems = S.validate(card, "plan.schema.json")
    assert problems and any("goal_id" in p or "observable" in p for p in problems)


# -- the checker's own rules ---------------------------------------------------------------------------


def schemas_in(tmp_path: Path, **files) -> Schemas:
    for name, body in files.items():
        (tmp_path / name).write_text(json.dumps(body), encoding="utf-8")
    return Schemas(tmp_path)


def test_a_keyword_it_cannot_judge_raises_instead_of_passing(tmp_path):
    s = schemas_in(tmp_path, **{"a.json": {"type": "object", "patternProperties": {"^x": {"type": "string"}}}})
    with pytest.raises(SchemaError, match="patternProperties"):
        s.validate({"xa": 1}, "a.json")


def test_a_reference_that_is_not_there_raises(tmp_path):
    s = schemas_in(tmp_path, **{"a.json": {"$ref": "nowhere.json#/$defs/x"}})
    with pytest.raises(SchemaError):
        s.validate({}, "a.json")
    s = schemas_in(tmp_path, **{"b.json": {"$ref": "#/$defs/missing"}})
    with pytest.raises(SchemaError):
        s.validate({}, "b.json")


def test_annotations_and_x_keywords_are_ignored(tmp_path):
    s = schemas_in(tmp_path, **{"a.json": {"title": "t", "description": "d", "$comment": "c", "x_max_bytes": 5, "type": "string"}})
    assert s.validate("ok", "a.json") == []


def test_one_of_means_exactly_one(tmp_path):
    s = schemas_in(tmp_path, **{"a.json": {"oneOf": [{"type": "number"}, {"minimum": 0}]}})
    assert s.validate("x", "a.json") == []  # a string matches only the second: `minimum` judges numbers alone
    assert s.validate(5, "a.json")  # matches both
    assert s.validate(-5, "a.json") == []  # matches the first only


def test_if_then_else(tmp_path):
    s = schemas_in(tmp_path, **{"a.json": {"if": {"required": ["a"]}, "then": {"required": ["b"]}, "else": {"required": ["c"]}}})
    assert s.validate({"a": 1, "b": 1}, "a.json") == []
    assert s.validate({"a": 1}, "a.json")
    assert s.validate({"c": 1}, "a.json") == []
    assert s.validate({}, "a.json")


def test_unevaluated_properties_sees_through_a_reference_and_all_of(tmp_path):
    s = schemas_in(tmp_path, **{"a.json": {
        "allOf": [{"$ref": "#/$defs/base"}], "properties": {"extra": {"type": "string"}},
        "unevaluatedProperties": False, "$defs": {"base": {"properties": {"name": {"type": "string"}}}}}})
    assert s.validate({"name": "x", "extra": "y"}, "a.json") == []
    assert s.validate({"name": "x", "other": 1}, "a.json")


def test_cross_file_references_resolve(tmp_path):
    s = schemas_in(tmp_path, **{"a.json": {"$ref": "b.json#/$defs/n"}, "b.json": {"$defs": {"n": {"type": "integer", "minimum": 1}}}})
    assert s.validate(3, "a.json") == [] and s.validate(0, "a.json") and s.validate("x", "a.json")


def test_date_time_and_the_other_basics(tmp_path):
    s = schemas_in(tmp_path, **{"a.json": {"type": "object", "required": ["t"], "additionalProperties": False,
                                          "properties": {"t": {"type": "string", "format": "date-time"},
                                                         "n": {"type": "integer", "exclusiveMinimum": 0},
                                                         "l": {"type": "array", "minItems": 1, "maxItems": 2, "uniqueItems": True}}}})
    assert s.validate({"t": "2026-10-24T10:00:00Z"}, "a.json") == []
    assert s.validate({"t": "yesterday"}, "a.json")
    assert s.validate({"t": "2026-10-24T10:00:00Z", "n": 0}, "a.json")
    assert s.validate({"t": "2026-10-24T10:00:00Z", "n": 1.5}, "a.json")
    assert s.validate({"t": "2026-10-24T10:00:00Z", "l": [1, 1]}, "a.json")
    assert s.validate({"t": "2026-10-24T10:00:00Z", "l": []}, "a.json")
    assert s.validate({"t": "2026-10-24T10:00:00Z", "z": 1}, "a.json")
    assert s.validate({"n": 1}, "a.json")
