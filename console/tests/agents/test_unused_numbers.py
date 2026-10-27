"""Console card 021: the numbers a plan lists and nothing uses, shown beside the plan the person signs.

The console holds a copy of the rule `unused_numbers(plan)` of `contracts/validate.py` (copied at
f5699603). These tests hold the copy to the rule's own cases, read from the tree's `contracts/` as data,
and hold the question detail to one card: the list and the fingerprint come from the same read.
"""

from __future__ import annotations

import json
import shutil

import pytest

from sma_console.agents import MockStore, QuestionDetail, SmaFiles
from sma_console.agents.mock_store import MOCK_DATA
from sma_console.agents.sma_files import plan_hash, repository_root, unused_numbers, unused_numbers_state
from sma_console.agents.store import UnusedNumbers

EXAMPLES = repository_root() / "contracts" / "examples"
QID = "mic-20260925-002"
PLAN_FILE = f"plan_microscope_{QID}.json"

# The eleven cases present when the rule was copied (f5699603). A missing one fails; it is never skipped.
AT_THE_RELEASE = [
    "unused_numbers_case_a_computed_numbers_input.json",
    "unused_numbers_case_a_criterions_number.json",
    "unused_numbers_case_compare_arm_levels.json",
    "unused_numbers_case_condition_on_a_device_no_selector_names.json",
    "unused_numbers_case_left_behind_a_selector.json",
    "unused_numbers_case_limits_ceilings_the_smoke_fraction_and_a_basis.json",
    "unused_numbers_case_mic_20260920_001_v4.json",
    "unused_numbers_case_named_twice.json",
    "unused_numbers_case_no_field_names_it.json",
    "unused_numbers_case_no_numbers.json",
    "unused_numbers_case_sweep_levels.json",
]
REJECTED_AT_THE_RELEASE = [
    "bad_unused_numbers_case_counts_a_computed_numbers_input_as_used.json",
    "bad_unused_numbers_case_counts_a_number_behind_a_selector_as_used.json",
    "bad_unused_numbers_case_counts_a_preconditions_basis_as_used.json",
]


def _case(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _cases():
    """The eleven by name, and any case added since: a name that is gone is still asked for."""
    found = {p.name for p in EXAMPLES.glob("unused_numbers_case_*.json")}
    return sorted(set(AT_THE_RELEASE) | found)


def _rejected():
    found = {p.name for p in (EXAMPLES / "rejected").glob("bad_unused_numbers_case_*.json")}
    return sorted(set(REJECTED_AT_THE_RELEASE) | found)


def test_the_cases_present_at_the_release_are_all_still_in_the_tree():
    missing = [n for n in AT_THE_RELEASE if not (EXAMPLES / n).is_file()]
    missing += [n for n in REJECTED_AT_THE_RELEASE if not (EXAMPLES / "rejected" / n).is_file()]
    assert missing == []


@pytest.mark.parametrize("name", _cases())
def test_the_copy_gives_each_cases_list_exactly_in_order(name):
    case = _case(EXAMPLES / name)
    assert unused_numbers(case["plan"]) == case["unused"]
    state = unused_numbers_state(case["plan"])
    assert state.worked_out is True and state.reason is None
    assert state.numbers == case["unused"]


@pytest.mark.parametrize("name", _rejected())
def test_the_copy_gives_a_list_that_differs_from_each_rejected_case(name):
    case = _case(EXAMPLES / "rejected" / name)
    assert unused_numbers(case["plan"]) != case["unused"]


def test_a_number_without_a_name_is_not_listed_and_does_not_stop_the_rule():
    """The rule completes on it (a missing camera ceiling puts None in the used set), so the copy does too."""
    plan = {"numbers": [{"value": 1, "unit": "s"}], "actions": []}
    assert unused_numbers(plan) == []
    assert unused_numbers_state(plan) == UnusedNumbers(worked_out=True, numbers=[], reason=None)


MALFORMED = [
    pytest.param({"numbers": [{"name": "a", "value": 1}], "actions": [3]}, id="an_action_that_is_not_an_object"),
    pytest.param({"numbers": [{"name": "a"}], "actions": [{"parameters": 5}]}, id="parameters_that_are_not_a_list"),
    pytest.param({"numbers": [{"name": "a"}], "stop_criteria": ["x"]}, id="a_criterion_that_is_not_an_object"),
    pytest.param({"numbers": [{"name": "a"}], "success_criteria": [{"number": ["a"]}]}, id="a_criterion_naming_a_list"),
    pytest.param({"numbers": ["x"]}, id="a_number_that_is_not_an_object"),
    pytest.param({"numbers": [{"name": ["a"]}]}, id="a_number_named_by_a_list"),
    pytest.param({"numbers": [{"name": "a"}], "focus_search": [1]}, id="a_focus_search_that_is_not_an_object"),
    pytest.param({"numbers": [{"name": "a"}], "smoke": {"record_fraction": ["a"]}}, id="a_smoke_fraction_naming_a_list"),
    pytest.param([1, 2], id="a_plan_that_is_not_an_object"),
]


@pytest.mark.parametrize("plan", MALFORMED)
def test_a_plan_the_rule_cannot_be_applied_to_is_a_state_with_a_reason_and_no_exception(plan):
    with pytest.raises(Exception):  # the rule itself raises here ...
        unused_numbers(plan)
    state = unused_numbers_state(plan)  # ... and the copy's state does not
    assert state.worked_out is False
    assert state.numbers == []
    assert isinstance(state.reason, str) and len(state.reason) > 20
    assert "Traceback" not in state.reason and "Error" not in state.reason  # in words, not an exception's text


def test_the_reasons_differ_by_what_was_wrong():
    reasons = {unused_numbers_state(p.values[0]).reason for p in MALFORMED}
    assert len(reasons) >= 3


def test_the_copy_does_not_change_the_plan_it_reads():
    case = _case(EXAMPLES / "unused_numbers_case_mic_20260920_001_v4.json")
    before = json.dumps(case["plan"], sort_keys=True)
    unused_numbers(case["plan"])
    unused_numbers_state(case["plan"])
    assert json.dumps(case["plan"], sort_keys=True) == before


# -- one card, one list ------------------------------------------------------------------------


@pytest.fixture
def tree(tmp_path):
    root = tmp_path / "sma"
    shutil.copytree(MOCK_DATA, root)
    path = root / "microscope_agent/questions" / QID / PLAN_FILE
    return root, path, json.loads(path.read_text("utf-8"))


def _write(path, plan):
    path.write_text(json.dumps(plan), encoding="utf-8")


def test_the_mocks_shipped_microscope_plan_lists_the_number_nothing_sets():
    d = MockStore().get_question(QID)
    assert d.unused_numbers is not None and d.unused_numbers.worked_out is True
    assert [n["name"] for n in d.unused_numbers.numbers] == ["nosepiece_position"]
    assert d.unused_numbers.numbers[0]["from"] == "numbers[0]"


def test_a_number_no_action_names_joins_the_list_and_the_fingerprint_moves_with_it(tree):
    root, path, plan = tree
    s = SmaFiles(root)
    before = s.get_question(QID)
    plan["numbers"].append({"name": "bleach_window", "value": 4, "unit": "s", "source": "assumed:x", "grade": "E5"})
    _write(path, plan)
    after = s.get_question(QID)
    assert "bleach_window" in [n["name"] for n in after.unused_numbers.numbers]
    assert "bleach_window" not in [n["name"] for n in before.unused_numbers.numbers]
    assert after.plan_hash != before.plan_hash
    # both come from the card that was read: the list is the rule on that card, the hash is that card's
    assert after.plan_hash == plan_hash(after.plan.data)
    assert after.unused_numbers.numbers == unused_numbers(after.plan.data)


def test_naming_it_from_an_action_takes_it_off_the_list(tree):
    root, path, plan = tree
    plan["numbers"].append({"name": "bleach_window", "value": 4, "unit": "s", "source": "assumed:x", "grade": "E5"})
    _write(path, plan)
    s = SmaFiles(root)
    assert "bleach_window" in [n["name"] for n in s.get_question(QID).unused_numbers.numbers]
    plan["actions"][0]["parameters"] = [*plan["actions"][0].get("parameters", []), "bleach_window"]
    _write(path, plan)
    after = s.get_question(QID)
    assert "bleach_window" not in [n["name"] for n in after.unused_numbers.numbers]
    assert after.plan_hash == plan_hash(plan)


NO_PLAN_QID = "mic-20260925-001"  # the mock's question that has a goal and a result and no plan card


def test_a_question_with_no_plan_has_no_list_at_all(tree):
    root, _, _ = tree
    d = SmaFiles(root).get_question(NO_PLAN_QID)
    assert d.plan is None and d.plan_hash is None
    assert d.unused_numbers is None  # nothing: neither an empty list nor a failure


def test_an_empty_list_is_told_apart_from_no_list(tree):
    root, path, plan = tree
    plan["numbers"] = []
    _write(path, plan)
    d = SmaFiles(root).get_question(QID)
    assert d.unused_numbers == UnusedNumbers(worked_out=True, numbers=[], reason=None)


def test_a_plan_the_rule_cannot_read_gives_the_could_not_be_worked_out_state_from_the_detail(tree):
    root, path, plan = tree
    plan["actions"] = [3]
    _write(path, plan)
    d = SmaFiles(root).get_question(QID)  # no exception
    assert d.plan_hash == plan_hash(plan)  # the fingerprint is still the card's
    assert d.unused_numbers.worked_out is False and d.unused_numbers.reason


def test_the_state_survives_to_dict_and_from_dict_in_all_three_states(tree):
    root, path, plan = tree
    for make in (
        lambda p: p,  # a list
        lambda p: {**p, "numbers": []},  # an empty list
        lambda p: {**p, "actions": [3]},  # could not be worked out
    ):
        _write(path, make(plan))
        d = SmaFiles(root).get_question(QID)
        again = QuestionDetail.from_dict(json.loads(json.dumps(d.to_dict())))
        assert again.unused_numbers == d.unused_numbers
    d = SmaFiles(root).get_question(NO_PLAN_QID)
    assert d.to_dict()["unused_numbers"] is None
    assert QuestionDetail.from_dict(json.loads(json.dumps(d.to_dict()))).unused_numbers is None


def test_a_detail_written_before_the_field_existed_still_reads():
    d = MockStore().get_question(QID).to_dict()
    del d["unused_numbers"]
    assert QuestionDetail.from_dict(d).unused_numbers is None


def test_reading_the_list_writes_nothing(tree):
    root, _, _ = tree
    before = {p.relative_to(root).as_posix(): (p.stat().st_size, p.stat().st_mtime_ns)
              for p in root.rglob("*") if p.is_file()}
    SmaFiles(root).get_question(QID)
    after = {p.relative_to(root).as_posix(): (p.stat().st_size, p.stat().st_mtime_ns)
             for p in root.rglob("*") if p.is_file()}
    assert after == before
