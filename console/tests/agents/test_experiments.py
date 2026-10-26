"""agents/experiments.py: the pure rules the Experiments screens stand on (console card 014).

No file is read here and nothing is sent. Each rule is held to the file that says it: the approval rule
to what the runtime's `authorise` does, the run request and its three replies to
`run_interface.schema.json`, the hand-step sheet to the format `devices/manual.py` writes.
"""

from __future__ import annotations

import json
import re

import pytest

from sma_console.agents import experiments, sma_run
from sma_console.agents.sma_files import plan_hash, repository_root

DEFS = json.loads((repository_root() / "contracts" / "schemas" / "run_interface.schema.json")
                  .read_text(encoding="utf-8-sig"))["$defs"]
SHA = "ab" * 32


def fits(instance, spec) -> bool:
    """Whether `instance` fits one `$defs` entry. The console's environment has no jsonschema, so this reads
    the keywords these three schemas use: object, `required`, `properties` with `const`, `type`, `pattern`
    and `minLength`, and `additionalProperties: false`."""
    if not isinstance(instance, dict) or not set(spec.get("required", [])) <= set(instance):
        return False
    if spec.get("additionalProperties") is False and set(instance) - set(spec["properties"]):
        return False
    for key, rule in spec["properties"].items():
        if key not in instance:
            continue
        value = instance[key]
        if "const" in rule and value != rule["const"]:
            return False
        if rule.get("type") == "string" and not isinstance(value, str):
            return False
        if "pattern" in rule and not re.search(rule["pattern"], str(value)):
            return False
        if "minLength" in rule and len(value) < rule["minLength"]:
            return False
    return True


def plan(**over):
    card = {"card": "plan", "id": "plan-mic-20261026-001-r2", "revision": 2, "status": "VALIDATED",
            "actions": [{"channel": "optical_tweezers", "action": "on"}]}
    card.update(over)
    return card


def approval(p=None, **over):
    p = p or plan()
    card = {"card": "plan_approval", "id": "appr-mic-20261026-001-r2", "status": "APPROVED",
            "plan_id": p["id"], "plan_revision": p["revision"], "plan_hash": plan_hash(p),
            "approved_by": "person", "approved_at": "2026-10-26T10:00:00Z"}
    card.update(over)
    return card


# -- which approval covers a plan: what the runtime's authorise does ------------------------------


def test_an_approval_naming_the_plan_revision_and_hash_covers_it():
    j = experiments.judge_approval(plan(), approval())
    assert (j.relevant, j.covers, j.why_void) == (True, True, None)
    assert j.signed_through is None


def test_the_plans_own_status_is_not_part_of_what_was_approved():
    """The hash leaves `status` out, so an approval made while the plan was a draft still covers it."""
    approved = approval(plan(status="DRAFT"))
    assert experiments.judge_approval(plan(status="VALIDATED"), approved).covers


def test_a_changed_plan_voids_the_approval_and_says_why():
    j = experiments.judge_approval(plan(actions=[]), approval())
    assert j.relevant and not j.covers and "changed" in j.why_void


def test_an_approval_with_no_plan_revision_covers_nothing_and_says_so():
    card = approval()
    del card["plan_revision"]
    j = experiments.judge_approval(plan(), card)
    assert j.relevant and not j.covers and "plan_revision" in j.why_void


def test_the_approvals_own_revision_is_not_the_plans():
    """`revision` is on every card; only `plan_revision` says which plan revision was approved."""
    card = approval(revision=2, plan_revision=1)
    assert not experiments.judge_approval(plan(), card).relevant


@pytest.mark.parametrize("over", [
    {"plan_id": "plan-mic-20261026-001-r1"}, {"plan_revision": 1}, {"card": "scope_approval"}])
def test_an_approval_for_another_plan_or_revision_or_kind_is_not_about_this_plan(over):
    assert not experiments.judge_approval(plan(), approval(**over)).relevant


def test_the_approvals_own_status_decides_nothing():
    """authorise does not read it, so neither does the screen: a REVOKED label is not a revocation."""
    assert experiments.judge_approval(plan(), approval(status="REVOKED")).covers


@pytest.mark.parametrize("mark", [
    {"via": "console", "login": "kyuhwan"}, {"via": "console", "login": "a.b_c-1"}])
def test_a_console_mark_is_read_and_its_login_kept(mark):
    j = experiments.judge_approval(plan(), approval(signed_through=mark))
    assert j.covers and j.signed_through == mark


@pytest.mark.parametrize("mark", [
    {"via": "hand", "login": "kyuhwan"}, {"via": "console"}, {"login": "kyuhwan"},
    {"via": "console", "login": "kyu hwan"}, {"via": "console", "login": "a@b.c"},
    {"via": "console", "login": "x" * 65}, {"via": "console", "login": "kyuhwan", "extra": 1},
    "console", None, []])
def test_a_signed_through_that_is_not_the_console_mark_covers_nothing(mark):
    j = experiments.judge_approval(plan(), approval(signed_through=mark))
    assert j.relevant and not j.covers and "signed_through" in j.why_void


def test_how_it_was_signed_is_said_in_words():
    assert experiments.signed_words(None) == "signed by hand"
    words = experiments.signed_words({"via": "console", "login": "kyuhwan"})
    assert "through the console" in words and "kyuhwan" in words
    assert "runtime checks" in words  # the console does not read the person's login file


# -- the run request and its three replies: run_interface.schema.json -----------------------------


def test_the_run_request_is_the_schemas_and_names_the_approval_files_hash():
    msg = experiments.run_request(SHA)
    assert msg == {"run": SHA} and fits(msg, DEFS["run_request"])
    assert not fits({"run": "approvals/appr.json"}, DEFS["run_request"])  # a path is not a request


@pytest.mark.parametrize("bad", ["", "AB" * 32, "ab" * 31, "ab" * 33, "sha256:" + SHA, "/x/" + SHA])
def test_a_request_is_made_only_from_a_sha256_in_lower_case_hex(bad):
    with pytest.raises(ValueError):
        experiments.run_request(bad)


def test_the_request_the_console_builds_is_the_only_shape_the_schema_admits():
    assert not fits({"run": SHA, "plan": "x"}, DEFS["run_request"])
    assert not fits({}, DEFS["run_request"])


REPLIES = [
    {"run": "started", "run_id": "run-20261026-001"},
    {"run": "waiting_for_bench", "run_id": "run-20261026-002"},
    {"run": "refused", "reason": "no approval on disk names this plan"},
]


def _reply_specs():
    return DEFS["run_reply"]["oneOf"]


def fits_one_reply(reply) -> bool:
    """oneOf: exactly one of the three accepts it."""
    return sum(fits(reply, spec) for spec in _reply_specs()) == 1


@pytest.mark.parametrize("reply", REPLIES)
def test_each_reply_fits_exactly_one_of_the_schemas_three_and_is_said_in_words(reply):
    assert fits_one_reply(reply)
    words = experiments.reply_words(reply)
    assert isinstance(words, experiments.ReplyWords) and words.text and words.kind != "unreadable"


def test_the_schemas_own_examples_are_replies_and_its_refused_ones_are_not_believed():
    for example in DEFS["run_reply"]["examples"]:
        assert fits_one_reply(example) and experiments.reply_words(example).kind != "unreadable"
    for refused in DEFS["run_reply"]["x_refused"]:
        assert not fits_one_reply(refused) and experiments.reply_words(refused).kind == "unreadable"
    for example in DEFS["run_request"]["examples"]:
        assert fits(example, DEFS["run_request"]) and experiments.run_request(example["run"]) == example
    for refused in DEFS["run_request"]["x_refused"]:
        assert not fits(refused, DEFS["run_request"])


def test_started_names_the_run_id():
    words = experiments.reply_words(REPLIES[0])
    assert words.kind == "started" and "run-20261026-001" in words.text


def test_waiting_for_the_bench_is_the_person_at_the_microscope_and_offers_nothing():
    words = experiments.reply_words(REPLIES[1])
    assert words.kind == "waiting_for_bench" and "microscope" in words.text
    assert "run-20261026-002" in words.text
    assert words.offers == []  # nothing in the console stands for the hand-over


def test_a_refusal_carries_its_reason():
    words = experiments.reply_words(REPLIES[2])
    assert words.kind == "refused" and "no approval on disk names this plan" in words.text


@pytest.mark.parametrize("reply", [
    {"run": "refused"}, {"run": "refused", "reason": ""},
    {"run": "started"}, {"run": "started", "run_id": "run-1"},
    {"run": "waiting_for_bench", "run_id": "run-20261026-1"},
    {"run": "started", "run_id": "run-20261026-001", "backend": "hardware"},
    {"run": "queued", "run_id": "run-20261026-001"}, {}, "started", None])
def test_a_reply_the_schema_does_not_admit_is_not_believed(reply):
    words = experiments.reply_words(reply)
    assert words.kind == "unreadable" and words.offers == []
    assert "not understood" in words.text
    assert not fits_one_reply(reply)


# -- how a run ended -----------------------------------------------------------------------------


def test_every_way_a_run_ends_has_its_words_and_no_other_does():
    assert set(experiments.ENDED_WORDS) == set(sma_run.RUN_ENDED_HOW)
    assert all(experiments.ended_words(how) == experiments.ENDED_WORDS[how] for how in sma_run.RUN_ENDED_HOW)
    assert "refus" in experiments.ended_words("refused")
    assert "safety" in experiments.ended_words("aborted_by_monitor")


def test_a_how_that_is_not_the_contracts_is_shown_as_the_run_wrote_it():
    words = experiments.ended_words("stopped: still running after the person's answer")
    assert "stopped: still running after the person's answer" in words
    assert experiments.ended_words(None) is None


# -- the hand-step sheet: devices/manual.py's format -----------------------------------------------

OPEN = """# manual steps for run-20261026-001

## s1 - optical_tweezers

Switch the trapping laser on at the controller and confirm the bead is held.

- opened: 2026-10-26T10:05:00Z
- **not confirmed** - nothing on this lock group proceeded
"""

CLOSED = """# manual steps for run-20261026-001

## s1 - sample_loading / hole 3

Check the loading: the sample is on the stage and the cover is closed.

- opened: 2026-10-26T10:05:00Z
- confirmed: 2026-10-26T10:07:30Z by kyuhwan
- observed: sample loaded, no air bubble

## s2 - optical_tweezers

Switch the trapping laser off.

- opened: 2026-10-26T10:20:00Z
- confirmed: 2026-10-26T10:21:00Z by kyuhwan
- observed: (nothing recorded)
"""


def test_a_sheet_not_confirmed_is_open():
    (s,) = experiments.parse_manual_steps(OPEN)
    assert (s.sheet_id, s.channel, s.element) == ("s1", "optical_tweezers", None)
    assert not s.confirmed and s.opened_at == "2026-10-26T10:05:00Z"
    assert "trapping laser" in s.instruction


def test_confirmed_sheets_keep_who_when_and_what_was_observed():
    a, b = experiments.parse_manual_steps(CLOSED)
    assert (a.sheet_id, a.channel, a.element) == ("s1", "sample_loading", "hole 3")
    assert a.confirmed and a.confirmed_at == "2026-10-26T10:07:30Z" and a.confirmed_by == "kyuhwan"
    assert a.observed == "sample loaded, no air bubble"
    assert b.confirmed and b.observed is None  # "(nothing recorded)" is no observation


def test_a_sheet_the_parser_cannot_place_is_open_not_confirmed():
    """Anything without a confirmed line waits: an unreadable sheet never reads as a done step."""
    (s,) = experiments.parse_manual_steps("## s9 - optical_tweezers\n\nDo it.\n\n- opened: 2026-10-26T10:00:00Z\n")
    assert not s.confirmed
    assert experiments.parse_manual_steps("") == []
    assert experiments.parse_manual_steps("no sheets here") == []


def test_the_waiting_line_has_no_button_in_it():
    line = experiments.WAITING_LINE
    assert line == "Waiting for a step at the microscope. Confirm it there."


# -- what a stop leaves on: the tweezers laser ---------------------------------------------------


def trap_events():
    return [{"t_mono": 1.0, "event": "apply", "channel": "optical_tweezers", "action": "on",
             "params": {"commands": [["TRAP_ON", "t1"]]}}]


@pytest.mark.parametrize("how", ["stopped_from_outside", "aborted_by_monitor"])
def test_a_stop_on_a_run_that_had_traps_says_the_laser_is_assumed_on(how):
    note = experiments.tweezers_note(how, trap_events())
    assert note == "tweezers laser: software cannot switch it; assumed on until you confirm"


@pytest.mark.parametrize("how", ["completed", "failed", "refused", None])
def test_the_note_is_for_a_stop_only(how):
    assert experiments.tweezers_note(how, trap_events()) is None


def test_a_stop_on_a_run_with_no_traps_says_nothing_about_the_laser():
    assert experiments.tweezers_note("stopped_from_outside", []) is None
    other = [{"t_mono": 1.0, "event": "apply", "channel": "aura", "action": "on", "params": {"commands": []}}]
    assert experiments.tweezers_note("stopped_from_outside", other) is None


# -- the example map: only recorded data, never drawn from a guess --------------------------------


def test_the_sample_map_parts_are_each_not_built_and_say_why():
    parts = {p["part"]: p for p in experiments.SAMPLE_MAP_PARTS}
    assert set(parts) == {"frames_with_stage_readback", "hole_fitter", "candidate_finder", "flags_and_confirmations"}
    assert all(p["state"] == "not_built" and p["why"] for p in parts.values())
    assert "stage" in parts["frames_with_stage_readback"]["why"]
