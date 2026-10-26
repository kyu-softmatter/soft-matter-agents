"""Run when operator.gate or find_approval changes: is another login's run still refused?

A question asked through the console carries `-c<NNN>` in its id, and its run
waits for the person at every tier (plan.md 6 after the tier table, 7.1.1
rule 9; task 028). This builds plans in a temporary tree, runs them through
`operator.run` on the mock, and requires each of task 028's six cases:

1. a console plan with an exact plan_approval and a readable inbox item runs as
   a smoke run, and its log names the item's file and the approval's, each by
   path and sha256;
2. the same plan is refused before anything is created with no approval, with
   only a scope_approval listing it, and as a Tier 1 plan with no approval;
3. it is refused under an exact approval with no inbox item, an unparseable
   item, and an attachment whose sha256 does not match;
4. a window-form plan behaves as before in test 2's three cases;
5. a window-form Tier 2 plan with a correct plan_approval runs as a smoke run
   and as one arm -- the approval is hashed against the plan on disk, not the
   smoke or arm view;
6. the `c` in the plan's qid is what decides: a plan whose other fields read
   as a window question, and whose item is marked as the person's own, is
   still refused without an approval.

Task 029 adds what check 91 reads: test 1's log carries the item at its top
level, equal to the gate event's copy, and validates against
run_log.schema.json; tests 4 and 5's window logs carry no `console_item` key
anywhere; and 7, an item under the real `simulation_agent/console_inbox/` is
recorded with a repo-relative, slash-separated path (the folder is not
created).

    PYTHONUTF8=1 python -m src.check_other_login_refusal      # from simulation_agent/

It needs numpy, and jsonschema with referencing for test 1's schema check,
and not `contracts`. Approvals, console inbox, runs, envelope
and the question's directory are all in a temporary folder; the template plan
and the budget are read from this tree and never written. It ends by showing
that `git status --short -- simulation_agent` did not change. Exit 0 when every
case holds.

On Windows the operator's peak-memory line imports `resource`, which exists
only on Unix; a stub reporting zero is installed for that one import, so the
record path runs. It changes no verdict this script checks.
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import types
from pathlib import Path

from . import cards
from . import hoomd_backend
from . import mock_backend
from . import operator

try:
    import resource  # noqa: F401
except ImportError:
    _stub = types.ModuleType("resource")
    _stub.RUSAGE_SELF = 0
    _stub.getrusage = lambda who: types.SimpleNamespace(ru_maxrss=0)
    sys.modules["resource"] = _stub

REAL_REPO, REAL_AGENT = cards.REPO, cards.AGENT
REAL_INBOX = operator.CONSOLE_INBOX           # as imported, before any case points it into a temp tree
TEMPLATE = cards.AGENT / "questions" / "sim-20260917-001" / "v3_plan_simulation_sim-20260917-001.json"
BUDGET = cards.AGENT / "envelope" / "budget.json"
CONSOLE_QID = "sim-20261024-c001"
WINDOW_QID = "sim-20261024-001"
ITEM_ID = "ci-20261024-101500-ab12"


class BackendBuilt(Exception):
    """Raised by the spy when operator.run gets as far as building a backend."""


def git_status() -> str:
    out = subprocess.run(["git", "-C", str(REAL_REPO), "status", "--short", "--", "simulation_agent"],
                         capture_output=True, text=True)
    return out.stdout if out.returncode == 0 else f"(git status failed: {out.stderr.strip()})"


def sandbox(tmp: Path, name: str) -> Path:
    """A fresh tree for one case, and every operator path pointed into it."""
    repo = tmp / name
    agent = repo / "simulation_agent"
    (agent / "envelope").mkdir(parents=True)
    (agent / "approvals").mkdir()
    (agent / "envelope" / "budget.json").write_bytes(BUDGET.read_bytes())
    cards.REPO, cards.AGENT = repo, agent
    operator.APPROVALS = agent / "approvals"
    operator.RUNS = agent / "runs"
    operator.ENVELOPE = agent / "envelope" / "budget.json"
    operator.CONSOLE_INBOX = agent / "console_inbox"
    return agent


def make_plan(qid: str, tier: int, arms: bool = False, plan_id: str | None = None) -> dict:
    """The template plan as a revision-1 card of `qid`, written into the sandbox."""
    p = copy.deepcopy(json.loads(TEMPLATE.read_text(encoding="utf-8")))
    p.update(qid=qid, id=plan_id or f"plan-{qid}-r1", revision=1, status="VALIDATED")
    for a in p["actions"]:
        if a["tier"] >= 1:
            a["tier"] = tier
    p["smoke"] = {"record_fraction": "smoke_record_fraction"}
    p["numbers"].append({"name": "smoke_record_fraction", "value": 0.01, "unit": "1",
                         "source": "assumed:test", "grade": "E5"})
    if arms:
        cond = next(c for c in p["conditions"] if c["parameter"] == "n_particles")
        p["conditions"] = [c for c in p["conditions"] if c is not cond]
        p["numbers"].append({**next(n for n in p["numbers"] if n["name"] == "n_particles"),
                             "name": "n_particles_b", "value": 500})
        p["compare_arms"] = [{"arm": "a", "conditions": [cond]},
                             {"arm": "b", "conditions": [{**cond, "number": "n_particles_b"}]}]
    qdir = cards.question_dir(qid)
    qdir.mkdir(parents=True)
    (qdir / "goal.json").write_text(json.dumps({"revision": 1}), encoding="utf-8")
    (qdir / f"plan_simulation_{qid}.json").write_text(json.dumps(p, indent=2), encoding="utf-8")
    return json.loads((qdir / f"plan_simulation_{qid}.json").read_text(encoding="utf-8"))


def approve(agent: Path, plan: dict) -> Path:
    path = agent / "approvals" / "pa-test-001.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"card": "plan_approval", "id": "pa-test-001", "plan_id": plan["id"],
                                "plan_revision": plan["revision"], "plan_hash": operator.plan_hash(plan)}),
                    encoding="utf-8")
    return path


def scope(agent: Path, qid: str) -> Path:
    path = agent / "approvals" / "sa-test-001.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"card": "scope_approval", "id": "sa-test-001", "qids": [qid]}), encoding="utf-8")
    return path


def inbox_item(agent: Path, qid: str, mark: str = "other_login", attachment_sha: str | None = None,
               raw: bytes | None = None) -> Path:
    inbox = agent / "console_inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    att = inbox / f"{ITEM_ID}--notes.txt"
    att.write_bytes(b"a file the asker attached\n")
    item = {"schema_version": "0.1", "item_id": ITEM_ID, "artifact": "console_question", "question_id": qid,
            "words": "what is the diffusivity of a 5 um bead in water?",
            "asked_by": {"login": "guest1", "console_role": {"may_ask": True, "may_draft": False,
                                                             "agents": ["simulation"], "may_ask_model_run": True}},
            "asked_at": "2026-10-24T10:15:00Z", "asker_mark": {"kind": mark},
            "attachments": [{"file": att.name,
                             "sha256": attachment_sha or hashlib.sha256(att.read_bytes()).hexdigest()}]}
    path = inbox / f"{ITEM_ID}.json"
    path.write_bytes(raw if raw is not None else json.dumps(item).encode())
    return path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def runs_it(qid: str, arm: str | None = None, budget: str = operator.SMOKE) -> Path:
    return operator.run(qid, "run-test-001", backend=mock_backend.MockBackend(seed=1), budget=budget, arm=arm)


def refuses(qid: str, *needles: str) -> str:
    """operator.run refuses, builds no backend, creates no run directory, and its reason holds every needle."""
    built = []

    class Spy:
        def __init__(self, *a, **k):
            built.append(1)
            raise BackendBuilt("operator.run built a backend")

    saved = hoomd_backend.HoomdBackend, mock_backend.MockBackend
    hoomd_backend.HoomdBackend = mock_backend.MockBackend = Spy
    try:
        operator.run(qid, "run-test-001")
    except operator.Refused as exc:
        reason = str(exc)
    except BackendBuilt:
        raise AssertionError("the run was not refused: it got as far as building a backend")
    else:
        raise AssertionError("the run was not refused")
    finally:
        hoomd_backend.HoomdBackend, mock_backend.MockBackend = saved
    assert not built, "a backend was built before the refusal"
    assert not operator.RUNS.exists() or not any(operator.RUNS.iterdir()), "runs/ is not empty after the refusal"
    missing = [n for n in needles if n not in reason]
    assert not missing, f"the reason does not name {missing}: {reason}"
    return reason


def log_of(out: Path) -> dict:
    return json.loads((out / "log.json").read_text(encoding="utf-8"))


def gate_event(log: dict) -> dict:
    return next(e for e in log["events"] if e["event"] == "gate")


def no_console_item(log: dict) -> None:
    """A window run's log carries no console_item key, at the top or in the gate event (task 029)."""
    assert "console_item" not in log, f"a window run's log.json carries console_item: {log['console_item']!r}"
    assert "console_item" not in gate_event(log), "a window run's gate event carries console_item"


def run_log_errors(log: dict) -> list[str]:
    """What run_log.schema.json says against `log`, read from this tree's contracts/ and never written."""
    import jsonschema
    from referencing import Registry, Resource
    schemas = cards.CONTRACTS / "schemas"
    registry = Registry().with_resources(
        (p.name, Resource.from_contents(json.loads(p.read_text(encoding="utf-8"))))
        for p in schemas.glob("*.schema.json"))
    schema = json.loads((schemas / "run_log.schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema, registry=registry)
    return [f"/{'/'.join(map(str, e.absolute_path))}: {e.message}" for e in validator.iter_errors(log)]


def test1(tmp: Path) -> str:
    agent = sandbox(tmp, "t1")
    plan = make_plan(CONSOLE_QID, tier=2)
    a = approve(agent, plan)
    item = inbox_item(agent, CONSOLE_QID)
    log = log_of(runs_it(CONSOLE_QID))
    got = gate_event(log).get("console_item") or {}
    assert got.get("path", "").endswith(f"console_inbox/{item.name}") and got.get("sha256") == sha(item), \
        f"the log does not name the inbox item by path and sha256: {got}"
    f = log["approval"].get("file") or {}
    assert f.get("path", "").endswith(f"approvals/{a.name}") and f.get("sha256") == sha(a), \
        f"the log does not name the approval file by path and sha256: {log['approval']}"
    assert log.get("console_item") == got, \
        f"log.json's top-level console_item is not the gate event's: {log.get('console_item')!r}"
    errors = run_log_errors(log)
    assert not errors, f"log.json does not validate against run_log.schema.json: {errors}"
    return ("1: console plan, exact plan_approval, readable item: ran as a smoke run; log names the item "
            "at its top level and in the gate event, and the approval file; the log validates")


def test2(tmp: Path) -> str:
    sandbox(tmp, "t2a")
    make_plan(CONSOLE_QID, tier=2)
    refuses(CONSOLE_QID, CONSOLE_QID, "another login")
    agent = sandbox(tmp, "t2b")
    make_plan(CONSOLE_QID, tier=2)
    scope(agent, CONSOLE_QID)
    inbox_item(agent, CONSOLE_QID)
    refuses(CONSOLE_QID, CONSOLE_QID, "another login")
    agent = sandbox(tmp, "t2c")
    make_plan(CONSOLE_QID, tier=1)
    inbox_item(agent, CONSOLE_QID)
    refuses(CONSOLE_QID, CONSOLE_QID, "another login")
    return "2: console plan refused before anything was created: no approval, scope_approval only, Tier 1 with none"


def test3(tmp: Path) -> str:
    agent = sandbox(tmp, "t3a")
    approve(agent, make_plan(CONSOLE_QID, tier=2))
    refuses(CONSOLE_QID, CONSOLE_QID, "console_inbox")
    agent = sandbox(tmp, "t3b")
    approve(agent, make_plan(CONSOLE_QID, tier=2))
    inbox_item(agent, CONSOLE_QID, raw=b"{not json")
    refuses(CONSOLE_QID, CONSOLE_QID, "cannot be read")
    agent = sandbox(tmp, "t3c")
    approve(agent, make_plan(CONSOLE_QID, tier=2))
    inbox_item(agent, CONSOLE_QID, attachment_sha="0" * 64)
    refuses(CONSOLE_QID, "attachment", "hash to")
    return "3: console plan under an exact approval refused: no item, unparseable item, attachment sha256 mismatch"


def test4(tmp: Path) -> str:
    sandbox(tmp, "t4a")
    make_plan(WINDOW_QID, tier=2)
    refuses(WINDOW_QID, "no approval card names")
    agent = sandbox(tmp, "t4b")
    make_plan(WINDOW_QID, tier=2)
    scope(agent, WINDOW_QID)
    log = log_of(runs_it(WINDOW_QID))
    assert log["approval"]["kind"] == "scope_approval", log["approval"]
    no_console_item(log)
    sandbox(tmp, "t4c")
    make_plan(WINDOW_QID, tier=1)
    log = log_of(runs_it(WINDOW_QID))
    assert log["approval"] == {"id": None, "kind": None}, log["approval"]
    no_console_item(log)
    return "4: window plan as before: Tier 2 refused with none, ran under a scope_approval, ran autonomously at Tier 1"


def test5(tmp: Path) -> str:
    agent = sandbox(tmp, "t5a")
    approve(agent, make_plan(WINDOW_QID, tier=2))
    log = log_of(runs_it(WINDOW_QID))
    assert log["approval"]["kind"] == "plan_approval"
    no_console_item(log)
    agent = sandbox(tmp, "t5b")
    approve(agent, make_plan(WINDOW_QID, tier=2, arms=True))
    log = log_of(runs_it(WINDOW_QID, arm="b", budget=operator.FULL))
    assert log["approval"]["kind"] == "plan_approval" and gate_event(log)["compare_arm"] == "b"
    no_console_item(log)
    return "5: window Tier 2 plan with a correct plan_approval ran as a smoke run and as arm b"


def test6(tmp: Path) -> str:
    agent = sandbox(tmp, "t6")
    make_plan(CONSOLE_QID, tier=1, plan_id="plan-sim-20260917-001-r3")
    inbox_item(agent, CONSOLE_QID, mark="persons_own")
    refuses(CONSOLE_QID, CONSOLE_QID, "another login")
    return "6: only the qid carries the c, the item says persons_own: still refused without an approval"


def test7(tmp: Path) -> str:
    """The record's path for an item in the real inbox is repo-relative, with forward slashes.

    Check 91 compares it with the item's own path in the tree. The folder is
    not created: `_where` only spells the path.
    """
    cards.REPO, cards.AGENT = REAL_REPO, REAL_AGENT
    item = REAL_INBOX / f"{ITEM_ID}.json"
    got = operator._where(item)
    want = f"simulation_agent/console_inbox/{ITEM_ID}.json"
    assert got == want, f"an item in the real inbox is recorded as {got!r}, not {want!r}"
    return f"7: an item in the real inbox is recorded as {got}"


def strings_of(node, at: str = ""):
    """Every string in a JSON value, with where it sits."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield from strings_of(v, f"{at}/{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from strings_of(v, f"{at}/{i}")
    elif isinstance(node, str):
        yield at, node


def test8(tmp: Path) -> str:
    """The paths a run log names are repo-relative with forward slashes (task 030).

    Check 91 finds a run's plan by `plan_path` exactly, so a backslash there
    makes a console run read as a window question's. The backslash appears
    only where str() of a path runs on Windows, so this fails only there.
    """
    agent = sandbox(tmp, "t8")
    plan = make_plan(CONSOLE_QID, tier=2)
    approve(agent, plan)
    inbox_item(agent, CONSOLE_QID)
    log = log_of(runs_it(CONSOLE_QID))
    want = f"simulation_agent/questions/{CONSOLE_QID}/plan_simulation_{CONSOLE_QID}.json"
    assert (cards.REPO / want).is_file(), f"{want} is not the plan file this test wrote"
    assert log.get("plan_path") == want, f"plan_path is {log.get('plan_path')!r}, not {want!r}"
    # An absolute path outside the repository, such as the engine build's
    # interpreter, is a machine's path and not a repo path; it is left alone.
    def outside(s: str) -> bool:
        p = Path(s)
        return p.is_absolute() and not p.is_relative_to(cards.REPO) and not p.is_relative_to(REAL_REPO)
    slashed = [f"{at}: {s!r}" for at, s in strings_of(log) if "\\" in s and not outside(s)]
    assert not slashed, f"log.json holds a backslash in a repo path: {slashed}"
    named = {"plan_path": log["plan_path"], "approval/file/path": log["approval"]["file"]["path"],
             "console_item/path": log["console_item"]["path"]}
    absolute = [f"{k}: {v}" for k, v in named.items() if Path(v).is_absolute() or ":" in v]
    assert not absolute, f"log.json names a path that is not repo-relative: {absolute}"
    return f"8: the run log's paths are repo-relative with forward slashes; plan_path is {want}"


def main() -> int:
    before = git_status()
    # getattr, so the same script can be run against the operator from before task 028, which has no inbox
    saved = (cards.REPO, cards.AGENT, operator.APPROVALS, operator.RUNS, operator.ENVELOPE,
             getattr(operator, "CONSOLE_INBOX", None))
    failed = 0
    with tempfile.TemporaryDirectory() as t:
        try:
            for test in (test1, test2, test3, test4, test5, test6, test7, test8):
                try:
                    print("PASS", test(Path(t)))
                except AssertionError as exc:
                    failed += 1
                    print("FAIL", test.__name__, exc)
                except operator.Refused as exc:
                    failed += 1
                    print("FAIL", test.__name__, "refused:", exc)
        finally:
            (cards.REPO, cards.AGENT, operator.APPROVALS, operator.RUNS,
             operator.ENVELOPE, operator.CONSOLE_INBOX) = saved
    after = git_status()
    print("git status --short -- simulation_agent:", "unchanged" if after == before else f"CHANGED\n{before}\n->\n{after}")
    return 1 if failed or after != before else 0


if __name__ == "__main__":
    sys.exit(main())
