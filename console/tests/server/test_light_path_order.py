"""The light-path order the Instruments page draws from (console card 023, part 2): the server side.

The order is `light_path_order` in contracts/schemas/idle_status.schema.json. It is read from two places only: the
latest `snapshot` event of the followed run, and card 085's status file outside a run. Every instance used here is the
schema file's own `examples` or `x_refused`, read from the file and not from a copy, so a change to the shape moves
these tests with it. The page's words come in the web tests; this side only says which of four things the source is:
no order, an order with a reason for having none, an order, or an order not understood.
"""

from __future__ import annotations

import copy
import json

import pytest
from sma_fake_run import tree_state
from test_instruments import (  # noqa: F401  -- the fixtures of the Instruments tests, shared
    LATEST,
    STATUS,
    client,
    ev,
    idle,
    reading,
    runs,
    snap,
    stand,
    tree,
    write_status,
)

from sma_console.agents.schema_lite import Schemas
from sma_console.agents.sma_files import repository_root

SCHEMAS = repository_root() / "contracts" / "schemas"
DEF = json.loads((SCHEMAS / "idle_status.schema.json").read_text(encoding="utf-8"))["$defs"]["light_path_order"]
EXAMPLES: list[dict] = DEF["examples"]
REFUSED: list[dict] = DEF["x_refused"]
READ = next(e for e in EXAMPLES if e["status"] == "read")
NOT_IN = next(e for e in EXAMPLES if e["status"] == "not_in_snapshot")
STAND = {"stand_ti2e": stand({"nosepiece": "3"})}


def order_of(got):
    return got["path"]["order"]


def with_order(order, run, t=1.0, label="before", states=None):
    ev(run, t, event="snapshot", label=label, states=states or STAND, light_path_order=order)


def status_with(root, order=None, **over):
    doc = idle(**over)
    if order is not None:
        doc["light_path_order"] = order
    write_status(root, doc)


def test_the_schemas_own_examples_are_orders_and_every_x_refused_is_not():
    schemas = Schemas(SCHEMAS)
    assert len(EXAMPLES) >= 2 and len(REFUSED) >= 2
    for e in EXAMPLES:
        assert schemas.validate_def(e, "idle_status.schema.json", "#/$defs/light_path_order") == [], e["status"]
    for r in REFUSED:
        assert schemas.validate_def(r, "idle_status.schema.json", "#/$defs/light_path_order") != [], r


# -- during a run: the latest snapshot event -----------------------------------------------------------------


def test_a_run_whose_snapshot_carries_an_order_gives_it_whole(client, tree, runs):
    run = runs("run-20261026-001")
    with_order(READ, run)
    got = client().get(LATEST).json()
    assert order_of(got) == {"state": "read", "data": READ, "problems": []}


def test_an_order_is_given_as_written_in_the_order_the_file_has_it(client, tree, runs):
    run = runs("run-20261026-001")
    swapped = copy.deepcopy(READ)
    swapped["branches"][0]["elements"].reverse()
    swapped["branches"][0]["elements"][0]["element"] = "renamed_element"
    with_order(swapped, run)
    data = order_of(client().get(LATEST).json())["data"]
    assert [e["element"] for e in data["branches"][0]["elements"]] == ["renamed_element", "dia_lamp"]
    assert [e["element"] for e in data["branches"][0]["elements"]] != [e["element"] for e in READ["branches"][0]["elements"]]


def test_a_not_in_snapshot_order_is_given_with_its_reason(client, tree, runs):
    run = runs("run-20261026-001")
    with_order(NOT_IN, run)
    got = order_of(client().get(LATEST).json())
    assert got["state"] == "not_in_snapshot" and got["data"]["reason"] == NOT_IN["reason"] and got["problems"] == []


def test_a_snapshot_with_no_order_key_is_a_source_with_no_order(client, tree, runs):
    run = runs("run-20261026-001")
    snap(run, 1.0, STAND)
    assert order_of(client().get(LATEST).json()) == {"state": "none", "data": None, "problems": []}


def test_only_the_latest_snapshot_is_read_and_an_older_order_is_never_carried_forward(client, tree, runs):
    run = runs("run-20261026-001")
    with_order(READ, run, 1.0)
    snap(run, 2.0, STAND, "after")
    assert order_of(client().get(LATEST).json())["state"] == "none"
    with_order(NOT_IN, run, 3.0, "later")
    assert order_of(client().get(LATEST).json())["state"] == "not_in_snapshot"


def test_a_run_with_no_snapshot_has_no_order(client, tree, runs):
    runs("run-20261026-001")
    assert order_of(client().get(LATEST).json())["state"] == "none"


@pytest.mark.parametrize("n", range(len(REFUSED)))
def test_an_order_in_an_event_that_the_schema_refuses_is_not_understood_and_gives_no_data(client, tree, runs, n):
    run = runs("run-20261026-001")
    with_order(REFUSED[n], run)
    got = order_of(client().get(LATEST).json())
    assert got["state"] == "not_understood" and got["data"] is None and got["problems"], n


def test_an_order_that_is_not_an_object_is_not_understood(client, tree, runs):
    run = runs("run-20261026-001")
    with_order("read", run)
    got = order_of(client().get(LATEST).json())
    assert got["state"] == "not_understood" and got["data"] is None


def test_an_order_with_a_null_value_is_not_understood_and_not_taken_for_no_order(client, tree, runs):
    run = runs("run-20261026-001")
    with_order(None, run)
    assert order_of(client().get(LATEST).json())["state"] == "not_understood"


def test_the_problems_are_capped(client, tree, runs):
    run = runs("run-20261026-001")
    bad = copy.deepcopy(READ)
    bad["branches"] = [{"branch": "A B", "elements": [{"element": "X", "channel": 3, "entry_ref": []}] * 20, "place_not_recorded": []}]
    with_order(bad, run)
    assert 0 < len(order_of(client().get(LATEST).json())["problems"]) <= 8


def test_an_order_cannot_be_checked_without_the_schema_in_the_tree_and_is_then_not_understood(client, tree, runs):
    run = runs("run-20261026-001")
    with_order(READ, run)
    (tree / "contracts" / "schemas" / "idle_status.schema.json").unlink()
    got = order_of(client().get(LATEST).json())
    assert got["state"] == "not_understood" and got["data"] is None and "cannot be checked" in got["problems"][0]


# -- outside a run: the status file ---------------------------------------------------------------------------


def test_the_status_file_gives_its_order(client, tree):
    status_with(tree, READ)
    got = client().get(LATEST).json()
    assert got["path"]["source"] == "status_file" and order_of(got) == {"state": "read", "data": READ, "problems": []}


def test_the_status_file_gives_a_not_in_snapshot_order_with_its_reason(client, tree):
    status_with(tree, NOT_IN)
    got = order_of(client().get(LATEST).json())
    assert got["state"] == "not_in_snapshot" and got["data"]["reason"] == NOT_IN["reason"]


def test_a_status_file_with_no_order_key_is_a_source_with_no_order(client, tree):
    status_with(tree)
    assert order_of(client().get(LATEST).json())["state"] == "none"


@pytest.mark.parametrize("n", range(len(REFUSED)))
def test_a_status_file_whose_order_the_schema_refuses_is_still_a_status_and_its_order_is_not_understood(client, tree, n):
    status_with(tree, REFUSED[n])
    c = client()
    got = c.get(LATEST).json()
    assert got["path"]["source"] == "status_file" and [e["name"] for e in got["path"]["elements"]]  # 017's list is still there
    assert order_of(got)["state"] == "not_understood" and order_of(got)["data"] is None and order_of(got)["problems"], n
    status = c.get(STATUS).json()
    assert status["state"] == "present" and status["data"]["light_path_order"] == REFUSED[n]


def test_a_status_file_that_fails_elsewhere_is_still_not_a_status_whatever_its_order_is(client, tree):
    bad = idle()
    bad["light_path_order"] = READ
    bad["last_run"]["last_snapshot"]["channels"][0]["how"] = "guessed"
    write_status(tree, bad)
    c = client()
    assert c.get(STATUS).json()["state"] == "invalid"
    assert c.get(LATEST).json()["path"]["source"] == "none"
    both = copy.deepcopy(bad)
    both["light_path_order"] = REFUSED[0]
    write_status(tree, both)
    assert c.get(STATUS).json()["state"] == "invalid"


def test_the_status_file_is_read_when_no_run_is_running_and_the_run_when_one_is(client, tree, runs):
    status_with(tree, NOT_IN)
    run = runs("run-20261026-001")
    with_order(READ, run)
    got = client().get(LATEST).json()
    assert got["path"]["source"] == "run" and order_of(got)["state"] == "read"
    run.end()
    got = client().get(LATEST).json()
    assert got["path"]["source"] == "status_file" and order_of(got)["state"] == "not_in_snapshot"


def test_an_ended_run_with_no_status_file_gives_the_last_snapshots_order(client, tree, runs):
    run = runs("run-20261026-001")
    with_order(READ, run)
    run.end()
    got = client().get(LATEST).json()
    assert got["path"]["source"] == "last_snapshot" and order_of(got)["state"] == "read"


def test_no_run_and_no_status_file_has_no_order(client, tree, runs):
    got = client().get(LATEST).json()
    assert got["state"] == "no_run" and order_of(got) == {"state": "none", "data": None, "problems": []}


def test_no_runs_folder_and_no_status_file_has_no_order(client, tree):
    got = client().get(LATEST).json()
    assert got["state"] == "runs_not_found" and order_of(got)["state"] == "none"


def test_reading_the_order_writes_nothing(client, tree, runs):
    run = runs("run-20261026-001")
    with_order(READ, run)
    status_with(tree, READ)
    before = tree_state(tree)
    c = client()
    for _ in range(3):
        assert c.get(LATEST).status_code == 200 and c.get(STATUS).status_code == 200
    assert tree_state(tree) == before


def test_the_readings_beside_the_order_are_the_same_with_it_and_without_it(client, tree, runs):
    run = runs("run-20261026-001")
    with_order(READ, run)
    ordered = client().get(LATEST).json()["path"]["elements"]
    run.end()
    plain = runs("run-20261027-001")
    snap(plain, 1.0, STAND)
    bare = client().get(LATEST).json()["path"]["elements"]
    assert ordered and [(e["name"], e["state"], e["value"]) for e in ordered] == [(e["name"], e["state"], e["value"]) for e in bare]


def test_a_status_files_readings_do_not_decide_the_order(client, tree):
    doc = idle(light_path_order=READ)
    doc["last_run"]["last_snapshot"]["channels"] = [reading("stand_ti2e", "Stand", "not_read")]
    write_status(tree, doc)
    assert order_of(client().get(LATEST).json())["state"] == "read"
