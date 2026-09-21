#!/usr/bin/env python3
"""The deterministic gate (plan.md section 8).

One program checks every card. No model takes part in it (P4): the exit code is
the only truth.

Each of the 37 checks reports one of five verdicts, and the distinction matters
more than the count:

  PASS       the check ran and found nothing wrong
  FAIL       the check ran and found something wrong
  UNDECIDED  the check needs a threshold nobody has chosen yet. An unchosen
             threshold is not a satisfied threshold (P0 rule 2, fail-closed)
  PENDING    the check needs artifacts a later milestone produces
  N/A        no artifact of that kind exists yet, so there was nothing to check

--strict turns UNDECIDED and PENDING into failures, which is what CI should use
once the milestones they wait on have landed.
--expect-fail inverts the meaning of the run: every card given must produce at
least one FAIL, and a card that stops failing breaks the run. A check nobody
tests is a check that quietly stopped working.

Usage:
  validate.py                     validate the repository
  validate.py PATH...             validate specific files or directories
  validate.py --strict
  validate.py --expect-fail examples/rejected
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
import pathlib
from pathlib import Path
from typing import Any, Iterable

CONTRACTS = Path(__file__).resolve().parent
REPO = CONTRACTS.parent

# Where the content being checked lives, and where git is asked about it, are
# not always the same directory. The pre-commit hook validates the tree the
# commit would create by unpacking the index into a scratch directory and
# running this file from there, so REPO is that export -- while checks 35 and
# 41 have to ask the real repository what is staged and who is committing. An
# export has no .git, and `git -C` inside one would either fail or, if TMPDIR
# happens to sit inside some other repository, answer confidently about that
# one instead. So the hook names the repository and only the git checks use it.
GIT_REPO = Path(os.environ.get("SMA_GIT_REPO") or REPO)

PASS, FAIL, UNDECIDED, PENDING, NA = "PASS", "FAIL", "UNDECIDED", "PENDING", "N/A"

# --------------------------------------------------------------------------- #
# findings
# --------------------------------------------------------------------------- #


@dataclass
class Finding:
    check: int
    status: str
    message: str
    path: str = ""

    def __str__(self) -> str:
        where = f" [{self.path}]" if self.path else ""
        return f"  check {self.check:>2} {self.status:<9} {self.message}{where}"


@dataclass
class Card:
    path: Path
    data: dict
    raw: str

    @property
    def kind(self) -> str:
        return self.data.get("card", "")

    @property
    def rel(self) -> str:
        try:
            return str(self.path.relative_to(REPO))
        except ValueError:
            return str(self.path)

    def numbers(self) -> dict[str, dict]:
        return {n["name"]: n for n in self.data.get("numbers", []) if isinstance(n, dict) and "name" in n}


@dataclass
class Bundle:
    cards: list[Card] = field(default_factory=list)
    md_files: list[Path] = field(default_factory=list)
    all_files: list[Path] = field(default_factory=list)
    artifacts: list[Card] = field(default_factory=list)

    def of_kind(self, *kinds: str) -> list[Card]:
        return [c for c in self.cards if c.kind in kinds]

    def of_artifact(self, *kinds: str) -> list[Card]:
        """Thread ledgers are not cards: they carry no numbers, so no grades."""
        return [a for a in self.artifacts if a.data.get("artifact") in kinds]

    def by_qid(self) -> dict[str, list[Card]]:
        out: dict[str, list[Card]] = {}
        for c in self.cards:
            out.setdefault(c.data.get("qid", ""), []).append(c)
        return out


# --------------------------------------------------------------------------- #
# registries
# --------------------------------------------------------------------------- #

UNITS = json.loads((CONTRACTS / "units.json").read_text())
LIMITS = json.loads((CONTRACTS / "validation_limits.json").read_text())

# WHICH FILE IS THE DESIGN DOCUMENT OF RECORD. `plan.md`, in English like
# everything else here. Three checks read it directly -- 42 reads section 8,
# 51 reads section 11, 55 reads section 7 -- and each names the file in its
# own findings.
#
# THE PREFERENCE WAS THE OTHER WAY UNTIL 2026-09-20 AND HAD TO BE TURNED.
# For a few hours the Korean text was canonical and `plan.md` a generated
# rendering, so this line preferred `plan_ko.md` by mere existence. Then
# architecture made `plan.md` the record and `8d61a3a` took the Korean out of
# version control -- untracked and .gitignore'd, NOT deleted. Preference by
# existence then picked a file that is in no commit:
#
#   a bare run in this working copy   -> plan_ko.md, stale, gitignored
#   the commit gate                   -> plan.md, because the gate unpacks the
#                                        INDEX to a scratch tree and an
#                                        untracked file is not in the index
#   a fresh clone, and anyone else    -> plan.md
#
# Two documents of record chosen by whether an ignored file happens to sit in
# your checkout, and the stale one still said in its own section 0 that Korean
# was canonical. The migration that made check 42 read either document was
# verified against a DELETED plan_ko.md (`b0ca1bc`), which is true of a clone
# and false here, and that gap is the whole defect: untracking is not deleting.
#
# THE FALLBACK IS ANNOUNCED, NOT SILENT, and it now says when the Korean copy
# is present but out of version control -- an editor who opens the wrong file
# gets no other warning. A run that quietly read a different file than its
# reader assumes is the shape 8.2 refuses: the defect is never the fallback,
# it is not saying which way the fallback went.
DESIGN_DOC_NAME = "plan.md" if (REPO / "plan.md").exists() else "plan_ko.md"
DESIGN_DOC = REPO / DESIGN_DOC_NAME

KB_DIR = REPO / "librarian_agent" / "kb"
KB_INDEX_PATH = KB_DIR / "index.json"


def load_kb() -> dict | None:
    """The knowledge store, if it exists.

    A store is not a librarian agent: until M3 a person curates it and agents
    read the files. What the store buys immediately is that a grade a card
    claims to have inherited can be checked instead of trusted (check 21).
    """
    if not KB_INDEX_PATH.exists():
        return None
    try:
        return json.loads(KB_INDEX_PATH.read_text())
    except json.JSONDecodeError:
        return None


KB_INDEX = load_kb()

SOURCE_GRADE = {
    "measured": "E1",
    "calibration": "E2",
    "spec": "E3",
    "prior_run": "E3",        # another project ran it; 10.3 rule 1 caps it here
    "literature": "E3",       # published, and not a vendor specification
    "operator_read": "E3",    # the operator read it off the instrument
    "operator_recall": "E5",  # the operator stated it from memory
    "computed": None,         # max(E4, worst input)
    "simulated": None,        # max(E4, worst input) too -- the model is the assumption (5.3)
    "assumed": "E5",
    "kb": None,               # inherited from kb_refs
}

PURPOSE_DEFAULT_INTENT = {
    "screen": "explore",
    "characterize": "explore",
    "compare": "explore",
    "verify": "confirm",
    "troubleshoot": "explore",
    "feed": None,       # the other side decides
}

CARD_SCHEMA = {
    "goal": "goal.schema.json",
    "plan": "plan.schema.json",
    "plan_approval": "plan_approval.schema.json",
    "scope_approval": "scope_approval.schema.json",
    "result": "result.schema.json",
    "refusal": "refusal.schema.json",
    "axis": "axis.schema.json",
    "synthesis": "synthesis.schema.json",
    "ask_simulation": "ask.schema.json",
    "ask_experiment": "ask.schema.json",
}

# Thread bookkeeping, not cards (4.4, 5.1). The discriminator is "artifact" so
# that a stray status.json cannot validate as one by sitting in the right place.
ARTIFACT_SCHEMA = {
    "thread_status": "thread_status.schema.json",
    "round_hashes": "round_hashes.schema.json",
    "screening": "screening.schema.json",
    "run_log": "run_log.schema.json",
    "envelope_safety": "envelope_safety.schema.json",
    # Split from envelope_safety on 2026-09-20 (plan.md 7): the simulation tree
    # holds budget.json and no safety.json, because the grade of harm differs.
    # Writing the schema is not wiring it -- check 1 resolves an artifact
    # through this dict alone, so until this line existed a budget.json would
    # have been refused as an unknown artifact the moment it appeared.
    "envelope_budget": "envelope_budget.schema.json",
}

GRADE_ORDER = ["E1", "E2", "E3", "E4", "E5", "E6"]


def worse(a: str, b: str) -> str:
    return a if GRADE_ORDER.index(a) >= GRADE_ORDER.index(b) else b


# --------------------------------------------------------------------------- #
# units and dimensions
# --------------------------------------------------------------------------- #


def unit_entry(unit: str) -> dict | None:
    return UNITS["units"].get(unit)


def dim_of(unit: str) -> dict[str, int] | None:
    e = unit_entry(unit)
    return dict(e["dim"]) if e else None


def si_factor(unit: str, temperature_k: float | None) -> float | None:
    """Convert one `unit` to SI base units. kT needs a temperature to be defined."""
    e = unit_entry(unit)
    if e is None:
        return None
    if e.get("si_factor") is None:
        if unit == "kT":
            if temperature_k is None:
                return None
            return UNITS["constants"]["k_B"]["value"] * temperature_k
        return None
    return float(e["si_factor"])


def dim_mul(a: dict, b: dict, sign: int = 1) -> dict:
    out = dict(a)
    for k, v in b.items():
        out[k] = out.get(k, 0) + sign * v
    return {k: v for k, v in out.items() if v != 0}


def dim_pow(a: dict, n: float) -> dict:
    return {k: v * n for k, v in a.items() if v * n != 0}


def dims_equal(a: dict, b: dict) -> bool:
    return {k: v for k, v in a.items() if v} == {k: v for k, v in b.items() if v}


def round_to_sig(value: float, digits: int) -> float:
    """Round to `digits` significant figures. Ties go away from zero, so the
    result does not depend on the platform's rounding mode."""
    if value == 0:
        return 0.0
    exp = math.floor(math.log10(abs(value)))
    scale = 10 ** (digits - 1 - exp)
    scaled = abs(value) * scale
    frac = scaled - math.floor(scaled)
    rounded = math.floor(scaled) + (1 if frac >= 0.5 else 0)
    return math.copysign(rounded / scale, value)


def sig_figs(value: float) -> int:
    """Significant figures of the shortest round-trip decimal form."""
    if value == 0:
        return 1
    s = repr(abs(float(value)))
    if "e" in s or "E" in s:
        s = s.split("e")[0].split("E")[0]
    s = s.replace(".", "").lstrip("0")
    s = s.rstrip("0") or "0"
    return max(1, len(s))


# --------------------------------------------------------------------------- #
# restricted formula evaluation
# --------------------------------------------------------------------------- #

CONSTANTS = {"pi": (math.pi, {}), "k_B": (UNITS["constants"]["k_B"]["value"], {"M": 1, "L": 2, "T": -2, "Th": -1})}


class FormulaError(Exception):
    pass


def eval_formula(expr: str, env: dict[str, tuple[float, dict]]) -> tuple[float, dict]:
    """Evaluate an arithmetic expression over named SI quantities.

    Returns (value_in_si, dimension). Only + - * / ** and parentheses; every name
    must be a number in the same card or a declared constant. Nothing else is
    reachable, so a formula cannot become a code path.
    """
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise FormulaError(f"cannot parse {expr!r}: {exc}") from exc

    def walk(node: ast.AST) -> tuple[float, dict]:
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                return float(node.value), {}
            raise FormulaError(f"non-numeric constant {node.value!r}")
        if isinstance(node, ast.Name):
            if node.id in env:
                return env[node.id]
            if node.id in CONSTANTS:
                return CONSTANTS[node.id]
            raise FormulaError(f"unknown name {node.id!r}")
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            v, d = walk(node.operand)
            return (v if isinstance(node.op, ast.UAdd) else -v), d
        if isinstance(node, ast.BinOp):
            lv, ld = walk(node.left)
            rv, rd = walk(node.right)
            if isinstance(node.op, ast.Mult):
                return lv * rv, dim_mul(ld, rd)
            if isinstance(node.op, ast.Div):
                if rv == 0:
                    raise FormulaError("division by zero")
                return lv / rv, dim_mul(ld, rd, -1)
            if isinstance(node.op, (ast.Add, ast.Sub)):
                if not dims_equal(ld, rd):
                    raise FormulaError(f"dimension mismatch in {'+' if isinstance(node.op, ast.Add) else '-'}: {ld} vs {rd}")
                return (lv + rv if isinstance(node.op, ast.Add) else lv - rv), ld
            if isinstance(node.op, ast.Pow):
                if rd:
                    raise FormulaError("exponent must be dimensionless")
                return lv ** rv, dim_pow(ld, rv)
            raise FormulaError(f"operator {type(node.op).__name__} not allowed")
        raise FormulaError(f"node {type(node).__name__} not allowed")

    return walk(tree)


def card_env(card: Card) -> tuple[dict[str, tuple[float, dict]], list[str]]:
    """Every number of a card as (SI value, dimension), plus problems found."""
    problems: list[str] = []
    nums = card.numbers()
    temp = None
    for n in nums.values():
        if n.get("name") == "temperature" and n.get("unit") == "K":
            temp = float(n["value"])
    env: dict[str, tuple[float, dict]] = {}
    for name, n in nums.items():
        f = si_factor(n.get("unit", ""), temp)
        d = dim_of(n.get("unit", ""))
        if f is None or d is None:
            e = unit_entry(n.get("unit", ""))
            if e is not None and e.get("si_factor") is None and n.get("unit") == "kT" and temp is None:
                problems.append(f"{name}: unit kT needs a number named temperature in K")
            else:
                problems.append(f"{name}: unknown unit {n.get('unit')!r}")
            continue
        env[name] = (float(n["value"]) * f, d)
    return env, problems


# --------------------------------------------------------------------------- #
# discovery
# --------------------------------------------------------------------------- #

SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules"}


REJECTED = "rejected"
GROUP_DIR = re.compile(r"^check([0-9]{2})_[a-z0-9_]+$")


def fixture_group(rel: str) -> tuple[str, int] | None:
    """The group a rejected fixture belongs to, and the check it is a fixture for.

    Some defects need two files: a ledger disagreeing with its envelope, or two
    refusals repeating a pair the thread ledger does not record. Neither fits a
    rule that every file must fail on its own -- the envelope and the refusals
    are individually correct, which is the point. So a folder one level under
    rejected/ is one fixture (plan.md 11-7).

    The folder names the check, and the count requires a FAIL from that check.
    Without that, a group would stay green on any unrelated failure long after
    the defect it claims to hold had gone -- a fixture no longer testing what it
    says it tests, which is the one thing this folder exists to prevent.
    """
    parts = rel.split("/")
    if REJECTED not in parts:
        return None
    i = parts.index(REJECTED)
    if len(parts) <= i + 2:
        return None                       # a flat file: its own unit, as before
    m = GROUP_DIR.match(parts[i + 1])
    if m is None:
        return ("/".join(parts[: i + 2]), -1)
    return ("/".join(parts[: i + 2]), int(m.group(1)))


def collect(roots: Iterable[Path], include_rejected: bool = False) -> Bundle:
    """Gather cards. The cards under examples/rejected/ are meant to fail, so a
    normal sweep steps over them; --expect-fail is the run that opens them."""
    b = Bundle()
    for root in roots:
        paths = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file())
        for p in paths:
            if any(part in SKIP_DIRS for part in p.parts):
                continue
            if not include_rejected and REJECTED in p.parts:
                continue
            b.all_files.append(p)
            if p.suffix == ".md":
                b.md_files.append(p)
            if p.suffix != ".json":
                continue
            try:
                raw = p.read_text()
                data = json.loads(raw)
            except (OSError, json.JSONDecodeError) as exc:
                b.cards.append(Card(p, {"__unreadable__": str(exc)}, ""))
                continue
            if isinstance(data, dict) and "card" in data:
                b.cards.append(Card(p, data, raw))
            elif isinstance(data, dict) and "artifact" in data:
                b.artifacts.append(Card(p, data, raw))
    return b


def card_sha(card: dict) -> str:
    """sha256 of a card with status removed.

    Status moves along the state machine on the same file (5.5), so hashing it
    would void an approval at the instant it was granted. That was learned once
    for approvals (0.2-3) and had to be learned again for the bridge's ledger,
    where an approval would have made a correctly transported round report that
    its source had been tampered with. One implementation now, two readers.
    """
    body = {k: v for k, v in card.items() if k != "status"}
    blob = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(blob.encode()).hexdigest()


def plan_hash(plan: dict) -> str:
    """What a plan_approval signs (5.5). The same hash, named for its use."""
    return card_sha(plan)


# --------------------------------------------------------------------------- #
# checks
# --------------------------------------------------------------------------- #


def check_01_schema(b: Bundle) -> list[Finding]:
    out: list[Finding] = []
    unreadable = [c for c in b.cards if "__unreadable__" in c.data]
    for c in unreadable:
        out.append(Finding(1, FAIL, f"unreadable json: {c.data['__unreadable__']}", c.rel))
    cards = [c for c in b.cards if "__unreadable__" not in c.data]
    if not cards:
        return out or [Finding(1, NA, "no cards found")]
    try:
        import jsonschema
        from referencing import Registry, Resource
    except ImportError:
        for c in cards:
            if c.kind not in CARD_SCHEMA:
                out.append(Finding(1, FAIL, f"unknown card kind {c.kind!r}", c.rel))
        for a in b.artifacts:
            if a.data.get("artifact") not in ARTIFACT_SCHEMA:
                out.append(Finding(1, FAIL, f"unknown artifact kind {a.data.get('artifact')!r}", a.rel))
        out.append(Finding(1, PENDING, "jsonschema not installed: only the card discriminator was checked"))
        return out

    resources = {}
    for f in (CONTRACTS / "schemas").glob("*.json"):
        resources[f.name] = Resource.from_contents(json.loads(f.read_text()))
    registry = Registry().with_resources(resources.items())

    cap_schema_path = CONTRACTS / "capabilities" / "capabilities.schema.json"
    if cap_schema_path.exists():
        cap_schema = json.loads(cap_schema_path.read_text())
        cv = jsonschema.Draft202012Validator(cap_schema, registry=registry)
        for f in sorted((CONTRACTS / "capabilities").glob("*.json")):
            if f.name == "capabilities.schema.json":
                continue
            try:
                cap = json.loads(f.read_text())
            except json.JSONDecodeError as exc:
                out.append(Finding(1, FAIL, f"unreadable capability table: {exc}", str(f.relative_to(REPO))))
                continue
            for err in sorted(cv.iter_errors(cap), key=lambda e: list(e.path)):
                loc = "/".join(str(x) for x in err.path) or "(root)"
                out.append(Finding(1, FAIL, f"{loc}: {err.message}", str(f.relative_to(REPO))))

    obs_path = CONTRACTS / "observables.json"
    if obs_path.exists():
        obs_schema = json.loads((CONTRACTS / "schemas" / "observable.schema.json").read_text())
        ov = jsonschema.Draft202012Validator(obs_schema, registry=registry)
        for entry in json.loads(obs_path.read_text()).get("observables", []):
            for err in sorted(ov.iter_errors(entry), key=lambda e: list(e.path)):
                loc = "/".join(str(x) for x in err.path) or "(root)"
                out.append(Finding(1, FAIL, f"observable {entry.get('id')!r}: {loc}: {err.message}", "contracts/observables.json"))

    if KB_DIR.exists():
        entry_schema = json.loads((CONTRACTS / "schemas" / "kb_entry.schema.json").read_text())
        ev = jsonschema.Draft202012Validator(entry_schema, registry=registry)
        for p in sorted((KB_DIR / "entries").glob("*.json")):
            try:
                entry = json.loads(p.read_text())
            except json.JSONDecodeError as exc:
                out.append(Finding(1, FAIL, f"unreadable kb entry: {exc}", str(p.relative_to(REPO))))
                continue
            for err in sorted(ev.iter_errors(entry), key=lambda e: list(e.path)):
                loc = "/".join(str(x) for x in err.path) or "(root)"
                out.append(Finding(1, FAIL, f"{loc}: {err.message}", str(p.relative_to(REPO))))

    for a in b.artifacts:
        name = ARTIFACT_SCHEMA.get(a.data.get("artifact"))
        if name is None:
            out.append(Finding(1, FAIL, f"unknown artifact kind {a.data.get('artifact')!r}", a.rel))
            continue
        schema = json.loads((CONTRACTS / "schemas" / name).read_text())
        validator = jsonschema.Draft202012Validator(schema, registry=registry)
        for err in sorted(validator.iter_errors(a.data), key=lambda e: list(e.path)):
            loc = "/".join(str(x) for x in err.path) or "(root)"
            out.append(Finding(1, FAIL, f"{loc}: {err.message}", a.rel))

    for c in cards:
        name = CARD_SCHEMA.get(c.kind)
        if name is None:
            out.append(Finding(1, FAIL, f"unknown card kind {c.kind!r}", c.rel))
            continue
        schema = json.loads((CONTRACTS / "schemas" / name).read_text())
        validator = jsonschema.Draft202012Validator(schema, registry=registry)
        for err in sorted(validator.iter_errors(c.data), key=lambda e: list(e.path)):
            loc = "/".join(str(x) for x in err.path) or "(root)"
            out.append(Finding(1, FAIL, f"{loc}: {err.message}", c.rel))
    if not out:
        out.append(Finding(1, PASS, f"{len(cards)} cards, {len(b.artifacts)} thread ledgers and the capability tables conform to their schema"))
    return out


def check_02_units(b: Bundle) -> list[Finding]:
    out: list[Finding] = []
    n_checked = 0
    for c in b.cards:
        if "__unreadable__" in c.data:
            continue
        _, problems = card_env(c)
        for p in problems:
            out.append(Finding(2, FAIL, p, c.rel))
        nums = c.numbers()
        n_checked += len(nums)
        # an interval must carry the same dimension as the number it bounds
        for key in ("constraints", "range"):
            for iv in c.data.get(key, []) or []:
                if not isinstance(iv, dict):
                    continue
                d_iv = dim_of(iv.get("unit", ""))
                if d_iv is None:
                    out.append(Finding(2, FAIL, f"{key}[{iv.get('parameter')}]: unknown unit {iv.get('unit')!r}", c.rel))
                    continue
                for basis in iv.get("basis", []):
                    n = nums.get(basis)
                    if n is None:
                        continue
                    d_n = dim_of(n.get("unit", ""))
                    if d_n is not None and not dims_equal(d_iv, d_n):
                        out.append(Finding(2, FAIL, f"{key}[{iv.get('parameter')}] is {iv.get('unit')} but its basis {basis} is {n.get('unit')}", c.rel))
    if not out:
        out.append(Finding(2, PASS, f"{n_checked} numbers use declared units with consistent dimensions"))
    return out


def check_03_source_and_grade(b: Bundle) -> list[Finding]:
    out: list[Finding] = []
    e5_by_plan: dict[str, int] = {}
    rationales_by_plan: dict[str, set] = {}
    total = 0
    for c in b.cards:
        if "__unreadable__" in c.data:
            continue
        for n in c.data.get("numbers", []):
            total += 1
            if not n.get("source"):
                out.append(Finding(3, FAIL, f"{n.get('name')}: no source", c.rel))
            if not n.get("grade"):
                out.append(Finding(3, FAIL, f"{n.get('name')}: no grade", c.rel))
            if n.get("grade") == "E6":
                out.append(Finding(3, FAIL, f"{n.get('name')}: E6 may not appear in a card", c.rel))
            if n.get("grade") == "E5" and c.kind == "plan":
                e5_by_plan[c.rel] = e5_by_plan.get(c.rel, 0) + 1
                # 11-2's unit, settled 2026-09-19: distinct rationales, not raw
                # E5. A computed E5 almost always inherits -- of this
                # repository's 17 in one plan, 9 did and none asserted E5 on its
                # own (5.8) -- so the raw count measures how long the derivation
                # chain is, not how much was guessed. Worse, capping the raw
                # count rewards dropping `formula` and `inputs`, which is what
                # check 17 reads: a cap that pays for hiding a derivation is
                # inverted, and unlike a bypassed gate it leaves a green card
                # rather than a trace.
                src = str(n.get("source", ""))
                if src.startswith("assumed:"):
                    rationales_by_plan.setdefault(c.rel, set()).add(src.split(":", 1)[1])
    cap = LIMITS.get("max_rationales_per_plan")
    counted = {rel: len(r) for rel, r in rationales_by_plan.items()}
    for rel in e5_by_plan:
        counted.setdefault(rel, 0)
    if cap is None:
        counts = ", ".join(f"{k}: {v}" for k, v in sorted(counted.items())) or "none"
        out.append(Finding(3, UNDECIDED, f"per-plan cap on distinct assumption rationales is unset "
                                         f"({LIMITS['max_rationales_per_plan_open_question']}); counted "
                                         f"rationales = [{counts}]. Not raw E5, which counts chain length: "
                                         f"the same plans hold "
                                         + ", ".join(f"{k}: {v}" for k, v in sorted(e5_by_plan.items()))))
    else:
        for rel, n in sorted(counted.items()):
            if n > cap:
                out.append(Finding(3, FAIL, f"{n} distinct assumption rationales exceed the cap of {cap}", rel))
    if not any(f.status == FAIL for f in out):
        out.insert(0, Finding(3, PASS, f"{total} numbers carry a source and a grade, no E6"))
    return out


def check_04_assumptions_explained(b: Bundle) -> list[Finding]:
    out: list[Finding] = []
    n = 0
    for c in b.cards:
        if "__unreadable__" in c.data:
            continue
        explained: set[str] = set()
        for a in c.data.get("assumptions", []) or []:
            explained.update(a.get("numbers", []))
        for num in c.data.get("numbers", []):
            if str(num.get("source", "")).startswith("assumed:"):
                n += 1
                if num["name"] not in explained:
                    out.append(Finding(4, FAIL, f"{num['name']} is assumed but not explained in assumptions[]", c.rel))
    return out or [Finding(4, PASS, f"{n} assumed numbers are explained")]


def envelope_files() -> list:
    """Every agent's ceilings file, under either name (plan.md 7).

    Three checks used to glob `envelope/safety.json` by name. After the split
    that made the simulation tree's ceilings **invisible** to all three rather
    than refused by them -- a FAIL is loud and an empty glob is not, which is
    the worse of the two failures and the reason this is one function.
    """
    return sorted(REPO.glob("*_agent/envelope/safety.json")) + \
           sorted(REPO.glob("*_agent/envelope/budget.json"))


def check_05_envelope(b: Bundle) -> list[Finding]:
    """The ceilings a person wrote, and whether a run could read them (2.1 rule 7).

    The shape is envelope_safety.schema.json's business and check 1 holds it.
    What a schema cannot hold is the unit: it would have to name the units it
    allows, and a second list of units drifts from units.json. So the one thing
    checked here is that every ceiling converts -- because the alternative is
    that it does not, at run time, inside si(), long after the person wrote it.
    """
    envs = envelope_files()
    if not envs:
        # Say what shape is available, rather than only that nobody has written
        # one. This globs every agent, and until 2026-09-19 the line read "a
        # person writes it" for all of them -- true of the simulation side,
        # where a person had simply not yet, and misleading for the microscope,
        # where the schema expresses compute ceilings and nothing else, so no
        # person could. The keys are read off the schema rather than listed
        # here, so this stays true when the shape widens (11-11).
        try:
            sch = json.loads((CONTRACTS / "schemas" / "envelope_safety.schema.json").read_text())
            shapes = {a.split("_")[0]: sorted(d.get("properties", {}))
                      for a, d in sch["$defs"].items() if a.endswith("_limits")}
        except (OSError, KeyError, json.JSONDecodeError):
            shapes = {}
        shape = ("; the shapes available are " + "; ".join(f"{a}: {k}" for a, k in sorted(shapes.items()))) if shapes else ""
        return [Finding(5, PENDING, f"no envelope/safety.json in any agent tree; a person writes it "
                                    f"(2.1 rule 7, 10.3 rule 4){shape}")]
    out: list[Finding] = []
    n = 0
    for env in envs:
        rel = str(env.relative_to(REPO))
        try:
            doc = json.loads(env.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            out.append(Finding(5, FAIL, f"cannot be read: {exc}", rel))
            continue
        # The file says which agent's limits it carries; the path says which
        # tree it is in. A schema cannot compare the two, and a microscope file
        # sitting in the simulation tree would validate perfectly while every
        # ceiling a run resolves there is the wrong instrument's.
        declared = doc.get("agent")
        in_tree = rel.split("/")[0].removesuffix("_agent")
        if declared and declared != in_tree:
            out.append(Finding(5, FAIL, f"declares agent {declared!r} and sits in {in_tree}'s tree. A run "
                                        f"resolves ceilings by path, so this file would answer with another "
                                        f"instrument's limits (2.1 rule 1)", rel))
        for target in doc.get("targets", []) or []:
            where = f"targets[{target.get('target')!r}]"
            limits = target.get("limits") or {}
            rows = [(where, limits)] + [
                (f"{where}.smoke_budget", limits.get("smoke_budget") or {})
            ]
            for label, row in rows:
                for key, limit in row.items():
                    if not isinstance(limit, dict) or "unit" not in limit:
                        continue
                    n += 1
                    entry = unit_entry(limit["unit"])
                    if entry is None:
                        out.append(Finding(5, FAIL, f"{label}.{key} is in {limit['unit']!r}, which units.json does not define", rel))
                    elif entry.get("si_factor") is None:
                        out.append(Finding(5, FAIL, f"{label}.{key} is in {limit['unit']!r}, which has no fixed SI factor, so a run cannot compare against it", rel))
    if out:
        return out
    return [Finding(5, PENDING, f"{n} ceilings convert; comparing a plan's conditions against them is not implemented yet")]


COMPARATORS = {
    "<": lambda a, s: a < s, "<=": lambda a, s: a <= s, ">": lambda a, s: a > s,
    ">=": lambda a, s: a >= s, "==": lambda a, s: a == s, "!=": lambda a, s: a != s,
}


def as_si(num: dict) -> float | None:
    """A number in SI, or None when it does not convert -- check 2 owns that."""
    try:
        f = si_factor(str(num.get("unit")), None)
        return None if f is None else float(num["value"]) * f
    except (TypeError, ValueError, KeyError):
        return None


def check_06_criteria(b: Bundle) -> list[Finding]:
    """The criteria contract: declared before execution, and evaluated from what
    was declared rather than asserted alongside it.

    The second half was missing and cost nothing to add. `met` could be flipped
    against the card's own `observed_number` and the gate stayed green -- found
    by mutating a card (tasks/008). Nothing new has to be read: the plan's
    comparator, the threshold and the observed value are all in this bundle, so
    the gate does the same arithmetic the writer does. That matters beyond this
    one case: arithmetic only the writer performs is an opt-in guard, and the
    same arithmetic in the gate is a chokepoint (2.1 rule 9). `simulation-6`
    asked for it against its own module.
    """
    out: list[Finding] = []
    plans = b.of_kind("plan")
    if not plans:
        return [Finding(6, NA, "no plan cards")]
    for c in plans:
        nums = c.numbers()
        for kind in ("stop_criteria", "success_criteria"):
            items = c.data.get(kind) or []
            if not items:
                out.append(Finding(6, FAIL, f"{kind} is empty; it must be declared before execution", c.rel))
            targets = {t.get("metric") for t in c.data.get("targets") or []}
            for cr in items:
                # A threshold is either a claim about the world or a decision
                # (5.3.1). Both are resolved: when the target left numbers[]
                # this check would otherwise have stopped covering the
                # criteria that compare against one.
                if "target" in cr:
                    if cr["target"] not in targets:
                        out.append(Finding(6, FAIL, f"{kind}[{cr.get('id')}] is measured against the target on "
                                                    f"{cr['target']!r}, which this card does not state", c.rel))
                elif cr.get("number") not in nums:
                    out.append(Finding(6, FAIL, f"{kind}[{cr.get('id')}] points at {cr.get('number')!r}, which is not in numbers[]", c.rel))
    by_plan = {str(pc.data.get("id")): pc for pc in plans}
    recomputed = 0
    for rc in b.of_kind("result"):
        plan = by_plan.get(str(rc.data.get("plan_id") or ""))
        if plan is None:
            continue
        declared = {str(cr.get("id")): (cr, kind)
                    for kind in ("stop_criteria", "success_criteria")
                    for cr in (plan.data.get(kind) or [])}
        pnums, rnums = plan.numbers(), rc.numbers()
        for ev in rc.data.get("criteria_evaluation") or []:
            cid = str(ev.get("id"))
            if cid not in declared:
                out.append(Finding(6, FAIL, f"evaluates {cid!r}, which {plan.data.get('id')} does not declare", rc.rel))
                continue
            cr, _kind = declared[cid]
            if ev.get("met") is None:
                continue        # not evaluated; the schema makes it say why
            obs, thr = rnums.get(str(ev.get("observed_number"))), pnums.get(str(cr.get("number")))
            comp = cr.get("comparator")
            if obs is None or thr is None or comp not in COMPARATORS:
                continue        # a target-valued threshold, or a number this run does not carry
            lhs, rhs = as_si(obs), as_si(thr)
            if lhs is None or rhs is None:
                continue        # check 2 owns unconvertible units
            got = COMPARATORS[comp](lhs, rhs)
            recomputed += 1
            if got != bool(ev.get("met")):
                out.append(Finding(6, FAIL,
                    f"{cid}: says met={ev.get('met')} and {obs.get('value')} {obs.get('unit')} "
                    f"{comp} {thr.get('value')} {thr.get('unit')} is {got}. A card does not get to assert "
                    f"what its own numbers decide", rc.rel))
    if recomputed and not any(f.status == FAIL for f in out):
        out.append(Finding(6, PASS, f"{recomputed} criteria recompute to the verdict the cards state"))
    return out or [Finding(6, PASS, f"{len(plans)} plans declare machine-readable stop and success criteria")]


def check_07_state_and_approval(b: Bundle) -> list[Finding]:
    out: list[Finding] = []
    plans = {c.data.get("id"): c for c in b.of_kind("plan")}
    approvals = b.of_kind("plan_approval")
    for c in b.of_kind("plan"):
        st = c.data.get("status")
        if st == "APPROVED":
            match = [a for a in approvals if a.data.get("plan_id") == c.data.get("id")]
            if not match:
                out.append(Finding(7, FAIL, "status is APPROVED but no plan_approval card was found", c.rel))
        if st in ("RUNNING", "DONE", "FAILED") and c.data.get("revision", 1) < 1:
            out.append(Finding(7, FAIL, "revision must be at least 1", c.rel))
    for a in approvals:
        p = plans.get(a.data.get("plan_id"))
        if p is None:
            out.append(Finding(7, PENDING, f"plan {a.data.get('plan_id')!r} not in this run; revision match unverified", a.rel))
            continue
        if a.data.get("plan_revision") != p.data.get("revision"):
            out.append(Finding(7, FAIL, f"approval is for revision {a.data.get('plan_revision')} but the plan is revision {p.data.get('revision')}", a.rel))
        expect = plan_hash(p.data)
        if a.data.get("plan_hash") != expect:
            out.append(Finding(7, FAIL, f"plan_hash does not match the plan (status excluded): expected {expect}", a.rel))
    if not any(f.status == FAIL for f in out):
        out.insert(0, Finding(7, PASS, f"state transitions and {len(approvals)} approvals are consistent"))
    return out


def canon_sha(obj: dict) -> str:
    """sha256 of a card in canonical form: sorted keys, no spaces.

    Not the raw bytes. The bridge re-serialises the card it carries inside the
    envelope, so byte equality is impossible; semantic equality is what "not a
    character changed" means about a number.
    """
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(blob.encode()).hexdigest()


def vocabulary_version() -> str:
    """A content hash of the observable vocabulary, derived and never stored.

    A result says which version's estimator it ran, and that pin is what lets
    `comparable` mean something: two results are comparable when both followed
    the same estimator, and "the same" needs a version to be a claim rather than
    a hope. Derived rather than written into observables.json, because a
    generated field inside a hand-edited file goes stale silently -- the failure
    that check 25 exists to catch in the store's index. An older pin is read
    back the way the librarian reads an older kb_version: from the commit where
    that content stood.
    """
    p = CONTRACTS / "observables.json"
    return vocabulary_version_of(p.read_text()) if p.exists() else ""


def vocabulary_version_of(text: str) -> str:
    """The same derivation over a given copy, so a past version hashes alike."""
    try:
        body = json.loads(text).get("observables", [])
    except json.JSONDecodeError:
        return ""
    blob = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "obs-" + hashlib.sha256(blob.encode()).hexdigest()[:12]


def load_observables() -> dict[str, dict]:
    p = CONTRACTS / "observables.json"
    if not p.exists():
        return {}
    return {o["id"]: o for o in json.loads(p.read_text()).get("observables", []) if "id" in o}


def produced_id(item: object) -> str | None:
    """The observable id in a `produces` entry, plain or composite.

    A table may declare a name outright or as {"id": ..., "requires_composition":
    [...]} when the production needs a perturbation overlaid (4.5.3). One
    normalisation with two readers: check 38, which holds the table against the
    vocabulary, and answerability below. They were separate once, and the
    composite form read as a dict here -- so an observable the instrument
    declares it can produce derived as "cannot".
    """
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return item.get("id")
    return None


def produced_ids(conf: dict) -> list[str]:
    return [i for i in (produced_id(x) for x in conf.get("produces") or []) if i]


WIRE = {
    "ask_simulation": ("experiment_to_simulation", "microscope_agent", "simulation_agent"),
    "ask_experiment": ("simulation_to_experiment", "simulation_agent", "microscope_agent"),
}
SIDE_OF_AGENT = {"microscope_agent": "experiment", "simulation_agent": "simulation"}


def derive_producible(cap: dict, observable: str, vocab: dict[str, dict]) -> tuple[str, list[str]]:
    """What the tables say, not what the envelope claims (4.4 rule 3).

    The same move as check 21 makes on grades: the verdict is derived from the
    declaration, so a card cannot claim more than its source supports. Three
    outcomes, because "nobody has declared it" is not "it cannot be done":

      yes         a configuration of the receiving side produces it
      no          the vocabulary says that side cannot, or the table is
                  populated and none of its configurations produces it
      undeclared  nobody has named the observable, or the table is a skeleton
                  or provisional and silent on it

    A name the vocabulary does not define resolves to undeclared and never to
    no. The round still fails -- on the vocabulary, which is the true statement
    -- but "nobody has named this" must not be reported as "that side cannot
    produce it", and a populated table used to turn one into the other.

    A composite declaration counts as production. What the overlay requires
    stays in the table, where whoever plans the configuration reads it; the
    envelope names the configurations and does not restate the requirement,
    because one fact in two places is two facts by next week (P3).
    """
    entry = vocab.get(observable)
    if entry is None:
        return "undeclared", []
    side = SIDE_OF_AGENT.get(cap.get("agent", ""), "")
    if side and side not in entry.get("producible_by", []):
        return "no", []
    producers = [conf.get("config") for conf in cap.get("configurations", [])
                 if observable in produced_ids(conf)]
    if producers:
        return "yes", [p for p in producers if p]
    if cap.get("status") == "populated":
        return "no", []
    return "undeclared", []


def check_08_bridge(b: Bundle) -> list[Finding]:
    """The wire (4.4). Every rule here is a way of not authoring.

    The bridge moves a card and says what the gates said about it. Each gate has
    three outcomes rather than two, and the third is the one that matters: a gate
    that failed belongs in a refusal card, and a gate that could not be resolved
    belongs in a held round whose turn is a person's. Collapsing those two makes
    the bridge record an impossibility nobody established.
    """
    asks = b.of_kind("ask_simulation", "ask_experiment")
    ledgers = b.of_artifact("round_hashes")
    statuses = b.of_artifact("thread_status")
    if not (asks or ledgers or statuses):
        return [Finding(8, NA, "no bridge threads")]

    out: list[Finding] = []
    # Answerability reads the vocabulary and a capabilities table together. That
    # a table may not claim a name the vocabulary does not define is check 38's
    # rule, over every table and whether or not a round exists; what belongs
    # here is narrower -- the observable this round asks for.
    vocab = load_observables()

    # An envelope in an inbox is a *delivery* of a round, not a round. The
    # round lives in bridge/threads/, and the thread-level rules below --
    # duplicate blocking, the ledger, the turn -- count rounds. Counting the
    # delivered copy as a second round made rule 5 refuse the first real
    # delivery for asking what its own original asked.
    delivered = [c for c in asks if "/inbox/" in c.rel]
    rounds = [c for c in asks if "/inbox/" not in c.rel]
    by_round = {(str(c.data.get("thread")), c.data.get("round")): c for c in rounds}
    for c in delivered:
        key = (str(c.data.get("thread")), c.data.get("round"))
        source = by_round.get(key)
        if source is None:
            out.append(Finding(8, FAIL, f"delivered as {key[0]} round {key[1]}, which is not a round in "
                                        f"bridge/threads/. A delivery carries a round; it does not open one "
                                        f"(4.4)", c.rel))
        elif canon_sha(c.data) != canon_sha(source.data):
            out.append(Finding(8, FAIL, f"the delivered envelope differs from {source.rel}. A delivery is the "
                                        f"round, byte for byte in canonical form -- otherwise the receiving "
                                        f"side acts on something the thread does not record (4.4 rule 1)", c.rel))

    by_thread: dict[str, list[Card]] = {}
    for c in rounds:
        by_thread.setdefault(str(c.data.get("thread")), []).append(c)

    for c in asks:
        expect_dir, sender, receiver = WIRE[c.kind]
        payload = c.data.get("payload_card") or {}

        expect = canon_sha(payload)
        if c.data.get("payload_hash") != expect:
            out.append(Finding(8, FAIL, f"payload_hash does not match payload_card: expected {expect} (4.4 rule 4)", c.rel))

        if c.data.get("author") != "bridge":
            out.append(Finding(8, FAIL, f"author is {c.data.get('author')!r}; an envelope is the bridge's and nobody else's (4.4)", c.rel))
        for fld in ("numbers", "assumptions", "kb_refs"):
            if c.data.get(fld):
                out.append(Finding(8, FAIL, f"{fld} is not empty: the bridge carries, it does not author. The payload's numbers keep their own sources and grades (4.4, 5.3)", c.rel))
        if payload.get("card") not in ("plan", "result"):
            out.append(Finding(8, FAIL, f"payload is a {payload.get('card')!r} card; a plan and a result cross, nothing else does (4.4)", c.rel))
        if payload.get("qid") != c.data.get("qid"):
            out.append(Finding(8, FAIL, f"envelope qid {c.data.get('qid')!r} is not the payload's {payload.get('qid')!r}; the envelope belongs to the question it carries (5.2)", c.rel))
        if c.data.get("direction") != expect_dir:
            out.append(Finding(8, FAIL, f"an {c.kind} card carries direction {c.data.get('direction')!r}, not {expect_dir!r}", c.rel))
        if payload.get("author") != sender:
            out.append(Finding(8, FAIL, f"an {c.kind} card carries a card {sender} wrote; this one is {payload.get('author')!r}'s (4.4)", c.rel))

        ans = c.data.get("answerability") or {}
        obs = str(ans.get("observable", ""))
        claimed = ans.get("producible")
        capfile = CONTRACTS / "capabilities" / str(ans.get("checked_against", ""))
        if not capfile.exists():
            out.append(Finding(8, FAIL, f"answerability cites {ans.get('checked_against')!r}, which does not exist", c.rel))
        else:
            cap = json.loads(capfile.read_text())
            if cap.get("agent") != receiver:
                out.append(Finding(8, FAIL, f"answerability was checked against {cap.get('agent')!r}, which is not the receiving side ({receiver})", c.rel))
            derived, producers = derive_producible(cap, obs, vocab)
            if claimed == "no":
                out.append(Finding(8, FAIL, f"the envelope carries a refused gate: it says {receiver} cannot produce {obs!r}. A gate that says no belongs in a refusal card with counterexample numbers, and then the round is never spent (4.4 rule 3)", c.rel))
            elif claimed != derived:
                out.append(Finding(8, FAIL, f"answerability claims {claimed!r} for {obs!r}; {capfile.name} and the vocabulary give {derived!r}. The verdict is derived, never declared (4.4 rule 3)", c.rel))
            elif claimed == "yes" and sorted(ans.get("producing_configs") or []) != sorted(producers):
                out.append(Finding(8, FAIL, f"producing_configs is {sorted(ans.get('producing_configs') or [])} and {capfile.name} lists {sorted(producers)}", c.rel))
            if obs and vocab and obs not in vocab:
                out.append(Finding(8, FAIL, f"the round asks for {obs!r}, which contracts/observables.json does not define", c.rel))

        dropped = sorted(set(payload.get("degraded") or []) - set(c.data.get("degraded") or []))
        if dropped:
            out.append(Finding(8, FAIL, f"the payload was made without {dropped} and the envelope does not say so; "
                                        f"a plan built in reduced mode must not read as normal on the other side "
                                        f"(3.1 rule 2)", c.rel))

        if c.data.get("trigger") == "plan_completion":
            if payload.get("card") != "plan":
                out.append(Finding(8, FAIL, f"trigger is plan_completion and the payload is a {payload.get('card')!r}; "
                                            f"what completed was not a plan. A finished run does not open a round -- "
                                            f"a person does (4.4)", c.rel))
            elif payload.get("status") == "DRAFT":
                out.append(Finding(8, FAIL, "trigger is plan_completion and the payload plan is still DRAFT; a plan "
                                            "that has not passed the validator has completed nothing (5.5)", c.rel))

        uc = c.data.get("unit_consistency") or {}
        verdict, against = uc.get("verdict"), uc.get("compared_against")
        rnd = c.data.get("round") or 0
        if verdict == "inconsistent":
            out.append(Finding(8, FAIL, "the unit check failed, so this is a refusal card and not an envelope: reason_code unit_mapping_ambiguous, and a person defines the mapping (4.4 failure table)", c.rel))
        elif verdict == "no_counterpart" and rnd > 1:
            out.append(Finding(8, FAIL, f"round {rnd} has a counterpart, so no_counterpart is a comparison that was not made (4.4 rule 2)", c.rel))
        elif verdict == "no_counterpart" and against is not None:
            out.append(Finding(8, FAIL, f"no_counterpart names {against!r} as the counterpart", c.rel))
        elif verdict == "consistent" and not against:
            out.append(Finding(8, FAIL, "consistent against nothing: compared_against must name the counterpart card (4.4 rule 2)", c.rel))

    for thread, cards in sorted(by_thread.items()):
        seen: dict[tuple, int] = {}
        for c in sorted(cards, key=lambda x: x.data.get("round") or 0):
            key = (c.data.get("direction"), (c.data.get("answerability") or {}).get("observable"))
            if key in seen:
                out.append(Finding(8, FAIL, f"round {c.data.get('round')} asks {key[1]!r} in the same direction as round {seen[key]}; a repeat is a knowledge reference recorded in status.json, not another round (4.4 rule 5)", c.rel))
            else:
                seen[key] = c.data.get("round") or 0
        delivered = [c for c in cards if c.data.get("status") == "VALIDATED"]
        if delivered and not any(str(s.data.get("thread")) == thread for s in statuses):
            out.append(Finding(8, FAIL, f"thread {thread} has a delivered envelope and no thread ledger; without one line saying whose turn it is, four windows are four windows nobody follows (6.2)", delivered[0].rel))

    # A thread owns its directory, so the two names have to agree. Without this
    # the (thread, round) key is global with nothing keeping it unique, and a
    # thread that borrows another's id collides with it from across the
    # repository -- which is how the example thread and the first real one met.
    for c in asks + ledgers + statuses:
        parts = c.rel.split("/")
        if len(parts) > 3 and parts[0] == "bridge" and parts[1] == "threads":
            if parts[2] != str(c.data.get("thread")):
                out.append(Finding(8, FAIL, f"this sits in threads/{parts[2]}/ and says thread "
                                            f"{c.data.get('thread')!r}; a thread owns its directory (7.1)", c.rel))

    ledger_of: dict[tuple, Card] = {}
    for h in ledgers:
        key = (str(h.data.get("thread")), h.data.get("round"))
        if key in ledger_of:
            out.append(Finding(8, FAIL, f"two ledgers for {key[0]} round {key[1]}", h.rel))
        ledger_of[key] = h
    verified = 0
    for c in asks:
        if c.data.get("status") != "VALIDATED":
            continue
        key = (str(c.data.get("thread")), c.data.get("round"))
        h = ledger_of.get(key)
        if h is None:
            out.append(Finding(8, FAIL, f"no r{key[1]}_hashes.json for this round: the envelope's own hash proves only that it agrees with itself (4.4 rule 4)", c.rel))
            continue
        payload = c.data.get("payload_card") or {}
        src = h.data.get("source") or {}
        if h.data.get("payload_sha256") != c.data.get("payload_hash"):
            out.append(Finding(8, FAIL, "the ledger's payload_sha256 is not the envelope's payload_hash", h.rel))
        if h.data.get("ask_card") != c.path.name:
            out.append(Finding(8, FAIL, f"the ledger covers {h.data.get('ask_card')!r} and this envelope is {c.path.name}", h.rel))
        if src.get("status") != payload.get("status"):
            out.append(Finding(8, FAIL, f"the ledger records the source at {src.get('status')!r} and the payload "
                                        f"says {payload.get('status')!r}. The hash leaves status out so a legitimate "
                                        f"transition does not read as tampering (5.5), so the status is pinned here "
                                        f"instead -- otherwise the bridge could advance it and nothing would see", h.rel))
        if src.get("card_id") != payload.get("id") or src.get("revision") != payload.get("revision"):
            out.append(Finding(8, FAIL, f"the ledger records {src.get('card_id')!r} revision {src.get('revision')} and the payload is {payload.get('id')!r} revision {payload.get('revision')}", h.rel))
        if src.get("path") is None:
            # Nothing on disk to recompute from, so the ledger's record of the
            # source must at least agree with the payload it wrapped -- in the
            # same hash, which leaves status out; the status is pinned above.
            if src.get("sha256") != card_sha(payload):
                out.append(Finding(8, FAIL, "a hand-fed card has no path to recompute from, so the recorded source hash must be the payload's", h.rel))
            continue
        f = REPO / str(src.get("path"))
        if not f.exists():
            out.append(Finding(8, FAIL, f"the source card {src.get('path')!r} is not on disk, so the transport cannot be recomputed. A hash nobody can recompute is not integrity (4.4 rule 4)", h.rel))
            continue
        try:
            on_disk = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            out.append(Finding(8, FAIL, f"the source card cannot be read: {exc}", h.rel))
            continue
        if on_disk.get("revision") != src.get("revision"):
            # The source moved on. Skipping the comparison is right -- the
            # ledger recorded a revision that no longer exists, and failing it
            # would refuse the one legitimate way out of a pin (5.3.1). Saying
            # so is not optional: until 2026-09-19 this branch was a bare
            # `continue` under a comment claiming it said so, which is the
            # defect this repository spent the day counting -- prose promising
            # a guard the code does not provide. A superseded round is
            # invisible otherwise, and the envelope already delivered to the
            # receiving side still describes the old revision.
            out.append(Finding(8, PENDING, f"{src.get('path')} is now revision {on_disk.get('revision')} and "
                                           f"this ledger records revision {src.get('revision')}, so the "
                                           f"transport cannot be recomputed. The round is superseded rather "
                                           f"than broken; what was delivered still describes the old "
                                           f"revision", h.rel))
            continue
        if card_sha(on_disk) != src.get("sha256"):
            out.append(Finding(8, FAIL, f"{src.get('path')} at revision {src.get('revision')} no longer "
                                        f"hashes to what this ledger recorded: either it was edited without "
                                        f"a revision bump, or the payload is not what was sent. Stop the "
                                        f"round; do not repair it (4.4 failure table). The finding is on the "
                                        f"ledger and the cause is in that card's tree, so naming it is "
                                        f"routing and not repair", h.rel))
        else:
            verified += 1

    pairs_seen: dict[str, dict[tuple, set]] = {}
    for r in b.of_kind("refusal"):
        thread = str(r.data.get("thread"))
        if not thread.startswith("thr-"):
            continue
        for ce in r.data.get("counterexample", []) or []:
            key = (r.data.get("reason_code"), ce.get("parameter"))
            pairs_seen.setdefault(thread, {}).setdefault(key, set()).add(r.data.get("round") or 0)

    for s in statuses:
        thread = str(s.data.get("thread"))
        state, turn = s.data.get("state"), s.data.get("turn")
        if state == "open" and turn == "human":
            out.append(Finding(8, FAIL, "the state is open but the turn is a person's; open means an agent owes the next card (4.4 rule 4)", s.rel))
        if state in ("held", "escalated", "closed") and turn != "human":
            out.append(Finding(8, FAIL, f"the state is {state} and the turn is {turn!r}; only a person moves a thread out of {state} (4.4)", s.rel))
        if state == "held" and not s.data.get("open_question"):
            out.append(Finding(8, FAIL, "a held round must name what a person has to answer (4.4 failure table)", s.rel))
        rounds = [c.data.get("round") or 0 for c in by_thread.get(thread, [])]
        if rounds and (s.data.get("round") or 0) < max(rounds):
            out.append(Finding(8, FAIL, f"the ledger says round {s.data.get('round')} and there is an envelope for round {max(rounds)}", s.rel))

        recorded = {(p.get("reason_code"), p.get("parameter")): set(p.get("rounds") or [])
                    for p in s.data.get("blocked_pairs") or []}
        repeated = {k: v for k, v in recorded.items() if len(v) >= 2}
        if repeated and state != "escalated":
            k, v = sorted(repeated.items())[0]
            out.append(Finding(8, FAIL, f"({k[0]}, {k[1]}) came back in rounds {sorted(v)}, so this thread owes a person and no further round opens (4.4 rule 6)", s.rel))
        if repeated:
            ceiling = max(r for v in repeated.values() for r in v)
            for c in by_thread.get(thread, []):
                if (c.data.get("round") or 0) > ceiling:
                    out.append(Finding(8, FAIL, f"round {c.data.get('round')} was opened after the repetition in round {ceiling} called the human (4.4 rule 6)", c.rel))
        for k, v in sorted(pairs_seen.get(thread, {}).items()):
            if len(v) >= 2 and len(recorded.get(k, set())) < 2:
                out.append(Finding(8, FAIL, f"({k[0]}, {k[1]}) was refused in rounds {sorted(v)} and the ledger does not record the repeat; a repetition nobody records is a round cap nobody enforces (4.4 rule 6)", s.rel))
        for sub in s.data.get("substitutions") or []:
            key = (sub.get("direction"), sub.get("observable"))
            if not any((c.data.get("direction"), (c.data.get("answerability") or {}).get("observable")) == key
                       for c in by_thread.get(thread, [])):
                out.append(Finding(8, FAIL, f"a substitution for {sub.get('observable')!r} that never crossed in this thread; rule 5 replaces a repeat, not a first ask (4.4 rule 5)", s.rel))

    if not any(f.status == FAIL for f in out):
        out.insert(0, Finding(8, PASS, f"{len(asks)} bridge rounds carry their cards unchanged; {verified} of them recompute against the source on disk"))
    return out


def check_09_md_vs_json(b: Bundle) -> list[Finding]:
    out: list[Finding] = []
    pairs = 0
    # "1" is dropped from the scan: in prose it is a digit, not a unit, and
    # keeping it makes an identifier like mic-20260917-001 parse as a quantity.
    unit_alt = sorted((u for u in UNITS["units"] if u != "1"), key=len, reverse=True)
    unit_re = "|".join(re.escape(u) for u in unit_alt)
    pattern = re.compile(
        r"(?<![A-Za-z0-9_.-])([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)[ \t]*(" + unit_re + r")(?![A-Za-z0-9_])"
    )
    for c in b.cards:
        if "__unreadable__" in c.data:
            continue
        md = c.path.with_suffix(".md")
        if not md.exists():
            continue
        pairs += 1
        known = {(round(float(n["value"]), 12), n["unit"]) for n in c.data.get("numbers", [])}
        text = md.read_text()

        # The same rule for the two identifiers a reader would act on. Numbers
        # were covered and prose was not, so the example round named a thread
        # that existed nowhere in the repository for a day -- in the file a
        # bridge seat copies when writing its first round, and one did. This is
        # not an attempt to check prose: it is one token, held to the card the
        # way a number is (5.6).
        for field, id_rx in (("thread", r"\bthr-[a-z0-9-]+"), ("qid", r"\b(?:mic|sim)-[0-9]{8}-[0-9]{3}\b")):
            want = c.data.get(field)
            if not want:
                continue
            for found in sorted(set(re.findall(id_rx, text))):
                if found != want:
                    out.append(Finding(9, FAIL, f"{md.name} names {field} {found!r} and the card is {want!r} "
                                                f"(JSON is authoritative, P3)", c.rel))
        for m in pattern.finditer(text):
            val, unit = float(m.group(1)), m.group(2)
            if not any(u == unit and (v == round(val, 12) or (v != 0 and abs(v - val) / abs(v) < 1e-9)) for v, u in known):
                out.append(Finding(9, FAIL, f"{md.name} states {m.group(0)!r}, which is not in the card's numbers[] (JSON is authoritative, P3)", c.rel))
    if not pairs:
        return [Finding(9, NA, "no json/md card pairs")]
    return out or [Finding(9, PASS, f"{pairs} markdown files agree with their json")]


def check_10_degraded(b: Bundle) -> list[Finding]:
    plans = {c.data.get("id"): c for c in b.of_kind("plan")}
    results = b.of_kind("result")
    if not results:
        return [Finding(10, NA, "no result cards")]
    out: list[Finding] = []
    for r in results:
        p = plans.get(r.data.get("plan_id"))
        if p is None:
            out.append(Finding(10, PENDING, f"plan {r.data.get('plan_id')!r} not in this run", r.rel))
            continue
        missing = set(p.data.get("degraded", [])) - set(r.data.get("degraded", []))
        if missing:
            out.append(Finding(10, FAIL, f"plan was degraded on {sorted(missing)} but the result does not say so (3.1 rule 2)", r.rel))
    return out or [Finding(10, PASS, f"{len(results)} results carry their plan's degraded list")]


def check_11_axis_independence(b: Bundle) -> list[Finding]:
    axes = b.of_kind("axis")
    if not axes:
        return [Finding(11, NA, "no axis cards")]
    out: list[Finding] = []
    # Siblings are the cards of one fan-out: same directory, same qid, same
    # revision. Pairing across revisions reported every card of a re-run as
    # reading its predecessor, because caller_id carries no revision (4.3.1)
    # and so the two are the same string. That is not a sibling read; it is the
    # same axis, asked again.
    def fanout(card) -> tuple:
        return (str(Path(card.rel).parent), card.data.get("qid"), card.data.get("revision"))

    for c in axes:
        blob = json.dumps(c.data, ensure_ascii=False)
        for other in axes:
            if other is c or fanout(other) != fanout(c):
                continue
            for token in (other.path.name, other.data.get("id"), other.data.get("caller_id")):
                if token and token in blob:
                    out.append(Finding(11, FAIL, f"references sibling {token!r}; S3 siblings may not read each other (4.5.2)", c.rel))
    return out or [Finding(11, PASS, f"{len(axes)} axis cards reference no sibling")]


# In an agent directory one question owns one flat folder, so the names are
# goal.json and synthesis.json. contracts/examples/ holds several questions side
# by side, so a suffix is allowed here too.
# `artifact_name` prefixes a later revision's file with `v<N>_`, and an origin
# has to be able to name one. Without this the goal is the only artifact that
# cannot be revisioned, two revisions' cards point at one goal.json, and one of
# them is necessarily wrong -- which is what 46 check 12 failures were.
ORIGIN_RE = re.compile(r"^(?:v[0-9]+_)?(axis_[a-z0-9_]+\.json|goal[a-z0-9_]*\.json|synthesis[a-z0-9_]*\.json|plan_[a-z0-9_.-]+\.json)#[a-z][a-z0-9_]*$")


def check_12_synthesis_closure(b: Bundle) -> list[Finding]:
    """S4 introduces no ungrounded number, and a carried number still matches
    the card it was carried from.

    Transport is verified by comparison with the source card, not by re-deriving
    the formula: a value already checked where it was produced does not become
    more true by being recomputed somewhere with fewer inputs.
    """
    out: list[Finding] = []
    syn = b.of_kind("synthesis")
    carried = 0
    for c in b.cards:
        if "__unreadable__" in c.data:
            continue
        for n in c.data.get("numbers", []):
            origin = n.get("origin")
            if c.kind == "synthesis" and not origin and not str(n.get("source", "")).startswith("computed:"):
                out.append(Finding(12, FAIL, f"{n.get('name')} has no origin; S4 may not introduce new numbers (4.5.4)", c.rel))
                continue
            if not origin:
                continue
            carried += 1
            if not ORIGIN_RE.match(str(origin)):
                out.append(Finding(12, FAIL, f"{n.get('name')} origin {origin!r} does not point at a card number", c.rel))
                continue
            fname, sname = str(origin).split("#", 1)
            src_card = next((x for x in b.cards if x.path.name == fname and x.data.get("qid") == c.data.get("qid")), None)
            if src_card is None:
                out.append(Finding(12, PENDING, f"{n.get('name')} cites {origin} but {fname} is not in this run", c.rel))
                continue
            src_num = src_card.numbers().get(sname)
            if src_num is None:
                out.append(Finding(12, FAIL, f"{n.get('name')} cites {origin} but {fname} has no number {sname!r}", c.rel))
                continue
            for field_name in ("value", "unit", "grade", "formula", "symbol"):
                if field_name in ("formula", "symbol") and field_name not in n:
                    continue
                if n.get(field_name) != src_num.get(field_name):
                    out.append(Finding(12, FAIL, f"{n.get('name')} carries {field_name} {n.get(field_name)!r} but {origin} has {src_num.get(field_name)!r}", c.rel))
    if not any(f.status == FAIL for f in out):
        out.insert(0, Finding(12, PASS, f"{len(syn)} synthesis cards are closed; {carried} carried numbers match their source"))
    return out


ALLOWED_PATHS = [
    r"^(plan\.md|CLAUDE\.md|ARCHITECT\.md|README\.md|\.gitignore|\.mcp\.json|pyproject\.toml|uv\.lock)$",
    r"^contracts/(units\.md|units\.json|observables\.json|quantities\.json|seats\.json|validate\.py|validation_limits\.json|history_fixtures\.py)$",
    r"^contracts/schemas/[A-Za-z0-9_.-]+\.json$",
    r"^contracts/hooks/[a-z-]+$",
    r"^contracts/capabilities/[A-Za-z0-9_.-]+\.json$",
    r"^contracts/examples/(rejected/)?[A-Za-z0-9_.-]+\.(json|md|jsonl)$",
    r"^contracts/examples/rejected/check[0-9]{2}_[a-z0-9_]+/[A-Za-z0-9_.-]+\.(json|md|jsonl)$",
    r"^microscope_agent/tasks/[A-Za-z0-9_.-]+$",
    r"^simulation_agent/tasks/[A-Za-z0-9_.-]+$",
    r"^(microscope|simulation)_agent/CLAUDE\.md$",
    # Declared names per agent, not any filename. This read
    # `envelope/[A-Za-z0-9_.-]+` until 2026-09-20, which accepted anything --
    # so section 7's envelope lines described a tree rather than binding one,
    # and simulation_agent/envelope/safety.json lived there for a day while
    # section 7 said it was not in that tree. The two agents differ on purpose
    # (7): the microscope holds a safety policy the person confirms, and the
    # simulation holds a budget nobody needs to measure, because a disk quota
    # is not a laser.
    r"^microscope_agent/envelope/(safety|snapshot)\.json$",
    r"^simulation_agent/envelope/(budget|snapshot)\.json$",
    r"^(microscope|simulation)_agent/approvals/[A-Za-z0-9_.-]+$",
    r"^(microscope|simulation)_agent/inbox/[a-z0-9-]+/[A-Za-z0-9_.-]+$",
    r"^(microscope|simulation)_agent/questions/[a-z0-9-]+/[A-Za-z0-9_.-]+$",
    r"^(microscope|simulation)_agent/runs/[a-z0-9-]+/([A-Za-z0-9_.-]+|raw/.*)$",
    r"^(microscope|simulation)_agent/src/([A-Za-z0-9_.-]+|devices/[A-Za-z0-9_.-]+)$",
    r"^librarian_agent/CLAUDE\.md$",
    r"^((microscope|simulation|librarian)_agent|bridge)/failures\.jsonl$",
    # 7.1 rule 9. Beside failures.jsonl and deliberately the same idiom -- a
    # seat-level append-only ledger -- for a different thing: what was
    # abandoned, against what was ruled. 9.3 criterion 2 counts the drops,
    # and a drop produces no other artefact, so until this path existed the
    # count of them was 0 for want of anywhere to write one.
    r"^((microscope|simulation|librarian)_agent|bridge)/rulings\.jsonl$",
    r"^librarian_agent/kb/(index\.json|(sources|distilled|entries|lessons|staging|exports)/[A-Za-z0-9_.-]+)$",
    r"^librarian_agent/queries/[A-Za-z0-9_.-]+$",
    r"^librarian_agent/tasks/[A-Za-z0-9_.-]+$",
    r"^bridge/tasks/[A-Za-z0-9_.-]+$",
    r"^librarian_agent/src/[A-Za-z0-9_.-]+$",
    r"^(microscope|simulation|librarian)_agent/README\.md$",
    r"^bridge/README\.md$",
    r"^bridge/CLAUDE\.md$",
    r"^bridge/failures\.jsonl$",
    r"^bridge/threads/[a-z0-9-]+/[A-Za-z0-9_.-]+$",
    r"^(microscope|simulation|librarian)_agent/\.claude/.*$",
    r"^bridge/\.claude/.*$",
    r"^\.claude/.*$",
    # The public page (7). It is outside every agent and outside contracts/,
    # so nothing about it is shared code: it is the repository's own front
    # door, a sibling of README.md, and it classifies as `design` below.
    r"^docs/[A-Za-z0-9_.-]+\.(html|css|js|svg|png|jpg|jpeg|webp|mp4|md)$",
    r"^docs/assets/[A-Za-z0-9_.-]+$",
]


def check_13_paths(b: Bundle) -> list[Finding]:
    out: list[Finding] = []
    n = 0
    for p in b.all_files:
        try:
            rel = str(p.relative_to(REPO))
        except ValueError:
            continue
        if p.name == ".DS_Store":
            continue
        n += 1
        if not any(re.match(rx, rel) for rx in ALLOWED_PATHS):
            out.append(Finding(13, FAIL,
                                f"path is declared in neither {DESIGN_DOC_NAME} section 7 nor ALLOWED_PATHS in this "
                                "file, and it needs BOTH -- section 7 is the prose of record and "
                                "ALLOWED_PATHS is what refuses. They are separate and nothing compares "
                                "them (11-11). This message named only section 7 until 2026-09-19, and "
                                "both a manager and the architecture seat edited section 7 alone and "
                                "watched the check keep failing (7.1 rule 7)", rel))
            continue
        parts = rel.split("/")
        if parts[0].endswith("_agent") or parts[0] == "bridge":
            if "raw" not in parts and len(parts) > 4:
                out.append(Finding(13, FAIL, f"depth {len(parts) - 1} exceeds the limit of 3 inside an agent (7.1 rule 6)", rel))

    # A round or a revision is a filename prefix (7.1 rule 3), and the prefix has
    # to agree with the card. This reads every card and ledger rather than the
    # envelopes alone: while it lived in check 8 it bit only the files whose
    # writer had already chosen the prefix form, so whoever wrote r1_refusal.json
    # was checked and whoever wrote refusal_r1.json was not. A rule enforced only
    # where it is convenient is P4 in reverse.
    prefixed = 0
    for c in b.cards + b.artifacts:
        m = re.match(r"^([rv])(\d+)_", c.path.name)
        if m is None or "__unreadable__" in c.data:
            continue
        # Two prefixes because they are two things (7.1 rule 3). While one
        # sentence covered both, this read r<N>_ as a round and a revision-2
        # plan named r2_ failed against its round of 0 -- 4.5.5 could not be
        # followed. The field each prefix answers to is the whole difference.
        field = "round" if m.group(1) == "r" else "revision"
        prefixed += 1
        if int(m.group(2)) != c.data.get(field):
            out.append(Finding(13, FAIL, f"the filename says {field} {int(m.group(2))} and the card says "
                                         f"{c.data.get(field)} (7.1 rule 3)", c.rel))
    return out or [Finding(13, PASS, f"{n} files sit in declared paths, {prefixed} of them naming their round or revision")]


def check_14_command_provenance(b: Bundle) -> list[Finding]:
    logs = list(REPO.glob("*_agent/runs/*/log.json"))
    if not logs:
        return [Finding(14, PENDING, "needs runs/<run_id>/log.json, which M1 produces")]
    return [Finding(14, PENDING, "log provenance not implemented yet")]


def check_15_approval_precedes_run(b: Bundle) -> list[Finding]:
    """6.1: a run above Tier 1 stands on a person's approval, and that approval
    exists BEFORE it. A Tier 0-1 run needs none and says so with a null id --
    which is why the null case is checked as hard as the other one: it is a
    claim about the plan's tier, and the plan is on disk to contradict it.
    """
    runs = [d for d in REPO.glob("*_agent/runs/*") if d.is_dir()]
    if not runs:
        return [Finding(15, NA, "no runs on disk")]
    plans = {str(c.data.get("id")): c for c in b.of_kind("plan")}
    approvals = {str(c.data.get("plan_id") or c.rel): c for c in b.of_kind("plan_approval")}
    scopes = b.of_kind("scope_approval")
    out: list[Finding] = []
    checked = 0
    for d in sorted(runs):
        rel = str(d.relative_to(REPO))
        log_path = d / "log.json"
        if not log_path.exists():
            out.append(Finding(15, FAIL, "run directory with no log.json, so nothing records what it stood on (4.6)", rel))
            continue
        try:
            log = json.loads(log_path.read_text())
        except Exception as exc:
            out.append(Finding(15, FAIL, f"unreadable run log: {exc}", rel))
            continue
        checked += 1
        appr = log.get("approval") or {}
        aid, t0 = appr.get("id"), str(log.get("t0_wall") or "")
        plan = plans.get(str(log.get("plan_id") or ""))
        if plan is None:
            out.append(Finding(15, PENDING, f"plan {log.get('plan_id')!r} is not in this run, so the tier it claims cannot be read", rel))
            continue
        tiers = [a.get("tier") for a in (plan.data.get("actions") or []) if isinstance(a.get("tier"), int)]
        top = max(tiers) if tiers else None
        if aid is None:
            if top is None:
                out.append(Finding(15, FAIL, f"null approval, but {plan.data.get('id')} declares no action tier to justify it (6.1)", rel))
            elif top >= 2:
                out.append(Finding(15, FAIL, f"null approval on a plan whose top action tier is {top}; Tier 2 takes a person and nothing in an agent may write one (6.1)", rel))
            else:
                out.append(Finding(15, PASS, f"Tier {top} run, no approval needed and the null says so rather than omitting it", rel))
            continue
        card = approvals.get(str(log.get("plan_id") or ""))
        if card is not None:
            a = card.data
            if str(a.get("plan_revision")) != str(log.get("revision")):
                out.append(Finding(15, FAIL, f"approval is for revision {a.get('plan_revision')} and the run carried revision {log.get('revision')}", rel))
            elif a.get("plan_hash") != plan.data.get("plan_hash", a.get("plan_hash")):
                out.append(Finding(15, FAIL, "approval names a different plan hash than the plan it approves", rel))
            elif t0 and str(a.get("approved_at") or "") > t0:
                out.append(Finding(15, FAIL, f"approval {aid} is dated {a.get('approved_at')}, after the run started at {t0}; an approval that follows its run approved nothing", rel))
            else:
                out.append(Finding(15, PASS, f"run stands on {aid}, granted before it started", rel))
            continue
        live = [s for s in scopes if str(s.data.get("id") or "") == str(aid)]
        if not live:
            out.append(Finding(15, FAIL, f"run names approval {aid!r} and no plan_approval or scope_approval with that id is on disk", rel))
            continue
        s = live[0].data
        if s.get("voided"):
            out.append(Finding(15, FAIL, f"scope approval {aid} is voided", rel))
        elif t0 and str(s.get("valid_until") or "") < t0:
            out.append(Finding(15, FAIL, f"scope approval {aid} expired {s.get('valid_until')} before the run at {t0}", rel))
        elif isinstance(s.get("runs_used"), int) and isinstance(s.get("max_runs"), int) and s["runs_used"] > s["max_runs"]:
            out.append(Finding(15, FAIL, f"scope approval {aid} is past its {s['max_runs']} runs", rel))
        else:
            out.append(Finding(15, PASS, f"run stands on live scope approval {aid}", rel))
    if checked and not out:
        return [Finding(15, PASS, f"{checked} runs, each preceded by what 6.1 requires of its tier")]
    return out


def check_16_dependency_direction(b: Bundle) -> list[Finding]:
    out: list[Finding] = []
    for f in CONTRACTS.glob("*.py"):
        bad = [m for m in re.findall(r"^\s*(?:from|import)\s+([A-Za-z0-9_.]+)", f.read_text(), re.M)
               if m.split(".")[0] in {"microscope_agent", "simulation_agent", "librarian_agent", "bridge"}]
        if bad:
            out.append(Finding(16, FAIL, f"contracts imports {bad}; contracts must import nothing (7.2 rule 1)", str(f.relative_to(REPO))))
    src = list(REPO.glob("*_agent/src/*.py")) + list(REPO.glob("*_agent/src/devices/*.py"))
    if not src:
        out.append(Finding(16, PASS, "contracts imports no agent (7.2 rule 1)"))
        out.append(Finding(16, PENDING, "the other four rules need agent code under src/, which M1 produces"))
        return out
    for f in src:
        rel = str(f.relative_to(REPO))
        text = f.read_text()
        imports = re.findall(r"^\s*(?:from|import)\s+([A-Za-z0-9_.]+)", text, re.M)
        is_device = "/devices/" in rel
        for mod in imports:
            if is_device and mod.startswith("devices"):
                out.append(Finding(16, FAIL, f"device module imports sibling {mod!r} (7.2 rule 5)", rel))
            if rel.endswith(("synthesis.py",)) or "/axis_" in rel:
                if "device" in mod or "orchestrator" in mod:
                    out.append(Finding(16, FAIL, f"planning code imports {mod!r}; it must not know about devices (7.2 rule 2)", rel))
    return out or [Finding(16, PASS, f"{len(src)} source files respect the dependency direction")]


def check_17_derived(b: Bundle) -> list[Finding]:
    out: list[Finding] = []
    n_computed = 0
    n_from_store = 0
    for c in b.cards:
        if "__unreadable__" in c.data:
            continue
        env, _ = card_env(c)
        nums = c.numbers()
        temp = next((float(n["value"]) for n in nums.values() if n.get("name") == "temperature" and n.get("unit") == "K"), None)
        for name, n in nums.items():
            src = str(n.get("source", ""))
            if not src.startswith("computed:"):
                if n.get("derived"):
                    out.append(Finding(17, FAIL, f"{name} is marked derived but its source is {src!r}; a named quantity is computed: (5.7)", c.rel))
                continue
            if n.get("origin"):
                continue                              # verified at its source by check 12
            n_computed += 1
            formula, inputs = n.get("formula"), n.get("inputs")
            if not formula or not inputs:
                out.append(Finding(17, FAIL, f"{name} is computed but has no formula/inputs", c.rel))
                continue
            # An input may name the store (5.3, ruled 2026-09-20): the second
            # case of the class that widened `basis`. The same three names are
            # legal in a KB entry's own `inputs` and were illegal here, and the
            # asymmetry pointed the wrong way -- the card is the artefact that
            # has to show its grounds to the gate, and it was the one that
            # could not name them. Resolution is check 54's, against kb_refs.
            from_store = [i for i in inputs if str(i).startswith("kb:")]
            missing = [i for i in inputs
                       if i not in env and i not in CONSTANTS and not str(i).startswith("kb:")]
            if missing:
                out.append(Finding(17, FAIL, f"{name} reads {missing}, which are neither numbers of "
                                             "this card nor kb: entries", c.rel))
                continue
            if from_store:
                # Resolved, not recomputed. The arithmetic needs each entry's
                # value AT THIS CARD'S PIN, and the index holds the current
                # store -- checking against today's value would be the error
                # check 58 exists to catch, one level down. So this says
                # plainly that it did not verify the number rather than
                # implying it did. Fetching pinned values is a separate check
                # and is raised rather than invented here.
                n_from_store += 1
                continue
            sub = {k: v for k, v in env.items() if k in inputs}
            try:
                value_si, dim = eval_formula(formula, sub)
            except FormulaError as exc:
                out.append(Finding(17, FAIL, f"{name}: {exc}", c.rel))
                continue
            f = si_factor(n.get("unit", ""), temp)
            d_declared = dim_of(n.get("unit", ""))
            if f is None or d_declared is None:
                continue
            if not dims_equal(dim, d_declared):
                out.append(Finding(17, FAIL, f"{name}: formula gives dimension {dim or '{}'} but the unit {n['unit']!r} is {d_declared or '{}'}", c.rel))
                continue
            declared_si = float(n["value"]) * f
            if declared_si == 0 and value_si == 0:
                continue
            # A value written as an order of magnitude is compared at that
            # precision. Demanding 2% of a one-digit number would make P15 and
            # this check contradict each other.
            om = n.get("precision") == "order_of_magnitude" or (
                c.data.get("intent", "explore") == "explore" and n.get("grade") in ("E4", "E5")
            )
            if om:
                digits = LIMITS["order_of_magnitude_sig_figs"]
                want = round_to_sig(value_si, digits)
                if want == 0 or abs(declared_si - want) / abs(want) > 1e-9:
                    out.append(Finding(17, FAIL, f"{name} states {n['value']} {n['unit']} but {formula} recomputes to {value_si / f:.6g}, which is {want / f:.6g} {n['unit']} at {digits} significant figure(s)", c.rel))
            else:
                tol = LIMITS["computed_value_tolerance_rel"]
                denom = abs(value_si) if value_si else abs(declared_si)
                if abs(declared_si - value_si) / denom > tol:
                    out.append(Finding(17, FAIL, f"{name} states {n['value']} {n['unit']} but {formula} recomputes to {value_si / f:.6g} {n['unit']}", c.rel))
    return out or [Finding(17, PASS, f"{n_computed - n_from_store} computed values recompute from their formulas; {n_from_store} rest on a kb: input and are resolved but not recomputed")]


def check_18_scope_range(b: Bundle) -> list[Finding]:
    scopes = b.of_kind("scope_approval")
    if not scopes:
        return [Finding(18, NA, "no scope_approval cards")]
    out: list[Finding] = []
    for c in scopes:
        if not c.data.get("valid_until"):
            out.append(Finding(18, FAIL, "scope_approval without valid_until", c.rel))
        if not c.data.get("max_runs"):
            out.append(Finding(18, FAIL, "scope_approval without max_runs", c.rel))
    envs = envelope_files()
    if not envs:
        out.append(Finding(18, PENDING, "subset-of-envelope test needs envelope/safety.json, which M1 produces"))
    return out


def check_19_scope_validity(b: Bundle) -> list[Finding]:
    scopes = b.of_kind("scope_approval")
    if not scopes:
        return [Finding(19, NA, "no scope_approval cards")]
    out: list[Finding] = []
    now = datetime.now(timezone.utc)
    for c in scopes:
        voided = c.data.get("voided")
        if voided:
            out.append(Finding(19, PASS, f"voided on {voided.get('reason')}; may not be used again", c.rel))
            continue
        try:
            until = datetime.fromisoformat(str(c.data["valid_until"]).replace("Z", "+00:00"))
        except (KeyError, ValueError):
            out.append(Finding(19, FAIL, "valid_until is not a parsable timestamp", c.rel))
            continue
        if until < now:
            out.append(Finding(19, FAIL, f"expired at {until.isoformat()} but is not marked voided", c.rel))
        if c.data.get("runs_used", 0) > c.data.get("max_runs", 0):
            out.append(Finding(19, FAIL, "runs_used exceeds max_runs but is not marked voided", c.rel))
    return out or [Finding(19, PASS, f"{len(scopes)} scope approvals are live and within their caps")]


def check_20_alternatives(b: Bundle) -> list[Finding]:
    plans = b.of_kind("plan")
    syn = {c.data.get("qid"): c for c in b.of_kind("synthesis")}
    if not plans:
        return [Finding(20, NA, "no plan cards")]
    out: list[Finding] = []
    for c in plans:
        s = syn.get(c.data.get("qid"))
        screened = len((s.data.get("configs_screened") or [])) if s else None
        rejected = c.data.get("alternatives_rejected") or []
        if screened is None:
            out.append(Finding(20, PENDING, "no synthesis card for this qid; screening count unknown", c.rel))
            continue
        if screened > 1 and not rejected:
            out.append(Finding(20, FAIL, f"{screened} configurations survived screening but alternatives_rejected is empty (S6)", c.rel))
        for r in rejected:
            if not r.get("grounds"):
                out.append(Finding(20, FAIL, f"rejection of {r.get('what')!r} has no numeric grounds", c.rel))
    return out or [Finding(20, PASS, "rejected configurations carry numeric grounds")]


def config_of_run(run_id: str, b: Bundle) -> str | None:
    """run_id -> the plan it carried out -> the configuration that plan names."""
    for log in REPO.glob(f"*_agent/runs/{run_id}/log.json"):
        try:
            plan_id = str(json.loads(log.read_text()).get("plan_id") or "")
        except Exception:
            return None
        for pc in b.of_kind("plan"):
            if str(pc.data.get("id")) == plan_id:
                sc = pc.data.get("system_configuration")
                return sc.get("config") if isinstance(sc, dict) else None
    return None


def number_roles(card) -> dict[str, set[str]]:
    """Which role each number is put to by the fields that name it (5.3).

    `values[]` is the card asserting something about the system; the comparison
    terms -- `criteria_evaluation[].observed_number`, `deviations[]`' two sides
    -- assert nothing beyond the run. A kind that branched on role would have to
    be chosen by the writer; the field already says it.
    """
    roles: dict[str, set[str]] = {}
    def mark(n, role):
        if isinstance(n, str) and n:
            roles.setdefault(n, set()).add(role)
    for v in card.data.get("values") or []:
        if isinstance(v, dict):
            mark(v.get("number"), "claim")
            mark(v.get("uncertainty"), "claim")
    for e in card.data.get("criteria_evaluation") or []:
        if isinstance(e, dict):
            mark(e.get("observed_number"), "reading")
    for d in card.data.get("deviations") or []:
        if isinstance(d, dict):
            mark(d.get("actual_number"), "reading")
            mark(d.get("planned_number"), "reading")
    return roles


def check_21_grade_derivation(b: Bundle) -> list[Finding]:
    out: list[Finding] = []
    n = 0
    # A result card names its plan and the plan names the configuration; that is
    # the only route from a `simulated:` number to the 5.3 declaration.
    plan_configs = {
        str(pc.data.get("id")): ((pc.data.get("system_configuration") or {}).get("config"))
        for pc in b.of_kind("plan")
        if isinstance(pc.data.get("system_configuration"), dict)
    }
    for c in b.cards:
        if "__unreadable__" in c.data:
            continue
        nums = c.numbers()
        kb_grades = {r.get("entry_id"): r.get("grade") for r in c.data.get("kb_refs", []) or []}
        for name, num in nums.items():
            n += 1
            if num.get("origin"):
                # A carried number keeps the grade it was given where it was
                # produced; check 12 compares it against that card.
                continue
            src = str(num.get("source", ""))
            if ":" not in src:
                continue
            prefix, ref = src.split(":", 1)
            declared = num.get("grade")
            expected = SOURCE_GRADE.get(prefix, "missing")
            if expected == "missing":
                out.append(Finding(21, FAIL, f"{name}: unknown source kind {prefix!r}", c.rel))
            elif expected is not None:
                if declared != expected:
                    out.append(Finding(21, FAIL, f"{name}: source {prefix}: derives grade {expected}, card says {declared} (self-reported grades fail)", c.rel))
            elif prefix == "kb":
                if ref not in kb_grades:
                    out.append(Finding(21, FAIL, f"{name}: kb source {ref!r} has no matching kb_refs entry to inherit a grade from", c.rel))
                elif declared != kb_grades[ref]:
                    out.append(Finding(21, FAIL, f"{name}: kb entry {ref} was returned as {kb_grades[ref]}, card claims {declared}", c.rel))
                elif KB_INDEX is not None:
                    stored = (KB_INDEX.get("entries") or {}).get(ref)
                    if stored is None:
                        out.append(Finding(21, FAIL, f"{name}: kb entry {ref!r} is not in the store", c.rel))
                    elif stored.get("grade") != declared:
                        out.append(Finding(21, FAIL, f"{name}: the store grades {ref} as {stored.get('grade')}, card claims {declared}", c.rel))
            elif prefix in ("computed", "simulated"):
                inputs = num.get("inputs") or []
                grades = [nums[i]["grade"] for i in inputs if i in nums]
                expect = "E4"
                for g in grades:
                    expect = worse(expect, g)
                if declared != expect:
                    out.append(Finding(21, FAIL, f"{name}: {prefix} from {grades or 'constants'} gives max(E4, worst) = {expect}, card says {declared}", c.rel))
                if prefix == "simulated":
                    # A run is not automatically evidence. 5.3 puts that judgement
                    # in the capability table, reached from the plan this result
                    # stands on. But the declaration governs only whether the
                    # number may ALSO stand as a claim about the world, and the
                    # role is already visible in the field that names it: values[]
                    # asserts, observed_number and actual_number report what the
                    # run read. So an undeclared configuration refuses everywhere
                    # and a non-independent one refuses under values[] alone.
                    cfg = plan_configs.get(str(c.data.get("plan_id") or ""))
                    roles = number_roles(c).get(name, set())
                    if cfg is None:
                        out.append(Finding(21, FAIL, f"{name}: source simulated:{ref} but no plan card names this card's system_configuration, so the 5.3 judgement cannot be read", c.rel))
                    else:
                        ok, why = configuration_is_its_own_source(cfg)
                        if ok:
                            pass
                        elif "claim" in roles:
                            out.append(Finding(21, FAIL, f"{name}: named from values[], where the card asserts something about the system, and {why}", c.rel))
                        elif not roles:
                            out.append(Finding(21, FAIL, f"{name}: source simulated:{ref} and no field names it, so nothing says it is this run's reading rather than a claim; {why}", c.rel))
    return out or [Finding(21, PASS, f"{n} grades follow from their sources")]


def configuration_is_its_own_source(config: str) -> tuple[bool, str]:
    """5.3: a run is a source only where the configuration produces a number its
    inputs do not determine, and that is declared in the capability table rather
    than judged here. Undeclared is not a permission -- it fails.
    """
    for f in sorted((CONTRACTS / "capabilities").glob("*.json")):
        if f.name == "capabilities.schema.json":
            continue
        try:
            table = json.loads(f.read_text())
        except Exception:
            continue
        for c in table.get("configurations") or []:
            if c.get("config") != config:
                continue
            decl = c.get("output_independent_of_input")
            if not isinstance(decl, dict):
                return False, f"configuration {config!r} has not declared output_independent_of_input in {f.name} (5.3); undeclared is not a permission"
            if not decl.get("independent"):
                return False, f"configuration {config!r} declares its output fixed by its input ({f.name}); the card cites the input, not the run (5.3)"
            return True, ""
    return False, f"configuration {config!r} is in no capability table, so nothing declares whether a run of it is a source"


def check_22_irreversible(b: Bundle) -> list[Finding]:
    plans = b.of_kind("plan")
    if not plans:
        return [Finding(22, NA, "no plan cards")]
    approvals = b.of_kind("plan_approval")
    out: list[Finding] = []
    for c in plans:
        nums = c.numbers()
        for a in c.data.get("actions", []) or []:
            if a.get("reversible"):
                continue
            bad = [p for p in a.get("parameters", []) if nums.get(p, {}).get("grade") in ("E4", "E5")]
            if not bad:
                continue
            has = any(x.data.get("plan_id") == c.data.get("id") for x in approvals)
            if not has:
                out.append(Finding(22, FAIL, f"action {a.get('id')!r} is irreversible and rests on E4/E5 numbers {bad}; individual plan_approval is required (2.1 rule 3)", c.rel))
    return out or [Finding(22, PASS, "irreversible actions rest on E1-E3 or carry an individual approval")]


def check_23_manual_lockout(b: Bundle) -> list[Finding]:
    if not list(REPO.glob("*_agent/runs/*/manual_steps.md")):
        return [Finding(23, PENDING, "needs run logs and manual instruction sheets, which M1 produces")]
    return [Finding(23, PENDING, "lockout reconstruction not implemented yet")]


def check_24_calibration_validity(b: Bundle) -> list[Finding]:
    used = [(c, n) for c in b.cards if "__unreadable__" not in c.data
            for n in c.data.get("numbers", []) if str(n.get("source", "")).startswith("calibration:")]
    if not used:
        return [Finding(24, NA, "no calibration-derived numbers")]
    return [Finding(24, PENDING, f"{len(used)} calibration numbers found; validity windows need envelope/snapshot.json (M1) and the KB behind it (M3)")]


_KB_HISTORY: dict | None = None


# Fields that carry what a card read. Everything else in an entry is how the
# store organises itself, and a store reorganising is not a claim changing.
# `subject` is the case that forced the distinction: its own schema says it is
# there "so a query can find it without already knowing its id" -- a discovery
# pointer with a registry and an id, no number, no grade, no validity. It was
# filled in store-wide as one migration, and that migration alone put 19 of
# check 25's 34 pending findings on the board, every one of them saying an
# entry had changed when nothing a card could have read had.
#
# What moved there is the DISCOVERY SURFACE, not nothing: a re-query finds
# different entries, which is the field's whole purpose, and check 49 and gap
# detection stand on it. Under a pin the old subject is what gets served, so a
# card already written is unexposed -- but unexposed and inconsequential are
# different, and the PASS line says which one this is. `identifiers` is the
# same kind.
#
# Naming the claim-bearing fields is reading the entry schema, not choosing a
# subset of it. The earlier comment here refused to choose one for a good
# reason -- which fields reach a card was not written down -- and what changed
# is that `subject` now says in its own description what it is for.
CLAIM_FIELDS = {"numbers", "unit", "kind", "grade", "grade_tag", "source",
                "source_ref", "claim", "validity", "valid_until",
                "validity_conditions", "symbol", "formula", "inputs",
                "supersedes", "conflict_with"}
# `numbers` is the one that matters most and was missing for an hour on
# 2026-09-19. The first version of this list named `value` and `uncertainty`,
# which are NOT top-level properties of kb_entry -- they live inside
# `numbers[]` -- so they could never match, while a changed number surfaces as
# the single key `numbers` and was therefore counted as bookkeeping. An
# objective's NA moving 1.42 -> 9.99 was classified "nothing a card could have
# read is different", which is the exact failure this check exists to catch.
# manager-librarian found it by checking the list against the schema instead
# of against the prose, which is what the list is for. Two fields that name
# nothing are worse than none: they read as coverage.
#
# `supersedes` and `conflict_with` are here because an entry a card cites
# being replaced, or gaining a contradiction, is something the citing card has
# to know -- rules 7 and 8 keep both for that reason. `grade_tag` because
# 4.3.1 orders within E3 by it (peer_reviewed -> textbook -> vendor_spec ->
# preprint), so a retag changes the evidential standing behind a citation
# while the grade letter sits still.


def kb_entry_at(sha: str, entry_id: str) -> dict | None:
    """One entry's bytes as of a commit, parsed. None if it was not there."""
    import subprocess
    try:
        blob = subprocess.run(["git", "-C", str(GIT_REPO), "show",
                               f"{sha}:librarian_agent/kb/entries/{entry_id}.json"],
                              capture_output=True, text=True, check=True).stdout
        return json.loads(blob)
    except (subprocess.CalledProcessError, json.JSONDecodeError, OSError):
        return None


def kb_index_at(version: str) -> tuple[dict | None, str | None]:
    """The store's index as it stood at a pinned version, from its own history.

    check 25's message has always said that confirming an older pin needs the
    store's git history. It said it instead of doing it, and the cost was not
    noise: the branch that reported it also skipped the grade comparison, so a
    card pinning anything but today's version was not checked at all. Moving a
    pin forward then made the check quieter and restored the grade check at the
    same time -- the record became less true and the report got better, which
    is the wrong way round for a gate to point.
    """
    global _KB_HISTORY
    if _KB_HISTORY is None:
        _KB_HISTORY = {}
        import subprocess
        rel = "librarian_agent/kb/index.json"
        try:
            shas = subprocess.run(["git", "-C", str(REPO), "log", "--format=%H", "--", rel],
                                  capture_output=True, text=True, check=True).stdout.split()
            for sha in shas:
                blob = subprocess.run(["git", "-C", str(REPO), "show", f"{sha}:{rel}"],
                                      capture_output=True, text=True, check=True).stdout
                doc = json.loads(blob)
                _KB_HISTORY.setdefault(doc.get("kb_version"), (doc, sha))
        except (OSError, subprocess.CalledProcessError, json.JSONDecodeError):
            pass
    found = _KB_HISTORY.get(version)
    return found if found else (None, None)


def check_25_kb_refs(b: Bundle) -> list[Finding]:
    out: list[Finding] = []
    moved_pending: dict[tuple, list[str]] = {}
    cards = [c for c in b.cards if "__unreadable__" not in c.data]
    n = 0
    for c in cards:
        kb_sources = [x for x in c.data.get("numbers", []) if str(x.get("source", "")).startswith("kb:")]
        refs = {r.get("entry_id"): r for r in c.data.get("kb_refs", []) or []}
        for num in kb_sources:
            n += 1
            ref = str(num["source"]).split(":", 1)[1]
            if ref not in refs:
                out.append(Finding(25, FAIL, f"{num['name']} cites kb:{ref} with no kb_refs record (4.3.1)", c.rel))
        if c.kind == "axis" and kb_sources and not refs:
            out.append(Finding(25, FAIL, "axis card uses librarian values but records no kb_refs", c.rel))
        for r in c.data.get("kb_refs", []) or []:
            if not r.get("kb_version"):
                out.append(Finding(25, FAIL, f"kb_ref {r.get('entry_id')} has no kb_version", c.rel))
                continue
            if KB_INDEX is None:
                continue
            if r["kb_version"] != KB_INDEX.get("kb_version"):
                past, sha = kb_index_at(r["kb_version"])
                eid = r.get("entry_id")
                if past is None:
                    # Absence of evidence is not confirmation. A version that
                    # was never committed hashes a working tree and has nowhere
                    # to be read back from.
                    out.append(Finding(25, PENDING, f"kb_ref {eid} pins {r['kb_version']}, which is in no committed index; a version that never landed cannot be confirmed", c.rel))
                    continue
                then = (past.get("entries") or {}).get(eid)
                if then is None:
                    out.append(Finding(25, FAIL, f"kb_ref {eid} pins {r['kb_version']} ({sha[:7]}), where the store had no such entry", c.rel))
                    continue
                if then.get("grade") != r.get("grade"):
                    out.append(Finding(25, FAIL, f"kb_ref {eid} claims {r.get('grade')} and the store said {then.get('grade')} at {r['kb_version']} ({sha[:7]})", c.rel))
                    continue
                now = (KB_INDEX.get("entries") or {}).get(eid)
                if now and now.get("sha256") == then.get("sha256"):
                    continue
                # The entry moved. Say WHAT moved, and separate the two kinds.
                # Every one of these used to read the same sentence -- "what
                # moved needs reading" -- 34 times, which is a warning nobody
                # reads and so a warning that is not one. Collected per
                # (entry, version) below and reported once, because the same
                # correction under five cards is one fact (11-11).
                before = kb_entry_at(sha, eid)
                after_p = KB_DIR / "entries" / f"{eid}.json"
                after = json.loads(after_p.read_text()) if after_p.exists() else None
                if before is None or after is None:
                    moved_pending.setdefault((eid, r["kb_version"], sha, None), []).append(c.rel)
                else:
                    moved = tuple(sorted(k for k in set(before) | set(after)
                                         if before.get(k) != after.get(k)))
                    moved_pending.setdefault((eid, r["kb_version"], sha, moved), []).append(c.rel)
                continue
            stored = (KB_INDEX.get("entries") or {}).get(r.get("entry_id"))
            if stored is None:
                out.append(Finding(25, FAIL, f"kb_ref cites {r.get('entry_id')!r}, which the store does not have", c.rel))
            elif stored.get("grade") != r.get("grade"):
                out.append(Finding(25, FAIL, f"kb_ref {r.get('entry_id')} claims {r.get('grade')} but the store says {stored.get('grade')}", c.rel))

    bookkeeping = 0
    for (eid, ver, sha, moved), rels in sorted(moved_pending.items(), key=lambda kv: str(kv[0])):
        if moved is not None and not (set(moved) & CLAIM_FIELDS):
            # Only organisational fields moved -- nothing a card could have
            # read is different. Counted rather than reported, so the number
            # stays visible without 19 findings saying nothing happened.
            bookkeeping += len(rels)
            continue
        where = f"{rels[0]} and {len(rels) - 1} more" if len(rels) > 1 else rels[0]
        if moved is None:
            out.append(Finding(25, PENDING, f"kb_ref {eid} pins {ver} ({sha[:7]}) and the entry has changed "
                                            f"since; its bytes at that commit could not be read back, so what "
                                            f"moved is unknown. {len(rels)} cards: {where}", rels[0]))
            continue
        claims = sorted(set(moved) & CLAIM_FIELDS)
        out.append(Finding(25, PENDING,
            f"kb_ref {eid} pins {ver} ({sha[:7]}) and the store has since corrected {', '.join(claims)}"
            + (f" (also {', '.join(k for k in moved if k not in claims)})" if set(moved) - set(claims) else "")
            + f". The grade held, so this is a correction under a live pin and not a regrade: the pin is still "
              f"an honest record of what was read, and the question is whether the {len(rels)} card(s) resting "
              f"on it should be revised. {where}", rels[0]))
    if bookkeeping:
        out.append(Finding(25, PASS, f"{bookkeeping} pinned refs sit on entries whose movement was in the "
                                     f"discovery surface only -- `subject`, `identifiers` -- so what each "
                                     f"card READ is unmoved, though what a re-query would FIND has changed"))

    if KB_INDEX is not None:
        entries = {}
        for p in sorted((KB_DIR / "entries").glob("*.json")):
            try:
                entries[json.loads(p.read_text())["entry_id"]] = hashlib.sha256(p.read_bytes()).hexdigest()
            except (json.JSONDecodeError, KeyError):
                continue
        stale = [eid for eid, digest in entries.items()
                 if (KB_INDEX.get("entries") or {}).get(eid, {}).get("sha256") != digest]
        missing = set((KB_INDEX.get("entries") or {})) - set(entries)
        if stale or missing:
            out.append(Finding(25, FAIL, f"kb/index.json is stale: changed {sorted(stale)}, gone {sorted(missing)}. Rebuild it with librarian_agent/src/kb_index.py", "librarian_agent/kb/index.json"))
    if not any(f.status == FAIL for f in out):
        out.insert(0, Finding(25, PASS, f"{n} librarian values match the store's grade and pinned version"))
    return out


def check_26_snapshot(b: Bundle) -> list[Finding]:
    """An envelope snapshot must be the store it names, byte for byte.

    4.3.2 says the copy is compared against the authoritative store so the two
    cannot diverge, and the snapshot says how: `built_from_commit` names the
    commit it was built from, so every byte is readable back with
    `git show <commit>:<path>`. That is what this reads.

    Against that commit and not against HEAD. The store moves; an envelope
    taken last week is honest, and what makes it honest is naming the commit
    whose bytes it holds. `kb_version` identifies the knowledge and
    `built_from_commit` identifies the packaging.

    Against the store rather than against the published export, which an
    earlier draft of this check did. The export is itself a copy, so comparing
    copy to copy verifies the wrong relation -- and `built_from_commit` names
    the store commit, not the commit the export file happens to live in, so
    the lookup was wrong as well as the target.

    The per-part hashes are not recomputed here and `snapshot_hash` is not
    re-derived. Both would need the exporter's canonical form, and restating
    it would put one rule in two places with nothing comparing them (11-11).
    Comparing the embedded text against the committed bytes subsumes them: if
    the text is right, what any hash of it says is a separate question for the
    exporter's own verifier.

    WHAT A FIXTURE FOR THIS CHECK HAS TO BE, pinned here rather than sent.
    11-7 settled on 2026-09-20 that the four history-reading checks -- 26, 35,
    41, 46 -- get a script that BUILDS a repository rather than a stored one,
    and assigned that harness to manager-bridge as check 65. The harness is
    that seat's; which case it runs for check 26 is this one's, and it is
    written into the check so the hand-off cites instead of carries.

    THE DIVERGENCE CASE IS A REAL EXPORT WHOSE BYTES BELONG TO ANOTHER COMMIT,
    and it is one of nine outcomes this check can produce. Six of the other
    eight are also failures and none of them is 4.3.2's divergence:

      no snapshot at all            -> PENDING, and the wrong branch entirely
      unreadable JSON               -> FAIL, but that is check 1's kind of defect
      no `built_from_commit`        -> FAIL: not a copy of anything
      commit carries no store       -> FAIL: not a copy of anything
      entry absent at that commit   -> FAIL: not a copy of anything
      entry text != committed bytes -> FAIL: A COPY OF SOMETHING ELSE  <- this
      table without `from`          -> FAIL: not a copy of anything
      table path absent at commit   -> FAIL: not a copy of anything
      table text != committed bytes -> FAIL: A COPY OF SOMETHING ELSE  <- this

    The line that matters runs between "this is not a copy of anything" and
    "this IS a copy, of something else". Only the second is what 4.3.2 means
    by the store and the copy diverging, and only the second is a state a real
    repository reaches by accident -- the others need a snapshot nobody could
    have produced. A fixture that names a bogus commit and calls itself a
    divergence fixture exercises branch four, fails, and stays green while
    testing something else. That is the defect check 64 hit on its own first
    draft: a check whose question got decided by what it happened to look at.

    So the case, minimally: a built repository holding `kb/index.json` and at
    least one entry at commit C, plus `<name>_agent/envelope/snapshot.json`
    naming C with ONE entry's `text` altered by one byte. One byte, because a
    fixture that diverges loudly would also trip the cheaper branches and
    could not tell them apart. The table surface wants its own case for the
    same reason -- entries and tables are read by separate loops, and a
    fixture for one proves nothing about the other.

    Two facts about the glob the harness would otherwise find by debugging:
    the pattern is `*_agent/envelope/snapshot.json`, so a fixture placed under
    `bridge/` is never read at all, and the blob lookup runs against GIT_REPO
    rather than against the tree being validated.
    """
    import subprocess
    snaps = sorted(REPO.glob("*_agent/envelope/snapshot.json"))
    if not snaps:
        return [Finding(26, PENDING, "needs envelope/snapshot.json (M1) and the KB it is exported from (M3)")]
    out: list[Finding] = []
    checked = 0

    def blob(commit: str, path: str):
        try:
            return subprocess.run(["git", "-C", str(GIT_REPO), "show", f"{commit}:{path}"],
                                  capture_output=True, text=True, check=True).stdout
        except (OSError, subprocess.CalledProcessError):
            return None

    for p in snaps:
        rel = str(p.relative_to(REPO))
        try:
            doc = json.loads(p.read_text())
        except json.JSONDecodeError as exc:
            out.append(Finding(26, FAIL, f"is not readable JSON: {exc}", rel))
            continue
        commit = doc.get("built_from_commit")
        if not commit:
            out.append(Finding(26, FAIL,
                "carries no `built_from_commit`, so nothing says which bytes this is a copy of. A "
                "snapshot built from an uncommitted export cannot be read back and cannot be "
                "checked (4.3.2)", rel))
            continue
        if blob(commit, "librarian_agent/kb/index.json") is None:
            out.append(Finding(26, FAIL,
                f"names built_from_commit {commit[:12]}, which is not a commit in this repository "
                "that carries the store. A copy whose origin cannot be read back is not a copy of "
                "anything", rel))
            continue
        bad: list[str] = []
        for eid, e in (doc.get("entries") or {}).items():
            want = blob(commit, f"librarian_agent/kb/entries/{eid}.json")
            if want is None:
                bad.append(f"entry {eid} does not exist at that commit")
            elif want != e.get("text"):
                bad.append(f"entry {eid} does not match the committed bytes")
        for name, t in (doc.get("tables") or {}).items():
            src = t.get("from")
            if not src:
                bad.append(f"table {name} does not say which file it came from")
                continue
            # `from` is written relative to the librarian's own directory, the
            # way that agent names its own files; git wants it from the root.
            path = src if src.startswith("librarian_agent/") else f"librarian_agent/{src}"
            want = blob(commit, path)
            if want is None:
                bad.append(f"table {name} names {path}, absent at that commit")
            elif want != t.get("text"):
                bad.append(f"table {name} does not match the committed bytes of {path}")
        if bad:
            out.append(Finding(26, FAIL,
                f"does not match the store at {commit[:12]}: " + "; ".join(bad[:4]) +
                (f"; and {len(bad) - 4} more" if len(bad) > 4 else "") +
                ". Fix the KB and re-export rather than editing the copy (4.3.2)", rel))
        else:
            checked += 1
    return out or [Finding(26, PASS,
        f"{checked} envelope snapshots hold the bytes the commit they name holds")]


KB_LIKE = re.compile(r"(entries|literature|references|knowledge|kb)[/_.]", re.I)


def check_27_knowledge_ownership(b: Bundle) -> list[Finding]:
    out: list[Finding] = []
    for agent in ("microscope_agent", "simulation_agent", "bridge"):
        root = REPO / agent
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if p.is_file() and KB_LIKE.search(str(p.relative_to(root))):
                out.append(Finding(27, FAIL, "looks like a knowledge store inside an execution agent (P14)", str(p.relative_to(REPO))))
    return out or [Finding(27, PASS, "no execution agent keeps its own knowledge store")]


def check_28_precision(b: Bundle) -> list[Finding]:
    out: list[Finding] = []
    limit = LIMITS["order_of_magnitude_sig_figs"]
    n = 0
    for c in b.cards:
        if "__unreadable__" in c.data:
            continue
        intent = c.data.get("intent")
        if intent is None and c.kind in ("axis", "synthesis"):
            intent = "explore"   # the default (5.8); a card may not silently claim confirm
        nums = c.numbers()
        for name, num in nums.items():
            grade = num.get("grade")
            if grade not in ("E4", "E5"):
                continue
            n += 1
            sf = sig_figs(num.get("value", 0))
            if intent == "explore" and sf > limit:
                out.append(Finding(28, FAIL, f"{name} is {grade} in explore mode but claims {sf} significant figures ({num['value']}); write an order of magnitude (P15)", c.rel))
            if num.get("precision") == "order_of_magnitude" and sf > limit:
                out.append(Finding(28, FAIL, f"{name} is marked order_of_magnitude but claims {sf} significant figures", c.rel))
        # a computed value may not be more precise than its inputs
        for name, num in nums.items():
            if not str(num.get("source", "")).startswith("computed:"):
                continue
            ins = [nums[i] for i in (num.get("inputs") or []) if i in nums]
            if not ins:
                continue
            worst = min(sig_figs(i.get("value", 0)) for i in ins)
            if sig_figs(num.get("value", 0)) > worst:
                out.append(Finding(28, FAIL, f"{name} claims {sig_figs(num['value'])} significant figures from inputs good to {worst} (P15)", c.rel))
    return out or [Finding(28, PASS, f"{n} estimated and computed values claim no precision they do not have")]


def check_29_failure_record(b: Bundle) -> list[Finding]:
    files = [p for p in b.all_files if p.name == "failures.jsonl"]
    if not files:
        return [Finding(29, NA, "no failures.jsonl")]
    out: list[Finding] = []
    # `qid` or `task`, exactly one. A seat with no questions/ has no qid --
    # the librarian's dead ends belong to a task, not to a question -- and
    # putting a task id in a field named qid makes one name mean two things,
    # which is the collision this repository keeps paying for. Requiring both
    # would block the same seat a different way.
    required = {"at", "kind", "detail"}
    # plan.md 8.1 lists six kinds; this set held five. The missing one was
    # abandoned_attempt -- the attempt folded without producing a card, which
    # 6.2.3 calls the record that exists nowhere else and makes a completion
    # condition for clearing a session. A seat trying to write it was refused,
    # so the one record the discipline depends on was the one the gate blocked.
    kinds = {"validator_failure", "refusal", "deviation", "scope_voided", "success",
             "abandoned_attempt"}
    # `task` was a free string and nothing compared it to a task file.
    # Measured 2026-09-20: 12 of 22 distinct values resolve to no task, and
    # two of them are whole sentences sitting in an id field. That is not
    # carelessness -- the field forces a name on work that never came from a
    # queue, so a seat with an empty queue writes `none-queue-empty`, and a
    # seat auditing its own output writes a paragraph. `occasion` is the
    # honest third option, and it keeps what those rows actually say instead
    # of flattening them into one reserved token.
    task_files = list((REPO / "librarian_agent" / "tasks").glob("*.md"))
    for agent in ("microscope_agent", "simulation_agent", "bridge"):
        task_files += list((REPO / agent / "tasks").glob("*.md"))
    invented: list[str] = []
    n_records = 0
    for p in files:
        for i, line in enumerate(p.read_text().splitlines(), 1):
            if not line.strip():
                continue
            n_records += 1
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                out.append(Finding(29, FAIL, f"line {i}: {exc}", str(p.relative_to(REPO))))
                continue
            missing = required - set(rec)
            if missing:
                out.append(Finding(29, FAIL, f"line {i}: missing {sorted(missing)}", str(p.relative_to(REPO))))
            owners = {k for k in ("qid", "task", "occasion") if rec.get(k)}
            if not owners:
                out.append(Finding(29, FAIL, f"line {i}: names no qid, task or occasion, so nothing says what this attempt belonged to", str(p.relative_to(REPO))))
            elif len(owners) > 1:
                out.append(Finding(29, FAIL, f"line {i}: names {sorted(owners)}; one record belongs to one of them", str(p.relative_to(REPO))))
            t = rec.get("task")
            if t:
                stem = str(t).split()[0].split("--")[0].strip()
                if not any(q.stem == stem or q.stem.startswith(stem + "-")
                           for q in task_files):
                    invented.append(f"{p.parent.name}:{str(t)[:40]}")
            if rec.get("kind") not in kinds:
                out.append(Finding(29, FAIL, f"line {i}: unknown kind {rec.get('kind')!r}", str(p.relative_to(REPO))))
    if out:
        return out
    tail = ""
    if invented:
        tail = (f"; {len(invented)} name a `task` that is no task file -- work that did not come "
                f"from a queue has to invent one, and an invented id is a name nothing can refuse "
                f"({invented[0]}). `occasion` is the field for those and is now accepted; "
                f"ADVISORY until the existing rows migrate, because they sit in three agents' "
                f"trees and no one seat can clear them")
    return [Finding(29, PASS,
                    f"{n_records} failure records in {len(files)} files are well formed{tail}")]


def check_30_lessons(b: Bundle) -> list[Finding]:
    lessons = list(REPO.glob("librarian_agent/kb/lessons/*.json"))
    if not lessons:
        return [Finding(30, NA, "no lessons yet (M5)")]
    out: list[Finding] = []
    need = {"trigger", "claim", "evidence", "n", "condition_range", "falsifier", "valid_until", "grade"}
    for p in lessons:
        rec = json.loads(p.read_text())
        missing = need - set(rec)
        if missing:
            out.append(Finding(30, FAIL, f"missing {sorted(missing)} (8.2)", str(p.relative_to(REPO))))
        if not rec.get("evidence"):
            out.append(Finding(30, FAIL, "no evidence id: a lesson must cite a real record, not an interpretation", str(p.relative_to(REPO))))
    return out or [Finding(30, PASS, f"{len(lessons)} lessons carry evidence, n and a falsifier")]


def check_31_candidate_preservation(b: Bundle) -> list[Finding]:
    if not list(REPO.glob("librarian_agent/kb/lessons/*.json")):
        return [Finding(31, NA, "no lessons yet, so none can have removed a candidate (P16)")]
    return [Finding(31, PENDING, "screening history comparison not implemented yet")]


def check_32_purpose(b: Bundle) -> list[Finding]:
    goals = b.of_kind("goal")
    if not goals:
        return [Finding(32, NA, "no goal cards")]
    out: list[Finding] = []
    for c in goals:
        purpose, intent = c.data.get("purpose"), c.data.get("intent")
        default = PURPOSE_DEFAULT_INTENT.get(purpose, "missing")
        if default == "missing":
            out.append(Finding(32, FAIL, f"unknown purpose {purpose!r}", c.rel))
            continue
        if default is not None and intent != default and not c.data.get("intent_rationale"):
            out.append(Finding(32, FAIL, f"purpose {purpose} defaults to intent {default} but the card says {intent} with no intent_rationale (4.5.1)", c.rel))
        if purpose == "compare" and not c.data.get("compare_variable"):
            out.append(Finding(32, FAIL, "purpose compare requires compare_variable", c.rel))
    return out or [Finding(32, PASS, f"{len(goals)} goals state a purpose consistent with their intent")]


def card_scope(card) -> str:
    """The folder a card's siblings share. Used by checks 33 and 58, which ask
    two halves of one question and must partition the same way."""
    return str(Path(card.rel).parent)


def check_33_caller_isolation(b: Bundle) -> list[Finding]:
    axes = b.of_kind("axis")
    if not axes:
        return [Finding(33, NA, "no axis cards")]
    out: list[Finding] = []

    # Siblings are the cards of one fan-out, and a fan-out lives in one
    # directory. Grouping by qid alone made a fixture in contracts/examples/ a
    # sibling of a real card in an agent's questions/ the moment the two shared
    # an id -- and they did, because the fixtures wear plausible qids. The
    # symptom was "siblings cite different kb_version", which was true of the
    # two sets and meaningless between them. Scope is the directory.
    # And the same argument a second time, for the same reason. A revision is a
    # re-run (4.5.5), so two revisions are two fan-outs and their cards are not
    # each other's siblings. caller_id is <qid>:<config>:<axis> with no revision
    # component (4.3.1), so the same axis at two revisions necessarily shares
    # one -- grouping without the revision made "caller_id reused" fire on a
    # question that had done nothing wrong, and made 4.5.5's own instruction
    # unfollowable.
    groups: dict[tuple[str, str, object], list] = {}
    for c in axes:
        groups.setdefault((card_scope(c), c.data.get("qid"), c.data.get("revision")), []).append(c)

    for (where, qid, _rev), group in sorted(groups.items(), key=lambda kv: str(kv[0])):
        callers = [c.data.get("caller_id") for c in group]
        if len(set(callers)) != len(callers):
            dupes = {x for x in callers if callers.count(x) > 1}
            out.append(Finding(33, FAIL, f"qid {qid} in {where}: caller_id reused {sorted(dupes)}; each sub-agent gets its own (4.3.1)"))
        versions = {c.data.get("kb_version") for c in group}
        if len(versions) > 1:
            out.append(Finding(33, FAIL, f"qid {qid} in {where}: siblings cite different kb_version {sorted(versions)}; S3.0 pins one"))
        for c in group:
            # Both forms, while the cards that predate a6dca6a migrate (4.3.1).
            # The one without the revision stops being accepted once they have.
            qid, cfg, ax = c.data.get("qid"), c.data.get("config"), c.data.get("axis")
            want = f"{qid}:v{c.data.get('revision')}:{cfg}:{ax}"
            legacy = f"{qid}:{cfg}:{ax}"
            if c.data.get("caller_id") == legacy:
                want = legacy
            if c.data.get("caller_id") != want:
                out.append(Finding(33, FAIL, f"caller_id {c.data.get('caller_id')!r} does not match {want!r}", c.rel))
    return out or [Finding(33, PASS, f"{len(axes)} axis cards are isolated by caller and pinned to one kb_version")]


def check_34_compare_arms(b: Bundle) -> list[Finding]:
    plans = [c for c in b.of_kind("plan") if c.data.get("purpose") == "compare"]
    if not plans:
        return [Finding(34, NA, "no comparison plans")]
    out: list[Finding] = []
    for c in plans:
        var = c.data.get("compare_variable")
        arms = c.data.get("compare_arms") or []
        if not var:
            out.append(Finding(34, FAIL, "purpose compare without compare_variable", c.rel))
            continue
        if len(arms) < 2:
            out.append(Finding(34, FAIL, "purpose compare needs at least two arms", c.rel))
            continue
        base = None
        for arm in arms:
            fixed = {d["parameter"]: d["number"] for d in arm.get("conditions", []) if d["parameter"] != var}
            if base is None:
                base = fixed
            elif fixed != base:
                diff = {k for k in set(base) | set(fixed) if base.get(k) != fixed.get(k)}
                out.append(Finding(34, FAIL, f"arm {arm.get('arm')!r} differs from the first arm in {sorted(diff)}, not only in {var} (4.5.1)", c.rel))
    return out or [Finding(34, PASS, f"{len(plans)} comparison plans hold every condition but the compared variable")]


AGENT_OF_PATH = [
    (re.compile(r"^microscope_agent/"), "microscope_agent"),
    (re.compile(r"^simulation_agent/"), "simulation_agent"),
    (re.compile(r"^librarian_agent/"), "librarian_agent"),
    (re.compile(r"^bridge/"), "bridge"),
]
# `plan_ko.md` is deliberately still here, and deliberately gone from
# ALLOWED_PATHS. The two lists answer different questions and the same name
# means different things to each. ALLOWED_PATHS asks what may exist on disk
# now, and the Korean record left version control on 2026-09-20 -- so keeping
# it there would silently permit a resurrection the person decided against.
# SHARED_PATHS is read by checks 35 and 41, which walk HISTORY, and three
# commits touched that file. Removing it from here reddens all three at once:
# verified by doing it, which produced `seat 'architecture' owns ['design'];
# this path is unattributable's` on 952205c, 31f86c1 and 8d61a3a. A path
# classifier for history must keep every name history ever had.
SHARED_PATHS = re.compile(r"^(plan\.md|plan_ko\.md|CLAUDE\.md|ARCHITECT\.md|README\.md|\.gitignore|\.mcp\.json|pyproject\.toml|uv\.lock|\.claude/|docs/)")
# Both lists, because they answer different questions about the same file:
# ALLOWED_PATHS says it may exist and SHARED_PATHS says whose boundary it is
# in. A root file added to the first alone passes check 13 and classifies as
# `unattributable`, so it exists legitimately and no seat may be said to own
# it. Section 7 records the coupling as of 2026-09-19.

# An agent's CLAUDE.md and .claude/ belong to the design seat, not to the agent
# (6.2). Counting them as the agent's made every ordinary design commit look
# like a boundary crossing, which is the fastest way to teach someone to ignore
# a check.
# What inside an agent's directory belongs to the design seats rather than to
# the agent. seats.json cannot add to this: `paths` there only narrows what a
# seat may touch, so a path this regex does not classify as design is refused
# by check 41 however the registry lists it. That asymmetry cost half a day on
# 2026-09-19, and check 48 exists to make a `paths` entry that cannot be
# granted fail loudly instead of silently.
INBOX = re.compile(r"^(microscope|simulation)_agent/inbox/")

DESIGN_OWNED = re.compile(r"^((microscope|simulation|librarian)_agent|bridge)/(CLAUDE\.md|README\.md|\.claude/|tasks/)")


def seat_boundary_of(path: str) -> str:
    """Whose territory a path is in (6.2.1).

    The same split check 35 counts, named instead of counted. One table, so a
    seat's boundary and a commit's boundary cannot drift apart.
    """
    if SHARED_PATHS.match(path) or DESIGN_OWNED.match(path) or path.startswith("contracts/"):
        return "design"
    # An inbox sits in the receiving agent's tree and belongs to the bridge
    # (7.1 rule 8). Place decides where a reader looks; this decides who may
    # write. An agent able to write its own inbox could forge a delivery, which
    # is the one thing the bridge exists to make impossible.
    if INBOX.match(path):
        return "bridge"
    for rx, agent in AGENT_OF_PATH:
        if rx.match(path):
            return agent
    return "unattributable"


def load_seats() -> dict:
    p = CONTRACTS / "seats.json"
    return json.loads(p.read_text()) if p.exists() else {}


def before_enforcement(sha: str) -> bool:
    """True when this commit is at or before the line the boundary became a gate.

    `enforced_from` in seats.json names that commit. Before it, section 6.2 was
    written and nothing refused a crossing, so checks 35 and 41 report rather
    than fail: a commit made under a convention did not break a gate that did
    not exist. Without this, moving a path between seats reddens history that
    was correct when it was written, and a sweep that reddens on every boundary
    move is a sweep nobody runs.

    It costs something, and the registry says so: a real crossing from before
    the line is hidden too. That was acceptable once, for a span small enough to
    read commit by commit. Moving this line forward again would not be -- it
    would turn a gate away from the work it was built to catch.
    """
    line = (load_seats() or {}).get("enforced_from")
    if not line:
        return False
    import subprocess
    try:
        subprocess.run(["git", "-C", str(GIT_REPO), "merge-base", "--is-ancestor", sha, line],
                       check=True, capture_output=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


WAS_CONVENTION = "the boundary was a convention here, before seats.json's enforced_from"


def check_35_session_boundary(b: Bundle, commit_range: str | None = None, staged: bool = False) -> list[Finding]:
    """One session writes inside one agent (6.2).

    A commit touching two agent directories came from a session that could see
    both, which is the thing the session split exists to prevent.

    --staged is the mode the pre-commit hook uses: there is no commit to range
    over yet, and refusing at commit time is the only refusal that arrives
    before the damage is in history.
    """
    if not commit_range and not staged:
        return [Finding(35, PENDING, "pass --commit-range or --staged; the pre-commit hook passes --staged (6.2)")]
    lax = False
    import subprocess

    def git(*args: str) -> str:
        return subprocess.run(["git", "-C", str(GIT_REPO), *args],
                              capture_output=True, text=True, check=True).stdout

    # The rule is per commit. Diffing the endpoints of a range would aggregate
    # several sessions' commits into one set and fail a history that is
    # perfectly well behaved -- and a check that fails correct work teaches
    # people to stop reading it.
    if not staged:
        # --no-merges, and not for tidiness. A merge holding several boundaries
        # is the definition of a merge, not a violation: the commits it holds
        # were each checked on their own branch. Without this, rev-list on
        # M~1..M returns the merge and the commits it brought, the count
        # exceeds one, and the decomposition re-enters on the identical range
        # forever -- which surfaced as `check raised RecursionError` and
        # refused every merge (6.2.1). What a merge contributes of its own is
        # check 41's, through --cc.
        try:
            shas = [x for x in git("rev-list", "--reverse", "--no-merges", commit_range or "").splitlines() if x.strip()]
        except (OSError, subprocess.CalledProcessError) as exc:
            return [Finding(35, FAIL, f"cannot read commit range {commit_range!r}: {exc}")]
        if not shas:
            return [Finding(35, NA, f"{commit_range} holds only merges; what a merge itself contributes is check 41's (6.2.1)")]
        if len(shas) == 1:
            # Diff that commit rather than the range: the range may also span
            # merges, and its endpoints would aggregate what they brought.
            # Falling through rather than recursing: the inner call would see
            # one commit again and land right back here.
            lax = before_enforcement(shas[0])
            commit_range = f"{shas[0]}~1..{shas[0]}"
        if len(shas) > 1:
            out: list[Finding] = []
            for sha in shas:
                lax = before_enforcement(sha)
                for f in check_35_session_boundary(b, f"{sha}~1..{sha}"):
                    if f.status == FAIL:
                        out.append(Finding(35, PENDING if lax else FAIL,
                                           f"{sha[:7]}: {f.message}"
                                           + (f" -- {WAS_CONVENTION}" if lax else ""), f.path))
            return out or [Finding(35, PASS, f"{len(shas)} commits each stay inside one boundary")]

    args = ["diff", "--name-only"]
    args += ["--cached"] if staged else [commit_range]
    try:
        paths = [p for p in git(*args).splitlines() if p.strip()]
    except (OSError, subprocess.CalledProcessError) as exc:
        what = "the staged set" if staged else f"commit range {commit_range!r}"
        return [Finding(35, FAIL, f"cannot read {what}: {exc}")]
    if not paths:
        return [Finding(35, NA, "nothing staged" if staged else f"no files changed in {commit_range}")]
    touched: dict[str, list[str]] = {}
    contracts_touched = []
    design_paths = []
    for p in paths:
        # One table, through seat_boundary_of, which is what its docstring
        # promises and what stopped being true the moment an inbox was
        # classified in one place and not the other: check 41 called
        # <agent>/inbox/ the bridge's and check 35 called it the agent's, so a
        # delivery that also moved the turn -- the ordinary case -- counted as
        # two boundaries and was refused.
        where = seat_boundary_of(p)
        if p.startswith("contracts/"):
            contracts_touched.append(p)
        if where == "design":
            design_paths.append(p)
        elif where != "unattributable":
            touched.setdefault(where, []).append(p)
    out: list[Finding] = []
    if len(touched) > 1:
        out.append(Finding(35, FAIL, f"one commit writes into {sorted(touched)}; a session writes inside one agent (6.2)"))
    if contracts_touched and touched:
        out.append(Finding(35, FAIL, f"the same commit edits contracts/ and {sorted(touched)}; contracts are read by agent sessions, not written by them"))
    if out:
        return [Finding(35, PENDING, f.message + f" -- {WAS_CONVENTION}", f.path) for f in out] if lax else out
    where = "the design seat" if (design_paths or contracts_touched) and not touched else (
        sorted(touched)[0] if touched else "no agent")
    return [Finding(35, PASS, f"{len(paths)} changed paths stay inside one boundary ({where})")]


def check_36_symbol_collision(b: Bundle) -> list[Finding]:
    defs: dict[str, tuple[str, str]] = {}
    out: list[Finding] = []
    n = 0
    for c in b.cards:
        if "__unreadable__" in c.data:
            continue
        for num in c.data.get("numbers", []):
            # Either declaration pulls it in. Gating on `derived` alone let a
            # minted group carrying a symbol and no flag pass unlooked-at, and
            # a check that stops looking still reports PASS.
            if num.get("origin") or not (num.get("derived") or num.get("symbol")):
                continue
            sym, formula = num.get("symbol"), num.get("formula")
            if not sym:
                out.append(Finding(36, FAIL, f"{num.get('name')} is derived but has no symbol", c.rel))
                continue
            n += 1
            if sym in defs and defs[sym][0] != formula:
                out.append(Finding(36, FAIL, f"symbol {sym!r} is {formula!r} here but {defs[sym][0]!r} in {defs[sym][1]} (5.7)", c.rel))
            else:
                defs[sym] = (formula, c.rel)
    if KB_INDEX is not None:
        for eid, e in (KB_INDEX.get("entries") or {}).items():
            # By symbol, not by kind. A symbol means one definition whatever its
            # dimension, and filtering on dimensionless_group dropped every
            # derived_quantity out of the collision check the moment that kind
            # existed -- silently, since a check that stops looking still passes.
            if not e.get("symbol"):
                continue
            sym, formula = e["symbol"], e.get("formula")
            if sym in defs and defs[sym][0] != formula:
                out.append(Finding(36, FAIL, f"symbol {sym!r} is {defs[sym][0]!r} in {defs[sym][1]} but the store defines it as {formula!r} (5.7)", "librarian_agent/kb/index.json"))
    elif n:
        out.append(Finding(36, PENDING, f"{n} ad-hoc groups checked against each other; comparing them with the store needs kb/index.json"))
    return out or [Finding(36, PASS if n else NA, f"{n} symbol definitions do not collide" if n else "no symbols defined")]


def agent_of_config(config: str) -> str | None:
    """Which agent's capability table declares this configuration.

    4.6.9's fourth time base is for a side that reads no clock, and that is a
    property of the declared model rather than of where a card sits -- a
    fixture lives in contracts/examples/ and still belongs to one side. So this
    reads the table, the same route check 21 takes to the independence
    declaration.
    """
    for f in sorted((CONTRACTS / "capabilities").glob("*.json")):
        if f.name == "capabilities.schema.json":
            continue
        try:
            table = json.loads(f.read_text())
        except Exception:
            continue
        for c in table.get("configurations") or []:
            if c.get("config") == config:
                return table.get("agent")
    return None


def check_37_time_base(b: Bundle) -> list[Finding]:
    results = b.of_kind("result")
    if not results:
        return [Finding(37, NA, "no result cards")]
    out: list[Finding] = []
    plan_cfg = {
        str(pc.data.get("id")): ((pc.data.get("system_configuration") or {}).get("config"))
        for pc in b.of_kind("plan")
        if isinstance(pc.data.get("system_configuration"), dict)
    }
    for c in results:
        tb = c.data.get("time_base") or {}
        align = tb.get("alignment")
        if align == "software_monotonic":
            out.append(Finding(37, FAIL, "physics rests on the software monotonic clock; use a trigger counter or a device timestamp (4.6.9)", c.rel))
        if align == "model_step_index":
            # The fourth means is for a side whose time is an integer step count
            # and reads no clock (4.6.9, 53e5561). An instrument result must not
            # leave by this door: on that side a step index would be a software
            # timestamp wearing another name, which is the thing the rule
            # forbids. Read from the capability table, not from the path -- a
            # fixture sits in contracts/examples/ and still belongs to one side.
            cfg = plan_cfg.get(str(c.data.get("plan_id") or ""))
            who = agent_of_config(cfg) if cfg else None
            if who is None:
                out.append(Finding(37, FAIL, f"rests on a model step index, but no capability table declares this card's "
                                             f"configuration ({cfg!r}), so nothing says this side reads no clock (4.6.9)", c.rel))
            elif who != "simulation_agent":
                out.append(Finding(37, FAIL, f"rests on a model step index and its configuration {cfg!r} belongs to {who}, "
                                             f"which has a clock; there a step index is a software timestamp under another "
                                             f"name (4.6.9)", c.rel))
        if not tb.get("t0_wall"):
            out.append(Finding(37, FAIL, "no t0_wall: events cannot be placed on a common axis", c.rel))
    if not list(REPO.glob("*_agent/runs/*/log.json")):
        out.append(Finding(37, PENDING, "per-event offsets need run logs from M1"))
    return out or [Finding(37, PASS, f"{len(results)} results rest on a time base 4.6.9 admits")]


def _optical_path_table() -> tuple[dict | None, str]:
    """The optical path table, from wherever the librarian last published it.

    4.3.2 puts a published table inside `snapshot_<agent>.json` under `tables`,
    not in a file of its own. This used to glob `optical_paths*.json`, a file
    the design never names -- so the validator was waiting for something nobody
    was asked to write, and the seat that noticed refused to write it rather
    than make a third copy of one table. Falls back to the flat staging table
    that is not decomposed yet (11.1).
    """
    for cand in sorted((KB_DIR / "exports").glob("snapshot_*.json")):
        try:
            snap = json.loads(cand.read_text())
        except json.JSONDecodeError:
            continue                      # check 1 reports an unreadable export
        pinned = (snap.get("tables") or {}).get("optical_paths")
        if not isinstance(pinned, dict):
            continue
        # A table is pinned as the file's bytes plus their sha256, not as a
        # parsed object: one canonical form and one hash per table, and a copy
        # sitting in an envelope can be checked without reaching for the
        # original. So the consumer parses the pinned text.
        try:
            table = json.loads(pinned["text"]) if "text" in pinned else pinned
        except (json.JSONDecodeError, TypeError):
            continue
        if table.get("configurations"):
            return table, f"{_rel(cand)} > tables.optical_paths"
    staged = KB_DIR / "staging" / "optical_paths.v0.json"
    if staged.exists():
        return json.loads(staged.read_text()), _rel(staged)
    return None, ""


def _rel(p) -> str:
    """Repo-relative when it can be, absolute when it cannot.

    A store handed in from outside the repository -- a self-test, a scratch
    export -- is not an error, and `relative_to` raising on it turned three
    separate call sites into crashes. Fixed once in check 43 and left in the two
    table helpers, which is the same miss twice.
    """
    try:
        return str(pathlib.Path(p).relative_to(REPO))
    except ValueError:
        return str(p)


def _sample_table() -> tuple[dict | None, str]:
    """The instance table -- what is physically on the bench, not what it is.

    Beside the device table rather than inside it: every column there is about
    driving hardware and false of a sample. Architecture ruled the split on
    2026-09-19 and the reason is instance versus type -- a measurement is made
    on an instance and a specification written about a type, so an observation
    of this bottle stays true of the bottle even if the bottle turns out to be
    another product.
    """
    staged = KB_DIR / "staging" / "samples.v0.json"
    if staged.exists():
        return json.loads(staged.read_text()), _rel(staged)
    return None, ""


def _device_table() -> tuple[dict | None, str]:
    """The channel table, from wherever the librarian last published it.

    Same preference as the optical path table: exports first, then the flat
    staging table it has not decomposed yet (11.1).
    """
    for cand in sorted((KB_DIR / "exports").glob("devices*.json")):
        return json.loads(cand.read_text()), _rel(cand)
    staged = KB_DIR / "staging" / "devices.v0.json"
    if staged.exists():
        return json.loads(staged.read_text()), _rel(staged)
    return None, ""


def check_38_one_table(b: Bundle) -> list[Finding]:
    """A configuration list, an optical path list and a channel table are one (4.6.7).

    Two tables drift, and the drift shows up as a plan that is valid on paper
    while no light reaches the detector.

    Configuration ids were compared here from the start; the `devices[]` lists
    were not, so a configuration could name hardware the channel table does not
    have and nothing failed. That is how `camera_splitter` -- a row retired on
    2026-09-17 because it was never a channel -- stayed named by three
    configurations after the table dropped it.
    """
    caps = sorted((CONTRACTS / "capabilities").glob("*.json"))
    caps = [c for c in caps if c.name != "capabilities.schema.json"]
    if not caps:
        return [Finding(38, NA, "no capability tables")]

    known_obs = {o["id"] for o in json.loads((CONTRACTS / "observables.json").read_text()).get("observables", [])}
    table, table_rel = _optical_path_table()
    out: list[Finding] = []
    checked = 0

    for f in caps:
        cap = json.loads(f.read_text())
        rel = str(f.relative_to(REPO))
        configs = cap.get("configurations", []) or []

        by_config = {c.get("config"): c for c in configs}
        for conf in configs:
            for item in conf.get("produces", []) or []:
                oid = produced_id(item)
                if oid not in known_obs:
                    out.append(Finding(38, FAIL, f"configuration {conf.get('config')!r} produces {oid!r}, which contracts/observables.json does not define", rel))
                if isinstance(item, str):
                    continue
                # "composes with anything" is a sentence a table can hold and an
                # instrument cannot. The perturbation has to name this side back.
                for need in item.get("requires_composition", []):
                    other = by_config.get(need)
                    if other is None:
                        out.append(Finding(38, FAIL, f"{conf.get('config')!r} needs {need!r} composed in for {oid!r}, and no such configuration is declared here", rel))
                    elif other.get("role") != "perturbation":
                        out.append(Finding(38, FAIL, f"{conf.get('config')!r} needs {need!r} composed in for {oid!r}, but {need!r} is {other.get('role')!r}; only a perturbation composes in", rel))
                    elif conf.get("config") not in (other.get("composes_with") or []):
                        out.append(Finding(38, FAIL, f"{conf.get('config')!r} claims {need!r} composes in for {oid!r}, but {need!r}'s composes_with is {sorted(other.get('composes_with') or [])}", rel))

        if cap.get("agent") != "microscope_agent":
            continue                      # only the instrument has an optical path table
        if table is None:
            out.append(Finding(38, PENDING, "no optical path table published or staged yet", rel))
            continue

        table_ids = {c["id"] for c in table.get("configurations", [])}
        cap_ids = {c["config"] for c in configs}
        checked += len(cap_ids)
        if cap_ids != table_ids:
            only_cap, only_table = sorted(cap_ids - table_ids), sorted(table_ids - cap_ids)
            out.append(Finding(38, FAIL, f"the two tables disagree: only in capabilities {only_cap}, only in {table_rel} {only_table}", rel))
        # The devices[] side of the same table. One direction only: a channel
        # may exist without appearing in any configuration (the piezo stage
        # appears in none), but a configuration may not name hardware that is
        # not there.
        devices, dev_rel = _device_table()
        if devices is None:
            out.append(Finding(38, PENDING, "no channel table published or staged yet, so the devices[] lists are unchecked", rel))
        else:
            live = {c["id"] for c in devices.get("channels", []) if "id" in c}
            retired = {r["id"]: r for r in devices.get("retired_rows", []) or [] if "id" in r}
            for conf in configs:
                for dev in conf.get("devices", []) or []:
                    if dev in live:
                        continue
                    if dev in retired:
                        row = retired[dev]
                        why = str(row.get("why", "")).split(".")[0].strip()
                        out.append(Finding(38, FAIL, f"configuration {conf.get('config')!r} names device {dev!r}, which {dev_rel} retired on {row.get('retired_at')}: {why}", rel))
                    else:
                        out.append(Finding(38, FAIL, f"configuration {conf.get('config')!r} names device {dev!r}, which is not a channel in {dev_rel}", rel))

        for conf in configs:
            ref = conf.get("optical_path")
            if ref is None:
                out.append(Finding(38, FAIL, f"configuration {conf.get('config')!r} declares no optical_path", rel))
            elif ref not in table_ids:
                out.append(Finding(38, FAIL, f"configuration {conf.get('config')!r} points at optical path {ref!r}, which {table_rel} does not have", rel))

    # A plan writes device names too, and nothing compared them until now: the
    # capability table was taught to match the channel table, the cards were
    # not. So a plan validates green and then stops at preflight, which is the
    # worst place to learn a name is wrong -- the gate has already passed it.
    #
    # A plan may name a channel OR an element. "set the dia lamp" is the true
    # statement; "set stand_ti2e" would lose which of that channel's ten
    # elements was meant. Resolving element to channel is the orchestrator's
    # job, not the card's.
    devices, dev_rel = _device_table()
    if devices is not None:
        known_names = {c["id"] for c in devices.get("channels", [])}
        known_names |= {e["id"] for c in devices.get("channels", [])
                        for e in (c.get("elements") or [])}
        approved_hashes = {a.data.get("plan_hash"): a.data.get("approved_by")
                           for a in b.of_kind("plan_approval")}
        for card in b.of_kind("plan"):
            if card.data.get("author") != "microscope_agent":
                continue                      # only the instrument has a channel table
            named = {a.get("device") for a in card.data.get("actions", []) or []}
            named |= {c.get("device") for c in card.data.get("conditions", []) or []}
            named |= set((card.data.get("system_configuration") or {}).get("devices") or [])
            unknown = sorted(n for n in named if n and n not in known_names)
            if not unknown:
                continue
            signer = approved_hashes.get(plan_hash(card.data))
            if signer:
                # Correcting the card would change its hash and void an approval
                # a person signed (5.5). Only that person can issue a corrected
                # revision, so this reports who is blocking rather than failing
                # work nobody inside the system is allowed to do.
                out.append(Finding(38, PENDING, f"{card.data.get('id')} names {unknown}, which {dev_rel} does not list; its hash is pinned by an approval signed by {signer}, so only a person can issue a corrected revision (5.5)", card.rel))
            else:
                out.append(Finding(38, FAIL, f"{card.data.get('id')} names device(s) {unknown}, which {dev_rel} lists as neither a channel nor an element", card.rel))

    for oid in known_obs:
        entry = next(o for o in json.loads((CONTRACTS / "observables.json").read_text())["observables"] if o["id"] == oid)
        for u in entry.get("units", []):
            if unit_entry(u) is None:
                out.append(Finding(38, FAIL, f"observable {oid!r} admits unit {u!r}, which units.json does not define", "contracts/observables.json"))

    return out or [Finding(38, PASS, f"{checked} configurations match the optical path table, and every produced id is in the vocabulary")]


def check_39_estimate_justified(b: Bundle) -> list[Finding]:
    """An estimate is legitimate only when someone looked (4.3.1).

    kb_refs records what the librarian supplied; kb_gaps records what it could
    not. Without the second, the service's actual output -- the discovery of a
    gap -- leaves no trace on disk, and an estimate standing on a real absence
    looks exactly like one nobody checked. A card that never reached the
    librarian says so in degraded, and this check does not apply to it: not
    reached and looked-for-and-absent are different claims.
    """
    out: list[Finding] = []
    n = 0
    for c in b.cards:
        if "__unreadable__" in c.data:
            continue
        if any("librarian" in str(d) for d in c.data.get("degraded") or []):
            continue
        assumed = {name for name, num in c.numbers().items()
                   if str(num.get("source", "")).startswith("assumed:")}
        if not assumed:
            continue
        gap_ids = {str(g.get("gap_id")) for g in (c.data.get("kb_gaps") or []) if isinstance(g, dict)}
        for a in c.data.get("assumptions") or []:
            if not isinstance(a, dict):
                continue
            covered = sorted(assumed.intersection(a.get("numbers") or []))
            if not covered:
                continue
            n += len(covered)
            ref = a.get("gap_ref")
            if not ref:
                out.append(Finding(39, FAIL, f"assumption {a.get('rationale_id')!r} explains {covered} but names no gap_ref; with the librarian reachable an estimate has to say what was looked for and not found (4.3.1)", c.rel))
            elif ref not in gap_ids:
                out.append(Finding(39, FAIL, f"assumption {a.get('rationale_id')!r} points at gap {ref!r}, which is not in this card's kb_gaps {sorted(gap_ids)}", c.rel))
    if out:
        return out
    if n == 0:
        return [Finding(39, NA, "no card estimated while the librarian was reachable")]
    return [Finding(39, PASS, f"{n} estimates each name the gap they stand on")]


def check_49_absent_searched_the_neighbourhood(b: Bundle) -> list[Finding]:
    """`absent` may only be claimed after the name neighbourhood was searched.

    4.3.1 already draws this line once: a gap with an empty `searched` is not a
    gap, because not-looked-for and not-there are different claims. `absent`
    makes the strongest claim of the five kinds -- it does not exist -- and its
    next action sends the caller outside and then to a person. A gap that has
    only tried one exact string has not earned it; what it knows is "not found
    under this name", and that has a different next action: ask again with the
    name the store uses.

    The two were structurally unable to back each other. `nearest` holds
    entries that answered to the NAME and fell short on CONDITIONS, and
    `absent` is emitted exactly when nothing answers to the name -- so an
    absent gap could never carry a `nearest`, and its emptiness meant nothing.
    `near_names` is the other axis and is what this check reads.

    The evidence is the service's first day: of nine empty kb_query answers,
    eight were the store holding the knowledge under another word or in a
    published table, and one was honestly not there. `numerical_aperture` came
    back absent while six entries held it as `na`. A false gap fails quietly --
    nothing rejects it, and later someone reads it as proof the value does not
    exist. For an agent whose distinguishing job is recording what it could not
    answer, recording an absence that is not there is the exact failure mode.
    """
    out: list[Finding] = []
    seen, degraded = 0, 0
    carried: list[tuple] = []
    bare: list[tuple] = []
    for c in b.cards:
        if "__unreadable__" in c.data:
            continue
        # The same carve-out check 39 makes, for the same reason. A card that
        # never reached the librarian wrote its gaps by hand, and no
        # neighbourhood search can stand behind one -- demanding it would fail
        # 25 cards across three other seats for work that was correct when it
        # was done. Not-reached and looked-for-and-absent are different claims,
        # and this check is about the second.
        if any("librarian" in str(d) for d in c.data.get("degraded") or []):
            degraded += 1
            continue
        for g in c.data.get("kb_gaps") or []:
            if not isinstance(g, dict) or g.get("kind") != "absent":
                continue
            seen += 1
            (carried if "near_names" in g else bare).append(
                (c.rel, g.get("gap_id"), g.get("observable")))
    # Expand, migrate, contract. The field exists and the server does not emit
    # it yet, so every absent gap is bare and failing them would refuse work
    # that could not have been done otherwise -- the deadlock that makes a gate
    # something to bypass. This flips itself: once any gap carries near_names
    # the migration has started, and a bare one after that is a real defect.
    # Check 43 does the same while the store catches up on `source`.
    if bare and not carried:
        return [Finding(49, PENDING,
                        f"{len(bare)} absent gaps carry no `near_names` and none carries it yet, so the "
                        "server has not started emitting it; this fails once the first one does",
                        bare[0][0])]
    for rel, gid, obs in bare:
        out.append(Finding(49, FAIL,
            f"gap {gid!r} for {obs!r} claims `absent` but carries no `near_names`, while "
            f"{len(carried)} other gaps do -- so nothing says the store was asked what it calls "
            "this. An empty list is an answer, searched and nothing near; a missing key is not (4.3.1)",
            rel))
    if out:
        return out
    if seen == 0:
        return [Finding(49, NA, f"no card that reached the librarian carries an `absent` gap; "
                                f"{degraded} are on the degraded path and out of scope")]
    return [Finding(49, PASS, f"{seen} absent gaps each searched the neighbourhood first")]


def check_55_section_7_names_are_allowed(b: Bundle) -> list[Finding]:
    """A file section 7 declares has to be one ALLOWED_PATHS would let exist.

    Two places say where a file may live and nothing compared them (11-11).
    Section 7 is the prose of record -- it carries reasons, references and
    ownership that a generated tree would lose -- and ALLOWED_PATHS is what
    actually refuses. Parsing section 7 to derive the regex was rejected: it
    would throw away everything the tree says beyond a path.

    The asymmetry is why this check runs one way. Someone editing ALLOWED_PATHS
    knows they are editing a regex; someone adding a line to section 7 believes
    they have declared the file. That happened twice on 2026-09-19 --
    bridge/README.md in the morning, contracts/quantities.json in the evening
    -- and never once the other way.

    It reads names and the directory each sits under, and nothing else --
    ordering, prose and the reasons the tree carries are not parsed, the
    limitation section 8 records for checks 47, 48, 50 and 51. The first draft
    read names alone, on the reasoning that the tree's shape was not needed;
    rebuilding the real regression in a scratch tree showed it passing, because
    a bare name finds some other directory whose pattern accepts it. A name
    with nowhere to live is not the failure -- a name in the wrong place is.

    What it deliberately does NOT catch, so nobody deletes it expecting more.
    Anything under a placeholder directory -- questions/<qid>/, inbox/<thread>/
    -- because the tree names a shape there and not a path; those subtrees are
    skipped whole rather than resolved against the grandparent, which is what
    the first run did to twenty-odd real files. A file that
    exists and is allowed but sits somewhere section 7 never mentions, which is
    check 13's job from the other side. And whether a declared file exists at
    all: declaring a path and writing it are different acts, and 11-13's whole
    point is that a gap should stay visible rather than be filled to make a
    check quiet.
    """
    text = DESIGN_DOC.read_text(encoding="utf-8") if DESIGN_DOC.exists() else ""
    m = re.search(r"^## 7\..*?^```\n(.*?)^```", text, re.S | re.M)
    if not m:
        return [Finding(55, PENDING, f"{DESIGN_DOC_NAME} has no section 7 tree block to read",
                        DESIGN_DOC_NAME)]

    # Indentation gives the containing directory, and the check needs it. The
    # first draft read a flat set of names and asked whether ALLOWED_PATHS
    # permits each SOMEWHERE -- built the real regression in a scratch tree
    # (quantities.json removed from the regex) and the check passed, because
    # some other directory's pattern accepts a .json of that name. A name with
    # no place is not the failure; a name in the wrong place is.
    paths: set[str] = set()
    stack: list[tuple[int, str | None]] = []
    for line in m.group(1).splitlines():
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        tok = line.strip().split()[0]
        while stack and stack[-1][0] >= indent:
            stack.pop()
        prefix = stack[-1][1] if stack else ""
        placeholder = any(c in tok for c in "<>*{}|")
        if tok.endswith("/"):
            # A placeholder directory pushes None, so its children are skipped
            # too. Without that, a file under questions/<qid>/ resolved to the
            # grandparent and twenty-odd real paths were reported wrong.
            if placeholder or prefix is None:
                stack.append((indent, None))
            else:
                stack.append((indent, "" if tok == "rebuild/" else prefix + tok))
        elif prefix is not None and not placeholder and re.fullmatch(r"[A-Za-z0-9_.\-]+\.[a-z]+", tok):
            paths.add(prefix + tok)

    out: list[Finding] = []
    tested = 0
    for path in sorted(paths):
        if any(re.fullmatch(pat, path) for pat in ALLOWED_PATHS):
            tested += 1
            continue
        out.append(Finding(55, FAIL,
                           f"{DESIGN_DOC_NAME} section 7 puts a file at {path!r} and ALLOWED_PATHS does not allow "
                           "that path, so writing it there would fail check 13. Section 7 is the prose "
                           "of record and ALLOWED_PATHS is what refuses; a line in one is not a "
                           "declaration", DESIGN_DOC_NAME))
    if out:
        return out
    return [Finding(55, PASS, f"{tested} paths section 7 declares are paths ALLOWED_PATHS permits")]


def check_62_computed_grade_derived(b: Bundle) -> list[Finding]:
    """A `computed:` grade should follow from what it was computed from.

    Check 43 already derives an entry's grade from its source KIND, but its
    `computed:` branch only asks whether the declared grade is in ("E4","E5") --
    it never reads the inputs. So E5 passes where 5.3 says E4, and the number
    looks derived while being declared. A grade that looks derived and is not
    is the quietest way to be wrong, because the thing that would catch it is
    the thing that is absent.

    5.3: `computed:` is **max(E4, worst input)**. Worse, not better -- the E4
    floor is a cap on how good arithmetic can make something, and the worst
    input is a cap on how good the chain can be.

    **`inputs` names three different relations, and this check composes over
    exactly one of them.** That is the correction of 2026-09-20; the first
    version of this check composed over all three and got one of them right by
    accident.

      1. FORMAL PARAMETERS of a relation -- `derived_quantity` and
         `dimensionless_group`, which the schema requires to carry a `formula`.
         `bead_diameter` in `bead_diameter**2/diffusivity` is a bound variable,
         not a reference to a value, and **no grade composes from it**: 5.3's
         max(E4, worst input) is a rule about a computed VALUE, and a relation
         composes no numbers. `tau_d` is E4 in a store holding no diameter at
         all. Reported, never derived, never blocked.
      2. QUANTITIES an inference rests on, named so their grades compose.
         `working_distance_is_measured_to_the_coverslip` rests on
         `working_distance` and `coverslip_thickness`, both carried as numbers.
         This is the one shape that composes.
      3. CLAIMS an inference rests on, which carry no numbers to compose. They
         go in `supports`, added to the schema on 2026-09-20 for exactly this,
         and the grade still caps at the worst support -- but only when every
         support is an entry. A premise the store does not hold cannot be
         graded, so one `external` support stops composition and says so.

    **What the accident was**, recorded because it is the argument that
    survives this rewrite: `tau_d` and `tracer_diffusivity_expected` are both
    relations with formulas, and the first version treated them differently --
    derived for one, blocked for the other -- purely because
    `tracer_diffusivity_expected`'s parameter names happen to collide with
    value names the store carries, and `tau_d`'s `bead_diameter` is the
    open_collisions synonym for `tracer_diameter` and collides with nothing.
    Rename one string in a formula and a grade appears. That is option 2 of
    task 020 -- resolving a bare name to whatever entry carries it -- arriving
    through a side door after being refused at the front.

    An input resolves when the store carries that name AND every carrier agrees
    on its grade. Unanimity rather than a unique carrier: six names are carried
    by more than one entry today, all six unanimous, so requiring uniqueness
    would refuse work it has no reason to refuse. And unanimity cannot be
    silent -- divergence is reported rather than resolved one way, which is
    what a unique-carrier rule could not promise.

    **It does not claim WHICH VALUE.** `pixel_size` is carried by twelve
    entries at one grade and twelve different values; this check resolves the
    grade of a name, not its value. Section 8 records that limitation for this
    family of checks.

    Nothing here is a failure or PENDING. Not a failure, because an entry that
    composes no grade is not wrong -- there is nothing to say about it. Not
    PENDING, which means an artifact a later milestone produces: **no milestone
    resolves a symbol.** So it is a count inside the pass, the idiom 15c29b0
    settled for advisory findings. The counts are split by KIND rather than
    gathered under one word, because "blocked" implies waiting and two of these
    shapes are permanent and correct.
    """
    if not KB_DIR.exists() or not (KB_DIR / "entries").exists():
        return [Finding(62, NA, "no knowledge store")]

    FORMULA_KINDS = ("derived_quantity", "dimensionless_group")

    carriers: dict[str, set[str]] = {}
    grade_of: dict[str, str] = {}
    entries = []
    for path in sorted((KB_DIR / "entries").glob("*.json")):
        try:
            e = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        entries.append(e)
        if e.get("entry_id") and e.get("grade"):
            grade_of[e["entry_id"]] = e["grade"]
        for n in e.get("numbers") or []:
            if isinstance(n, dict) and n.get("name") and n.get("grade"):
                carriers.setdefault(n["name"], set()).add(n["grade"])

    out: list[Finding] = []
    derived: list[str] = []
    relations: list[str] = []
    by_claim: list[str] = []
    partly_outside: list[str] = []
    no_basis: list[str] = []
    dangling: list[str] = []
    unresolved: list[str] = []
    divergent: list[str] = []

    def _verdict(eid, worst, e):
        want = f"E{worst}"
        if e.get("grade") != want:
            out.append(Finding(62, FAIL,
                f"{eid} declares {e.get('grade')} and what it rests on gives {want} -- 5.3 makes "
                f"a computed grade max(E4, worst input), and check 43 only checks the range, so "
                f"nothing else would say so", _rel(KB_DIR / "entries" / f"{eid}.json")))
            return False
        return True

    for e in entries:
        if not str(e.get("source") or "").startswith("computed:"):
            continue
        eid = str(e.get("entry_id"))

        # Shape 1. A relation. Its `inputs` are the formula's free variables,
        # and binding them to whatever the store happens to carry under the
        # same string is the move 020 refused.
        if e.get("kind") in FORMULA_KINDS:
            relations.append(eid)
            continue

        sups = e.get("supports")
        ins = e.get("inputs")

        # Shape 3. Supporting claims. They carry no numbers, so the cap comes
        # from each supporting ENTRY's own grade -- and only if the store holds
        # every one of them.
        if sups:
            worst = 4
            outside = False
            broken = None
            for sup in sups:
                if not isinstance(sup, dict):
                    continue
                if sup.get("external"):
                    outside = True
                    continue
                g = grade_of.get(str(sup.get("entry")))
                if g is None:
                    broken = f"{eid} -> {sup.get('entry')}"
                    continue
                worst = max(worst, int(g[1:]))
            if broken:
                # A dangling support is a defect and an external premise is by
                # design, so they get separate words even though both stop the
                # composition. Reported once, under the defect.
                dangling.append(broken)
            elif outside:
                partly_outside.append(eid)
            elif _verdict(eid, worst, e):
                by_claim.append(eid)
            continue

        # Shape 2. Quantities. The only shape whose grade composes by arithmetic.
        if ins is None:
            no_basis.append(eid)
            continue
        worst = 4
        blocked = None
        for name in ins:
            grades = carriers.get(name)
            if not grades:
                blocked = f"{eid}:{name} carried by nothing"
                unresolved.append(blocked)
                break
            if len(grades) > 1:
                blocked = f"{eid}:{name} carried at {sorted(grades)}"
                divergent.append(blocked)
                break
            worst = max(worst, int(sorted(grades)[0][1:]))
        if blocked:
            continue
        if _verdict(eid, worst, e):
            derived.append(eid)

    if out:
        return out

    def phrase(ids, one, many, tail):
        return f"{len(ids)} {one if len(ids) == 1 else many} {tail} ({', '.join(ids[:3])})"

    parts = []
    if derived:
        parts.append(phrase(derived, "computed grade derives", "computed grades derive",
                            "from quantities and matches" if len(derived) == 1
                            else "from quantities and match"))
    if relations:
        parts.append(phrase(relations, "formula entry takes", "formula entries take",
                            "no grade from their inputs, which is correct and permanent -- those "
                            "are parameters of a relation, not references to values"))
    if by_claim:
        parts.append(phrase(by_claim, "entry rests", "entries rest",
                            "on supporting entries and caps at the worst of them"))
    if partly_outside:
        parts.append(phrase(partly_outside, "entry rests", "entries rest",
                            "partly on a premise the store does not hold, so nothing composes"))
    if no_basis:
        parts.append(phrase(no_basis, "entry names", "entries name",
                            "neither `inputs` nor `supports`, so there is nothing to compose over"))
    if dangling:
        parts.append(phrase(dangling, "entry names", "entries name",
                            "a support that is no entry in this store, so nothing composes"))
    if unresolved:
        parts.append(phrase(unresolved, "input names", "inputs name",
                            "a quantity the store does not carry"))
    if divergent:
        parts.append(phrase(divergent, "input names", "inputs name",
                            "a quantity whose carriers disagree"))

    if not parts:
        return [Finding(62, NA, "no entry carries a computed: source")]
    return [Finding(62, PASS, "; ".join(parts))]


def check_64_every_rejected_fixture_is_reached(b: Bundle) -> list[Finding]:
    """Every file under examples/rejected/ is a subject or an input, never neither.

    `--expect-fail` asserts that each fixture CARD fails, which is how a check
    that quietly stopped working gets caught. But it iterates cards and
    artifacts, and the folder holds files that are neither: `bad_md_number.md`
    exists so that `bad_md_number.json` fails check 9, and a group's
    `receiving_agent/CLAUDE.md` exists so the group fails check 50. Those are
    INPUTS. Nothing walks them, so nothing notices a fixture that has stopped
    being a fixture.

    Deleting an input is already caught, because the subject then stops failing
    and --expect-fail says so. What is not caught is an input that is still
    there and no longer does its job, while some OTHER defect in the subject
    keeps it failing -- the fixture passes for the wrong reason, which is the
    shape this repository keeps finding.

    This check cannot tell a live input from a dead one; that would be running
    the fixture, which is --expect-fail's job. What it can say is that every
    file is REACHED: a non-iterated file is accounted for when it shares a stem
    with an iterated file, or sits in a group folder that has an iterated
    member. A file that is neither is dead weight, and dead weight in a
    directory whose whole purpose is to fail is indistinguishable from a test.
    """
    root = CONTRACTS / "examples" / "rejected"
    if not root.exists():
        return [Finding(64, NA, "no rejected fixtures on disk")]
    files = sorted(p for p in root.rglob("*") if p.is_file())
    if not files:
        return [Finding(64, NA, "no rejected fixtures on disk")]

    # What --expect-fail WOULD iterate, not what this run happened to collect.
    # A plain run excludes the rejected tree entirely, so reading b.cards here
    # made every fixture an orphan -- the check asked about this run when the
    # question is about the directory.
    rejected_bundle = collect([root], True)
    subjects = {c.rel for c in (rejected_bundle.cards + rejected_bundle.artifacts)}
    reached, inputs, orphans = [], [], []
    for f in files:
        rel = _rel(f)
        if rel in subjects:
            reached.append(rel)
            continue
        by_stem = any(_rel(s) in subjects for s in f.parent.glob(f.stem + ".*") if s != f)
        group = next((q for q in f.parents if q.name.startswith("check") and q.parent == root), None)
        by_group = bool(group) and any(_rel(m) in subjects for m in group.rglob("*") if m.is_file())
        (inputs if (by_stem or by_group) else orphans).append(rel)

    if orphans:
        return [Finding(64, FAIL,
                        f"{len(orphans)} files under examples/rejected/ are neither iterated by --expect-fail "
                        f"nor an input to something that is ({', '.join(orphans[:3])}). A fixture nothing "
                        "reaches cannot fail, and in this directory that is indistinguishable from one that "
                        "passes", orphans[0])]
    return [Finding(64, PASS,
                    f"{len(reached)} rejected fixtures are iterated and {len(inputs)} are inputs to one")]


def _judge(what: str, src: str, declared, rel, out: list, b, index_grades: dict) -> None:
    """One source string against one declared grade, for an entry or a number in it.

    Lifted out of check 43's entry branch on 2026-09-20 so the two levels
    cannot drift. They had already drifted the only way that matters: the
    number level was not judged at all.
    """
    prefix, ref = src.split(":", 1)
    expected = SOURCE_GRADE.get(prefix, "missing")
    if declared == "E6":
        out.append(Finding(43, FAIL, f"{what}: E6 is a value a model produced and may not enter the store (4.3)", rel))
        return
    if expected == "missing":
        out.append(Finding(43, FAIL, f"{what}: unknown source kind {prefix!r}", rel))
    elif expected is not None:
        if declared != expected:
            out.append(Finding(43, FAIL, f"{what}: source {prefix}: derives {expected}, it says {declared} (self-reported grades fail)", rel))
    elif prefix in ("computed", "simulated"):
        if declared not in ("E4", "E5"):
            out.append(Finding(43, FAIL, f"{what}: {prefix}: is E4 at best and never better, it says {declared}", rel))
        if prefix == "simulated":
            cfg = config_of_run(ref, b)
            if cfg is None:
                out.append(Finding(43, FAIL, f"{what}: source simulated:{ref} but that run's configuration cannot be resolved, so 5.3's independence declaration cannot be read", rel))
            else:
                ok, why = configuration_is_its_own_source(cfg)
                if not ok:
                    out.append(Finding(43, FAIL, f"{what}: a run's reading may not be carried into the store as a standing fact -- {why}", rel))
    elif prefix == "kb":
        if ref not in index_grades:
            out.append(Finding(43, FAIL, f"{what}: cites kb:{ref}, which the index has no grade for to inherit", rel))
        elif declared != index_grades[ref]:
            out.append(Finding(43, FAIL, f"{what}: inherits kb:{ref}, graded {index_grades[ref]} in the store, and says {declared}", rel))


def check_43_entry_grade(b: Bundle) -> list[Finding]:
    """An entry's grade follows from its source kind, the way a card's does (5.3).

    Check 21 derives grades for cards and never looks at the store, and the
    entry schema had no `source` field at all -- so every grade in kb/entries/
    was self-reported, which is the one thing 5.3 forbids on the card side. 4.3
    refuses a separate scale for the librarian because two scales become two
    truths; two derivations of one scale do the same.

    `source` is optional while the store catches up, so entries written before
    the field existed are counted rather than failed. Whatever is present is
    derived, and this check reports how much is not yet covered instead of
    passing as though it were.
    """
    if not KB_DIR.exists():
        return [Finding(43, NA, "no knowledge store")]
    files = sorted((KB_DIR / "entries").glob("*.json"))
    if not files:
        return [Finding(43, NA, "no entries in the store")]

    index_grades: dict[str, str] = {}
    if KB_INDEX is not None:
        index_grades = {k: v.get("grade") for k, v in (KB_INDEX.get("entries") or {}).items()}

    out: list[Finding] = []
    without: list[str] = []
    derived = 0
    numbers_derived = 0
    for p in files:
        try:
            rel = str(p.relative_to(REPO))
        except ValueError:
            rel = str(p)                    # a store outside the repo: a self-test
        try:
            e = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue                        # check 1 reports an unreadable entry
        eid = e.get("entry_id") or p.stem
        declared = e.get("grade")
        if declared == "E6":
            out.append(Finding(43, FAIL, f"{eid}: E6 is a value a model produced and may not enter the store (4.3)", rel))
        # EVERY NUMBER INSIDE THE ENTRY, BY THE SAME RULE. Until 2026-09-20
        # this loop read the entry's own `source` and stopped, so the store
        # had a door: put a run's reading in `numbers[]` and write the ENTRY's
        # source as `literature:`, and it walked in. simulation-3 measured
        # both halves -- entry-level `simulated:` fails, the same string one
        # level down passes -- and three documents said the store was the
        # furthest "nowhere else" a non-independent run's reading could not
        # reach. It was, of the entry's label. Not of the entry.
        #
        # And the wider half, which that probe also exposed: a number here
        # could declare ANY grade from any source. Check 21 derives this for a
        # card's numbers and nothing did it for an entry's, so E1 from a
        # `literature:` source passed.
        for n in e.get("numbers") or []:
            if not isinstance(n, dict):
                continue
            nsrc = str(n.get("source") or "")
            if ":" not in nsrc:
                continue                    # the field is optional while the store catches up
            numbers_derived += 1
            _judge(f"{eid} numbers[{n.get('name')}]", nsrc, n.get("grade"), rel, out, b,
                   index_grades)

        src = str(e.get("source") or "")
        if ":" not in src:
            without.append(eid)
            continue
        derived += 1
        prefix, ref = src.split(":", 1)
        expected = SOURCE_GRADE.get(prefix, "missing")
        if expected == "missing":
            out.append(Finding(43, FAIL, f"{eid}: unknown source kind {prefix!r}", rel))
        elif expected is not None:
            if declared != expected:
                out.append(Finding(43, FAIL, f"{eid}: source {prefix}: derives {expected}, the entry says {declared} (self-reported grades fail)", rel))
        elif prefix in ("computed", "simulated"):
            # the formula is itself an assumption, so a computed value is E4 at
            # best and follows its worst input down (5.3). A run's output is E4
            # at best because the model is -- same rule, different obligation.
            if declared not in ("E4", "E5"):
                out.append(Finding(43, FAIL, f"{eid}: {prefix}: is E4 at best and never better, the entry says {declared}", rel))
            if prefix == "simulated":
                # 5.3: a reading the run's own inputs already fix may be named
                # from the comparison fields of that run's result card and
                # nowhere else. The store is the furthest "nowhere else" there
                # is -- an entry here is the reading offered as a standing fact.
                cfg = config_of_run(ref, b)
                if cfg is None:
                    out.append(Finding(43, FAIL, f"{eid}: source simulated:{ref} but that run's configuration cannot be resolved, so 5.3's independence declaration cannot be read", rel))
                else:
                    ok, why = configuration_is_its_own_source(cfg)
                    if not ok:
                        out.append(Finding(43, FAIL, f"{eid}: a run's reading may not be carried into the store as a standing fact -- {why}", rel))
        elif prefix == "kb":
            if ref not in index_grades:
                out.append(Finding(43, FAIL, f"{eid}: cites kb:{ref}, which the index has no grade for to inherit", rel))
            elif declared != index_grades[ref]:
                out.append(Finding(43, FAIL, f"{eid}: inherits kb:{ref}, graded {index_grades[ref]} in the store, and says {declared}", rel))

    if out:
        return out
    if without:
        shown = ", ".join(sorted(without)[:5])
        more = f" and {len(without) - 5} more" if len(without) > 5 else ""
        return [Finding(43, PENDING, f"{derived} entry grades and {numbers_derived} numbers inside them derive from their source; {len(without)} carry no `source` yet, so those grades are still self-reported ({shown}{more}). The librarian seat fills the field, and then it becomes required")]
    return [Finding(43, PASS, f"{derived} entry grades and {numbers_derived} numbers inside them follow from their source kind")]


def check_44_subject_resolves(b: Bundle) -> list[Finding]:
    """An entry's subject names a registry, and the id has to be in it (4.3.1).

    `subject` exists so a query can reach an entry without already knowing its
    id: before it, 14 of 25 entries were reachable only by an id the caller had
    to learn by reading the staging table first. The field is worth little on
    its own -- a subject nothing resolves is a free string with grammar, and the
    ids it carries were checked by hand when they were written, which is the
    guarantee that rots.

    `quantity` is the weak kind and is checked against a de facto registry: the
    names actually used in numbers[] somewhere. It catches a typo and not much
    else, which is why the schema labels it rather than implying more.
    """
    if not KB_DIR.exists():
        return [Finding(44, NA, "no knowledge store")]
    files = sorted((KB_DIR / "entries").glob("*.json"))
    if not files:
        return [Finding(44, NA, "no entries in the store")]

    devices, dev_rel = _device_table()
    device_ids: set[str] = set()
    if devices:
        for c in devices.get("channels", []) or []:
            if c.get("id"):
                device_ids.add(c["id"])
            for el in c.get("elements", []) or []:
                if isinstance(el, dict) and el.get("id"):
                    device_ids.add(el["id"])
        # Retired rows count. A fact about hardware that was taken out is the
        # one somebody comes back for, and it would have nowhere to point.
        for r in devices.get("retired_rows", []) or []:
            if isinstance(r, dict) and r.get("id"):
                device_ids.add(r["id"])

    paths, path_rel = _optical_path_table()
    config_ids = {c["id"] for c in (paths or {}).get("configurations", []) if c.get("id")}
    observable_ids = set(load_observables())

    # The declared half of the quantity registry, added 2026-09-19. Until then
    # `quantity` was the one subject kind with no declared registry and this
    # check said so. The union is the expand step: a declared id resolves even
    # with no number of that name yet, and a de facto name still resolves while
    # contracts/quantities.json is being populated. The contract step -- drop
    # the de facto half and require declaration -- was written as waiting on
    # task 015, which was then withdrawn: the condition could no longer occur
    # and a comment saying "waits on 015" read as a live block. It waits on
    # nothing now except the registry covering the names in use, and the
    # de facto half is the half that lets an entry be its own registry.
    declared_quantities: set[str] = set()
    _qreg = CONTRACTS / "quantities.json"
    if _qreg.exists():
        try:
            declared_quantities = {q["id"] for q in
                                   json.loads(_qreg.read_text()).get("quantities", [])}
        except (json.JSONDecodeError, KeyError, TypeError):
            declared_quantities = set()
    quantity_names: set[str] = set()
    for c in b.cards:
        if "__unreadable__" in c.data:
            continue
        for n in c.data.get("numbers", []) or []:
            if isinstance(n, dict) and n.get("name"):
                quantity_names.add(n["name"])
    for p in files:
        try:
            e = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        for n in e.get("numbers", []) or []:
            if isinstance(n, dict) and n.get("name"):
                quantity_names.add(n["name"])

    # `sample` resolves against the sample table and NOTHING else -- not the
    # way `quantity` does. `quantity` accepts a name used in numbers[]
    # anywhere, which lets an entry satisfy its own subject; that failed on
    # 2026-09-19 when renaming a number dangled five subjects that had only
    # ever resolved against a number in the same file. The execution seat
    # asked for this distinction explicitly before the wiring existed.
    samples, sam_rel = _sample_table()
    sample_ids: set[str] = set()
    if samples:
        for group in ("instances", "retired_rows"):
            for row in samples.get(group) or []:
                if isinstance(row, dict) and row.get("id"):
                    sample_ids.add(row["id"])

    registries = {"device": (device_ids, dev_rel or "the device table"),
                  "configuration": (config_ids, path_rel or "the optical path table"),
                  "observable": (observable_ids, "contracts/observables.json"),
                  "quantity": (quantity_names | declared_quantities, "the names used in numbers[] or declared in contracts/quantities.json"),
                  "sample": (sample_ids, sam_rel or "the sample table")}

    out: list[Finding] = []
    resolved, without = 0, []
    for p in files:
        try:
            e = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        try:
            rel = str(p.relative_to(REPO))
        except ValueError:
            rel = str(p)
        subjects = e.get("subject") or []
        if not subjects:
            without.append(e.get("entry_id") or p.stem)
            continue
        for s in subjects:
            if not isinstance(s, dict):
                continue                      # check 1 reports the shape
            kind, sid = s.get("kind"), s.get("id")
            known, where = registries.get(kind, (None, ""))
            if known is None:
                out.append(Finding(44, FAIL, f"{e.get('entry_id')}: subject kind {kind!r} has no registry", rel))
            elif not known:
                out.append(Finding(44, PENDING, f"{e.get('entry_id')}: {kind} subjects cannot be checked, {where} is not published yet", rel))
            elif sid not in known:
                out.append(Finding(44, FAIL, f"{e.get('entry_id')}: subject {kind}:{sid!r} is not in {where}. A subject names a registry so that it can be wrong; do not add the id to make this pass", rel))
            else:
                resolved += 1
    if out:
        return out
    tail = f"; {len(without)} entries carry none yet" if without else ""
    return [Finding(44, PASS if resolved else NA, f"{resolved} subjects resolve against their registry{tail}")]


def check_42_check_registry(b: Bundle) -> list[Finding]:
    """A check is registered in three places, and they have to agree.

    plan.md section 8 declares it, a def check_NN_ implements it, and the CHECKS
    list runs it. Twice on 2026-09-17 they disagreed: check 38 was declared and
    not implemented, check 40 implemented and not declared. Either way a number
    in the document pointed at nothing, which is the failure this repository
    calls decoration.
    """
    src = (CONTRACTS / "validate.py").read_text()
    implemented = {int(m) for m in re.findall(r"^def check_(\d+)_", src, re.M)}
    listed_block = re.search(r"^CHECKS = \[(.*?)^\]", src, re.S | re.M)
    listed = {int(m) for m in re.findall(r"check_(\d+)_", listed_block.group(1))} if listed_block else set()

    plan = DESIGN_DOC
    if not plan.exists():
        return [Finding(42, PENDING,
                        f"{DESIGN_DOC_NAME} is not in this tree, so the declarations cannot be read")]
    body = plan.read_text()
    try:
        # Split on the section NUMBER, not its title. This read
        # "## 8. 검증 계층" until 2026-09-20 -- the only Korean literal left in
        # this file -- so check 42 could parse the Korean document and nothing
        # else, and deleting plan_ko.md failed it with "cannot find section 8's
        # check list". A title is translated and renamed; a number is the
        # identifier this repository already treats as load-bearing (11-5).
        # Line 3953 was already doing it this way.
        section = re.split(r"^## 8\.\s", body, maxsplit=1, flags=re.M)[1]
        section = re.split(r"^### 8\.1", section, maxsplit=1, flags=re.M)[0]
    except IndexError:
        return [Finding(42, FAIL, f"cannot find section 8's check list in {DESIGN_DOC_NAME}",
                        DESIGN_DOC_NAME)]
    declared = {int(m) for m in re.findall(r"^(\d+)\. ", section, re.M)}
    # Numbers section 8 records as in progress, with the seat that holds them.
    # A check is agreed, then implemented, then declared, so between the second
    # and third step it exists in code and not in the list. Failing that window
    # would mean declaring first, and then every session is blocked for as long
    # as the implementation takes -- the shape of three outages already. The
    # allowance is deliberately narrow: only these numbers, only one-sided, and
    # reported rather than passed, because a recorded work in progress and a
    # mismatch nobody knows about are different things (section 8).
    in_progress = {int(m): who.strip() for m, _what, who in
                   re.findall(r"^\|\s*(\d+)\s*\|([^|]*)\|([^|]*)\|\s*$", section, re.M)}

    out: list[Finding] = []
    for n, who in sorted(in_progress.items()):
        sides = [name for name, have in (("declared", n in declared), ("implemented", n in implemented)) if have]
        if len(sides) == 1:
            out.append(Finding(42, PENDING, f"check {n} is {sides[0]} and not the other, which section 8 records "
                                            f"as in progress under {who}", DESIGN_DOC_NAME))
        elif not sides:
            out.append(Finding(42, PENDING, f"check {n} is assigned to {who} and neither declared nor implemented",
                               DESIGN_DOC_NAME))

    for label, missing, where in (
        ("declared but not implemented", declared - implemented - set(in_progress), DESIGN_DOC_NAME),
        ("implemented but not declared", implemented - declared - set(in_progress), "contracts/validate.py"),
        ("implemented but never run", implemented - listed, "contracts/validate.py"),
        ("run but not implemented", listed - implemented, "contracts/validate.py"),
    ):
        if missing:
            out.append(Finding(42, FAIL, f"{label}: {sorted(missing)}", where))
    return out or [Finding(42, PASS, f"{len(implemented)} checks are declared, implemented and run")]


def check_40_window_condition(b: Bundle) -> list[Finding]:
    """A window-dependent observable is not one number (5.7).

    When the vocabulary marks an observable window_required, the plan has to
    carry that window as a condition. Without it a short-lag and a long-lag
    result land in one column under one name, and nothing in the record says
    they were different measurements.
    """
    plans = b.of_kind("plan")
    if not plans:
        return [Finding(40, NA, "no plan cards")]
    vocab = load_observables()
    out: list[Finding] = []
    checked = 0
    for c in plans:
        obs = (c.data.get("observable") or {}).get("name")
        entry = vocab.get(obs)
        if entry is None:
            out.append(Finding(40, FAIL, f"observable {obs!r} is not in contracts/observables.json. Not a hold: a "
                                          f"card naming something the vocabulary does not define is a reference to "
                                          f"nothing, and holding it lets a typo through with its window requirement "
                                          f"silently unenforced -- and become a thread waiting on a person at the "
                                          f"bridge. A new observable is entered in the vocabulary first (11-1)", c.rel))
            continue
        if not entry.get("window_required"):
            continue
        checked += 1
        want = entry.get("window_parameter")
        if not want:
            out.append(Finding(40, FAIL, f"the vocabulary marks {obs!r} window_required but names no window_parameter", "contracts/observables.json"))
            continue
        conditions = {d.get("parameter"): d.get("number") for d in c.data.get("conditions", []) or []}
        if want not in conditions:
            out.append(Finding(40, FAIL, f"{obs!r} depends on a window, so the plan must carry {want!r} as a condition (5.7); it carries {sorted(conditions)}", c.rel))
            continue
        if conditions[want] not in c.numbers():
            out.append(Finding(40, FAIL, f"condition {want!r} points at {conditions[want]!r}, which is not in numbers[]", c.rel))
    return out or [Finding(40, PASS, f"{checked} plans carry the window their observable depends on")]


def check_48_registry_grants(b: Bundle) -> list[Finding]:
    """A `paths` entry that cannot grant is dead letter (6.2.1).

    seats.json narrows; it does not grant. Check 41 classifies a path first,
    refuses it when that category is not in the seat's `owns`, and only then
    narrows by `paths`. So a path listed for a seat whose `owns` does not cover
    its category reads as a grant in the registry and is refused at the gate,
    with nothing saying the two disagree. That is what bridge/README.md was for
    half of 2026-09-19: listed, classified as the agent's, refused, and the
    registry looked correct the whole time.

    Two copies of one fact with nothing comparing them is what 11-11 counts.
    This is the comparison.
    """
    reg = load_seats()
    if not reg:
        return [Finding(48, PENDING, "contracts/seats.json is absent, so there is nothing to compare")]
    out: list[Finding] = []
    checked = 0
    for seat in reg.get("seats", []):
        owns = set(seat.get("owns", []))
        for path in seat.get("paths") or []:
            checked += 1
            where = seat_boundary_of(path)
            if where not in owns:
                out.append(Finding(48, FAIL, f"seat {seat.get('seat')!r} lists {path!r}, which counts as "
                                             f"{where!r} and not as anything it owns ({sorted(owns)}). A paths "
                                             f"entry that cannot grant is dead letter: the registry reads as a "
                                             f"grant and check 41 refuses it (6.2.1)", "contracts/seats.json"))
    return out or [Finding(48, PASS, f"{checked} registry paths fall inside a category their seat owns")]


def check_46_vocabulary_pin(b: Bundle) -> list[Finding]:
    """A result's estimator pin has to be readable back (5.1, 11-1).

    `estimation.vocabulary_version` says which version of the vocabulary the run
    followed, and that is what lets `comparable` mean the same estimator ran on
    both sides. A pin nobody can resolve says nothing: a version that was never
    committed hashes a working tree, and there is nowhere to read it back from.
    The librarian's server says the same about a kb_version it cannot serve.

    Resolvable means the current derivation, or a commit where the vocabulary
    stood at that content. Older is normal -- a result records what it ran
    against, and the vocabulary grows one entry at a time.
    """
    pinned = [(c, (c.data.get("estimation") or {}).get("vocabulary_version")) for c in b.of_kind("result")]
    pinned = [(c, v) for c, v in pinned if v]
    if not pinned:
        return [Finding(46, NA, "no result pins a vocabulary version")]

    known = {vocabulary_version()}
    import subprocess

    def git(*args: str) -> str:
        return subprocess.run(["git", "-C", str(GIT_REPO), *args],
                              capture_output=True, text=True, check=True).stdout

    try:
        shas = [x for x in git("log", "--format=%H", "--", "contracts/observables.json").splitlines() if x.strip()]
        for sha in shas:
            known.add(vocabulary_version_of(git("show", f"{sha}:contracts/observables.json")))
    except (OSError, subprocess.CalledProcessError):
        return [Finding(46, PENDING, "git history is not readable here, so only the current version can be resolved")]

    out = [Finding(46, FAIL, f"estimation pins {v}, which is not the vocabulary now and stood at no commit. A "
                             f"version that was never committed hashes a working tree, and there is nowhere to "
                             f"read back what estimator it declared", c.rel)
           for c, v in pinned if v not in known]
    return out or [Finding(46, PASS, f"{len(pinned)} results pin a vocabulary version that resolves, "
                                     f"out of {len(known)} the history holds")]


def check_41_seat_attribution(b: Bundle, commit_range: str | None = None, staged: bool = False) -> list[Finding]:
    """A commit says which seat made it (6.2.1).

    git records no session, so a seat declares itself: the committer identity is
    the seat and the author stays the person. Check 35 counts boundaries and so
    passes a commit that stays inside one -- the wrong one. This check knows
    which one is the committer's.

    It cannot separate two sessions that share an identity. Two design seats
    both answer to the root, so they need two entries here with `paths`
    divided; until that is filled the registry says so rather than implying a
    protection it does not give.
    """
    reg = load_seats()
    if not reg:
        return [Finding(41, PENDING, "contracts/seats.json is absent; no seat has an identity")]
    if not commit_range and not staged:
        return [Finding(41, PENDING, "pass --commit-range or --staged; the pre-commit hook passes --staged (6.2.1)")]

    import subprocess

    def git(*args: str) -> str:
        return subprocess.run(["git", "-C", str(GIT_REPO), *args],
                              capture_output=True, text=True, check=True).stdout

    def seats_at(ref: str) -> dict:
        """The registry as it stood at `ref`.

        A commit is judged against the boundaries that existed when it was
        made, not today's. Otherwise moving a path between seats turns old
        history red, and a sweep that reddens whenever a boundary moves is a
        sweep nobody runs. The question this check asks is whether a seat was
        inside its boundary *then* (6.2.1, section 8).

        The parent's registry, not the commit's own: read from its own tree, a
        commit that widens a seat is judged by the widening it just made. Read
        from the parent, widening seats.json has to be a legitimate commit by
        whoever owns that file, and the new boundary takes effect from the next
        commit on. A merge takes its first parent; a root commit has none and
        falls back to its own tree.
        """
        try:
            return json.loads(git("show", f"{ref}:contracts/seats.json"))
        except (OSError, subprocess.CalledProcessError, json.JSONDecodeError):
            return {}

    def judge(email: str, paths: list[str], label: str = "", merge: bool = False,
              reg: dict | None = None) -> list[Finding]:
        reg = reg if reg is not None else load_seats()
        by_email = {s["committer_email"]: s for s in reg.get("seats", [])}
        unknown_status = FAIL if reg.get("unknown_committer") == "refuse" else PENDING
        pre = f"{label}: " if label else ""
        if not reg:
            return [Finding(41, PENDING, f"{pre}contracts/seats.json did not exist yet, so these "
                                         f"{len(paths)} paths carry no attribution")]
        seat = by_email.get(email)
        if seat is None:
            # On a plain commit, report is partial coverage: check 35 still
            # counts boundaries and the paths are visible. On a merge it is zero
            # coverage -- check 35 does not decompose merges by design (6.2.1),
            # so with no attribution nothing looks at what the merge itself
            # contributed. The same policy means two different things, so the
            # default splits. A person merging adopts human@seat.invalid for the
            # one line it costs; merges are far rarer than commits.
            if merge:
                return [Finding(41, FAIL,
                                f"{pre}a merge by {email!r}, which is not a seat in contracts/seats.json: "
                                f"check 35 does not read merges, so these {len(paths)} paths the merge "
                                f"contributed would be checked by nothing (6.2.1)")]
            # Name them. A count is unactionable here in a way it is not
            # elsewhere: for every other finding the path is in the finding,
            # and this is the one case where nothing downstream will ever
            # look -- check 35 still counts boundaries, but no seat owns
            # these paths, so no later sweep attributes them. "17 paths carry
            # no attribution" tells a reader that something is wrong and not
            # what. Capped, because an unattributed merge of a long branch
            # would otherwise print a screenful.
            shown = ", ".join(sorted(paths)[:8])
            more = f", and {len(paths) - 8} more" if len(paths) > 8 else ""
            return [Finding(41, unknown_status,
                            f"{pre}committer {email!r} is not a seat in contracts/seats.json, so these "
                            f"{len(paths)} paths carry no attribution: {shown}{more}")]
        owns, narrow = set(seat.get("owns", [])), seat.get("paths")
        # excludes subtracts from whatever owns and paths grant. It exists so a
        # tier cannot hold the file that says what it may touch: a manager able
        # to edit its own `paths` has no boundary, only a preference (6.2.1).
        excludes = seat.get("excludes") or []
        out: list[Finding] = []
        for path in paths:
            where = seat_boundary_of(path)
            hit = next((x for x in excludes if path.startswith(x)), None)
            if where not in owns:
                out.append(Finding(41, FAIL, f"{pre}seat {seat['seat']!r} owns {sorted(owns)}; this path is "
                                             f"{where}'s (6.2.1)", path))
            elif hit is not None:
                out.append(Finding(41, FAIL, f"{pre}seat {seat['seat']!r} is excluded from {hit!r}; another seat "
                                             f"owns it so that this one cannot widen itself (6.2.1)", path))
            elif narrow and not any(path.startswith(x) for x in narrow):
                out.append(Finding(41, FAIL, f"{pre}seat {seat['seat']!r} is narrowed to {narrow}, which does "
                                             f"not cover this path (6.2.1)", path))
        return out

    if staged:
        ident = git("var", "GIT_COMMITTER_IDENT")
        m = re.search(r"<([^>]*)>", ident)
        paths = [x for x in git("diff", "--cached", "--name-only").splitlines() if x.strip()]
        if not paths:
            return [Finding(41, NA, "nothing staged")]
        email = m.group(1) if m else ""
        staged_reg = seats_at("HEAD")
        out = judge(email, paths, reg=staged_reg)
        seat = next((s for s in staged_reg.get("seats", []) if s.get("committer_email") == email), None)
        return out or [Finding(41, PASS, f"the staged set is {(seat or {}).get('seat')!r}'s "
                                         f"({len(paths)} paths)")]

    # Per commit, for the same reason check 35 is: a range holds several seats'
    # commits, and aggregating them would fail a history that is well behaved.
    try:
        rows = [x for x in git("log", "--reverse", "--format=%H%x00%ce%x00%P", commit_range or "").splitlines() if x.strip()]
    except (OSError, subprocess.CalledProcessError) as exc:
        return [Finding(41, FAIL, f"cannot read commit range {commit_range!r}: {exc}")]
    if not rows:
        return [Finding(41, NA, f"no commits in {commit_range}")]
    out, clean, quiet_merges = [], 0, 0
    for row in rows:
        sha, ce, parents = (row.split("\x00") + ["", ""])[:3]
        # A merge is read with --cc: what belongs to the merging seat is what
        # is in no parent, which is a conflict resolution or an edit slipped in
        # while merging (6.2.1). Plain -r prints nothing for a merge, so
        # skipping on an empty list let exactly that edit through unattributed.
        merge = len(parents.split()) > 1
        shape = ["--cc"] if merge else ["-r"]
        paths = [x for x in git("diff-tree", "--no-commit-id", "--name-only", *shape, sha).splitlines() if x.strip()]
        if not paths:
            # A clean merge contributes nothing, so there is nothing to
            # attribute. That is an answer, not a gap.
            quiet_merges += 1 if merge else 0
            continue
        base = f"{sha}^" if parents.split() else sha
        found = judge(ce, paths, sha[:7], merge, seats_at(base))
        if found and before_enforcement(sha):
            found = [Finding(41, PENDING if f.status == FAIL else f.status,
                             f.message + (f" -- {WAS_CONVENTION}" if f.status == FAIL else ""), f.path)
                     for f in found]
        out.extend(found) if found else None
        clean += 0 if found else 1
    if out:
        return out
    tail = f", and {quiet_merges} merges contributed nothing of their own" if quiet_merges else ""
    return [Finding(41, PASS, f"{clean} commits stay inside the seat that made them{tail}")]


def check_45_undegraded_is_backed_by_the_log(b: Bundle) -> list[Finding]:
    """A card claiming the librarian answered has a line in the query log.

    `degraded: ["librarian_agent"]` is the honest value while the service is
    unreachable, and its absence is a positive claim: this question was put to
    the service and the service answered. Until now nothing anywhere compared
    that claim to the one record that would show it. The claim is cheap to make
    by accident -- an executing agent that reads kb/ by hand gets the same
    numbers and writes the same card, and 3.0 draws its line between reading
    the files and the service answering exactly because those look identical
    from inside the card.

    WHAT THIS DOES NOT ESTABLISH, and 9.1 was corrected on 2026-09-19 to say
    so: the log CARRIES the claim, it does not VERIFY it. `caller_id` is an
    argument the caller supplies and the server cannot see the identity behind
    it, so a line proves a call was made under that id, never that this seat
    made it. Corroboration, not proof. What it forecloses is the case with no
    line at all, where nothing was asked and the card says otherwise.

    The migration window is honoured rather than assumed away. 4.3.1 put the
    revision into `caller_id` on 2026-09-18 and the form without it is accepted
    while cards migrate, so a card whose id matches the log only once the
    `:v<N>:` is removed is reported rather than failed -- the call happened and
    the id was renamed afterwards. That becomes a failure when the pattern
    tightens, which is the point at which it should.
    """
    log = REPO / "librarian_agent" / "queries" / "log.jsonl"
    if not log.exists():
        return [Finding(45, PENDING, "librarian_agent/queries/log.jsonl is not in this tree, so a claim "
                                     "that the service answered has nothing to be compared against")]
    logged: set[str] = set()
    for line in log.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            cid = json.loads(line).get("caller_id")
        except json.JSONDecodeError:
            continue
        if cid:
            logged.add(cid)
    unrevised = {re.sub(r":v\d+:", ":", c, count=1) for c in logged}

    out: list[Finding] = []
    backed, degraded = 0, 0
    for c in b.cards:
        if "__unreadable__" in c.data:
            continue
        cid = c.data.get("caller_id")
        if not cid:
            continue
        if any("librarian" in str(d) for d in c.data.get("degraded") or []):
            degraded += 1
            continue
        if cid in logged:
            backed += 1
        elif re.sub(r":v\d+:", ":", cid, count=1) in unrevised:
            out.append(Finding(45, PENDING,
                f"{cid!r} is not in the query log, but the log holds it without its revision -- the call "
                "happened and the id was renamed afterwards, which 4.3.1 accepts while cards migrate. "
                "This becomes a failure when the pattern tightens", c.rel))
        else:
            out.append(Finding(45, FAIL,
                f"claims the librarian answered -- `degraded` does not name it -- but the query log holds "
                f"no call under {cid!r}. Either the service was never reached, in which case `degraded` "
                'should say ["librarian_agent"] (3.1 rule 2), or the id was chosen rather than issued '
                "(4.3.1). The log corroborates a claim and cannot verify one, so this is the weaker "
                "direction only: no line at all", c.rel))
    if out:
        return out
    if backed == 0:
        return [Finding(45, NA, f"no card claims the librarian answered; {degraded} are on the degraded path")]
    return [Finding(45, PASS, f"{backed} cards claim the service answered and the log carries a call for "
                              f"each; {degraded} others say degraded and are out of scope")]


def check_47_registry_prose_names_real_seats(b: Bundle) -> list[Finding]:
    """A seat name cited in seats.json's prose resolves to a seat in it.

    The registry decides who may commit what, and its prose does real work: the
    `growth` note prescribes the identity a second session takes, and a seat's
    own `note` says which identity that session holds. On 2026-09-18 one of
    those named `seat/simulation-1`, which was never registered and whose
    branch no longer existed, so a dangling name was deciding who may commit.
    It survived because prose is not data -- nothing read it but people.

    This is 11-11's shape at one remove. There the same fact lived in two
    places and they drifted; here a name lives in prose and the thing it names
    lives in the list, and only the list is maintained. `growth` records the
    other half already: its example said `microscope-2`, that identity was
    spent on an A/B variant and deferred, and the next microscope session
    arrived at exactly the question the example was supposed to answer.

    A HISTORICAL CITATION IS NOT A DEFECT, and the fix to simulation-1 is the
    proof: correcting the note meant writing the dead name down and saying it
    was never real. Reads a declaration and not comprehension; section 8 states
    that limit for the kind. So it does not guess. A name the registry lists in
    `retired_names` is a citation; one it does not is a dangler. Recording it
    is the registry owner's call, which is the architecture seat's: this check
    reports until the key exists and refuses after, so the first entry arms it
    rather than a second seat having to be told.
    """
    raw = load_seats()
    if not raw:
        return [Finding(47, PENDING, "contracts/seats.json is not in this tree")]
    names = {s.get("seat") for s in raw.get("seats", [])}
    retired = raw.get("retired_names")

    # Prose is every string that is not one of the fields the checks read as
    # data. Reading the data fields too would flag `paths` and `excludes`,
    # which name directories and not seats.
    STRUCTURAL = {"seat", "committer_email", "owns", "paths", "excludes", "enforced_from"}

    def prose(node, key: str = ""):
        if isinstance(node, dict):
            for k, v in node.items():
                if k not in STRUCTURAL:
                    yield from prose(v, k)
        elif isinstance(node, list):
            for v in node:
                yield from prose(v, key)
        elif isinstance(node, str):
            yield key, node

    dangling: list[tuple[str, str]] = []
    cited = 0
    for key, text in prose(raw):
        for n in set(re.findall(r"([A-Za-z0-9_-]+)@seat\.invalid", text)) | set(
                 re.findall(r"seat/([A-Za-z0-9_-]+)", text)):
            if n in names:
                cited += 1
            elif retired is not None and n in retired:
                cited += 1
            else:
                dangling.append((key, n))
    if not dangling:
        return [Finding(47, PASS, f"{cited} seat names cited in the registry's prose all resolve",
                        "contracts/seats.json")]
    if retired is None:
        return [Finding(47, PENDING,
            f"the registry's prose names {sorted({n for _, n in dangling})} under "
            f"{sorted({k for k, _ in dangling})}, and no seat by those names exists. Whether each is a "
            "dangling reference or a deliberate citation of a dead name is the registry owner's call "
            "(architecture): add a top-level `retired_names` listing the citations, and this check "
            "refuses the rest from then on", "contracts/seats.json")]
    return [Finding(47, FAIL,
        f"the registry's prose names {sorted({n for _, n in dangling})} under "
        f"{sorted({k for k, _ in dangling})}; no seat by those names exists and `retired_names` does not "
        "list them. Prose here decides who may commit, so a name that resolves to nothing is an "
        "instruction that cannot be followed", "contracts/seats.json")]


def check_56_undecided_names_the_settled_unit(b: Bundle) -> list[Finding]:
    """Check 3's open threshold reports distinct rationales, not raw E5.

    11-2 settled the unit on 2026-09-19 and left the threshold open, which is
    an unusual state to be in and the reason this check exists: for as long as
    a cap is unset, the UNDECIDED line is the only place the repository says
    what would be capped. It is read far more often than 11-2 is. While it said
    `counted E5 = [7, 5, 17]` it was teaching the unit that had just been
    rejected -- and a message pointing at the wrong thing is believed, which
    this repository has now counted several times.

    Why the unit moved is worth having here rather than one file away. A
    computed E5 almost always inherits: of one plan's 17, nine were computed
    and every one of them took E5 from an assumed input, none asserting it
    alone (5.8). So the raw count measures derivation length. Capping it would
    reward dropping `formula` and `inputs` -- the fields check 17 reads -- and
    that is worse than a bypassed gate, because a bypass leaves a trace and a
    hidden derivation leaves a green card.

    WHAT THE UNIT DOES NOT MEASURE, and the declaration says so too: a
    rationale count counts how many times a guess was made, never how much
    weight one carries. A single rationale holding up an entire plan counts as
    one. That is the price of not counting chain length, and leaving it unsaid
    would let a pass read as "this plan assumes little".

    The check compares numbers rather than wording. It recomputes the counts
    and requires each to appear against its plan, so reverting the unit fails
    it even if the sentence still says `rationale`.
    """
    plans = [c for c in b.cards if c.kind == "plan" and "__unreadable__" not in c.data]
    if not plans:
        return [Finding(56, NA, "no plan cards to count")]
    expect: dict[str, int] = {}
    for c in plans:
        rats = {str(n.get("source", "")).split(":", 1)[1]
                for n in c.data.get("numbers", []) or []
                if n.get("grade") == "E5" and str(n.get("source", "")).startswith("assumed:")}
        expect[c.rel] = len(rats)

    undecided = [f for f in check_03_source_and_grade(b) if f.status == UNDECIDED]
    if not undecided:
        return [Finding(56, NA, "check 3 reports no open threshold, so a cap is set and there is no "
                                "UNDECIDED line to teach a unit")]
    msg = " ".join(f.message for f in undecided)
    if "rationale" not in msg:
        return [Finding(56, FAIL, "check 3's UNDECIDED line never says what it counts. While the threshold "
                                  "is open this line is the only place the repository states the unit "
                                  "(11-2)", "contracts/validate.py")]
    wrong = [f"{rel}: {n}" for rel, n in sorted(expect.items()) if f"{rel}: {n}" not in msg]
    if wrong:
        return [Finding(56, FAIL, f"check 3's UNDECIDED line does not report the distinct-rationale count "
                                  f"for {len(wrong)} plan(s) -- expected {wrong[0]!r}. 11-2 settled the unit "
                                  f"as distinct rationales; a line reporting raw E5 teaches the unit that "
                                  f"was rejected, and whoever sets the threshold reads this line and not "
                                  f"11-2", "contracts/validate.py")]
    return [Finding(56, PASS, f"check 3's open threshold reports distinct rationales for {len(expect)} plans, "
                              f"which is 11-2's settled unit")]


def check_57_irreversible_rests_on_a_confirmed_limit(b: Bundle) -> list[Finding]:
    """An irreversible action is bounded by a limit a person actually checked.

    4.6.6.1 rule 3 settled the boundary this sits on. Two channels take
    commands and report nothing back, and the person chose to automate them
    with the blind spot recorded rather than to refuse them -- so a command
    goes out, nothing treats that channel's state as confirmed, and the run
    log carries `verification: none`. The third bullet is this check:
    **an irreversible action still requires a confirmed limit.** Being able to
    command the trap is not being able to confirm it is off.

    So `carried_over` is not confirmation here. It is legal in the envelope --
    forbidding it would mean confirming every ceiling before the file can
    exist, and then nobody starts the file -- and that licence stops at the
    actions that cannot be undone. `physical` carries who, when and how, and
    only that clears an irreversible action.

    WHAT IT DOES NOT COVER. A limit can be confirmed while compliance with it
    is unverifiable: `optical_power_max` is `physical` today and the channels
    it bounds are `read_back: false`, so nothing reads back whether the limit
    held. That is a different failure and 4.6.6.1 puts it on the run log's
    `verification` field, not here. Folding it in would make one check carry
    two rules.

    Reversibility and the parameter list come from check 22's reading of
    `actions[]`, not from a second notion of irreversible (11-11).
    """
    plans = [c for c in b.of_kind("plan") if "__unreadable__" not in c.data]
    if not plans:
        return [Finding(57, NA, "no plan cards")]

    envelopes: dict[str, dict] = {}
    for env in envelope_files():
        try:
            doc = json.loads(env.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        limits: dict[str, dict] = {}
        for tgt in doc.get("targets", []) or []:
            for name, lim in (tgt.get("limits") or {}).items():
                if not isinstance(lim, dict):
                    continue
                # A budget limit carries `chosen_by` and never `confirmation`:
                # P0 rule 7 binds safety.* only (4.6.6.1, plan.md 7). Recorded
                # here rather than skipped, so an irreversible action bounded
                # only by a budget fails this check instead of passing it by
                # being unseen. The simulation tree has no irreversible action
                # today; that is a fact about today and not about the rule.
                if "confirmation" in lim or "chosen_by" in lim:
                    limits[name] = lim
        envelopes[env.parent.parent.name] = limits

    out: list[Finding] = []
    cleared = ungoverned = 0
    for c in plans:
        agent = c.data.get("author")
        limits = envelopes.get(str(agent))
        for a in c.data.get("actions", []) or []:
            if a.get("reversible"):
                continue
            for param in a.get("parameters", []) or []:
                if limits is None:
                    ungoverned += 1
                    continue
                # A limit is named for the quantity it bounds: <quantity>_max
                # or <quantity>_min, which is how envelope_safety.schema.json
                # names all six of them.
                lim = limits.get(f"{param}_max") or limits.get(f"{param}_min")
                if lim is None:
                    ungoverned += 1
                    continue
                kind = (lim.get("confirmation") or {}).get("kind")
                if kind == "physical":
                    cleared += 1
                else:
                    out.append(Finding(57, FAIL,
                        f"action {a.get('id')!r} is irreversible and rests on {param!r}, whose limit is "
                        f"confirmed as {kind!r} -- carried from another document and not checked here. "
                        f"4.6.6.1 rule 3: an irreversible action requires a confirmed limit, and "
                        f"carried_over's licence stops at what cannot be undone (2.1 rule 7)", c.rel))
    if out:
        return out
    if ungoverned and not cleared:
        # Expand, migrate, contract. The envelopes are days old and carry the
        # two limits P0 ranks highest, not yet the ones these actions rest on.
        # Failing now would refuse work that could not have been done, which
        # is the deadlock that makes a gate something to go around; this flips
        # itself the moment any irreversible parameter gains a limit.
        return [Finding(57, PENDING, f"{ungoverned} irreversible parameters have no limit in their agent's "
                                     f"envelope yet, so there is no confirmation to read. This becomes a "
                                     f"failure once any of them is bounded")]
    if not cleared and not ungoverned:
        return [Finding(57, NA, "no irreversible actions")]
    return [Finding(57, PASS, f"{cleared} irreversible parameters rest on limits a person physically "
                              f"confirmed; {ungoverned} are not bounded by the envelope yet")]


def check_50_delivery_has_a_reader(b: Bundle) -> list[Finding]:
    """A delivered envelope has a receiver with a reason to read it.

    The delivery path and a seat that knows the path exists are two facts, and
    on 2026-09-19 only the first was written down. Round 1 of
    thr-tracer-diffusivity-001 was delivered into microscope_agent/inbox/
    correctly -- checks 8, 13 and 41 all passed on it, the payload hash
    recomputed -- and the receiving seat had no reason to look: neither its
    standing orders nor any of its six task cards contained the word. It read
    the round only because one session told another in chat. That notification
    worked and left no record, which is the 6.2 rule 2 shape: if the session
    resets, nothing on disk says a round is waiting.

    The check is on the delivery, not on the tree. It refuses the bridge for
    delivering into a tree that cannot receive, rather than refusing an agent
    for the contents of a file it does not own -- get that backwards and the
    seat that cannot fix the problem is the one that is blocked.

    Reads a declaration and not comprehension; section 8 states that limit
    once, for this kind.
    What it forecloses is the case that actually happened, where the word is
    absent altogether.
    """
    delivered = [c for c in b.of_kind("ask_simulation", "ask_experiment") if "/inbox/" in c.rel]
    if not delivered:
        return [Finding(50, NA, "nothing has been delivered")]

    out: list[Finding] = []
    for c in delivered:
        agent = c.rel.split("/inbox/")[0]
        orders = REPO / agent / "CLAUDE.md"
        if not orders.exists():
            out.append(Finding(50, FAIL, f"delivered into {agent}/, which has no CLAUDE.md -- there is no seat "
                                         f"here to have been told anything (7.1 rule 8)", c.rel))
        elif "inbox/" not in orders.read_text():
            out.append(Finding(50, FAIL, f"{agent}/CLAUDE.md never names the inbox, so this envelope is a dead "
                                         f"letter: delivered, valid, and addressed to a seat with no reason to "
                                         f"look. The bridge may not deliver into a tree that cannot receive "
                                         f"(7.1 rule 8); the section belongs to that agent's manager",
                               c.rel))
    if out:
        return out
    agents = sorted({c.rel.split("/inbox/")[0] for c in delivered})
    return [Finding(50, PASS, f"{len(delivered)} delivered envelopes, in {len(agents)} trees whose standing "
                              f"orders name the inbox")]


def check_51_open_question_has_a_home(b: Bundle) -> list[Finding]:
    """A held thread's open question resolves to a place the answer is recorded.

    `held` means a gate could not be resolved and a person has to resolve it
    (4.4). The person is not in this repository, so the only thing carrying the
    question to them is the place it is written down -- and on 2026-09-19 the
    first real hold named plan.md 11 as that place while 11 held no such entry.
    The field said so honestly, which is better than lying and is still a
    declaration whose other end nobody reads: the same shape as an inbox with
    no reader (check 50) and a registry path no boundary grants (check 48).

    Two halves, and the schema enforced neither. Its description already says
    open_question is "required when state is held", with no conditional under
    it -- a rule stated in prose beside the mechanism that was supposed to hold
    it. So this check requires the field on a held thread, and requires the
    reference in it to name a section 11 item that exists.

    Reads a declaration and not comprehension; section 8 states that limit
    once, for this kind.
    """
    held = [a for a in b.of_artifact("thread_status") if a.data.get("state") == "held"]
    if not held:
        return [Finding(51, NA, "no thread is held")]

    plan = DESIGN_DOC
    if not plan.exists():
        return [Finding(51, PENDING,
                        f"{DESIGN_DOC_NAME} is not in this tree, so the homes cannot be read")]
    try:
        section = plan.read_text().split("## 11.")[1].split("## 12.")[0]
    except IndexError:
        return [Finding(51, FAIL, f"cannot find section 11 in {DESIGN_DOC_NAME}", DESIGN_DOC_NAME)]
    recorded = {int(m) for m in re.findall(r"^(\d+)\. ", section, re.M)}

    out: list[Finding] = []
    for a in held:
        q = (a.data.get("open_question") or "").strip()
        if not q:
            out.append(Finding(51, FAIL, "held with no open_question. Held means a person has to resolve it, and "
                                         "a question nobody wrote down reaches no person (4.4). The schema says "
                                         "this field is required when held and nothing enforced it", a.rel))
            continue
        cited = {int(m) for m in re.findall(r"\b11-(\d+)\b", q)}
        missing = sorted(cited - recorded)
        if not cited:
            out.append(Finding(51, FAIL, "the open question names no recorded home. It has to say where the "
                                         f"answer gets written, as `{DESIGN_DOC_NAME} 11-<n>`, or the only record of the "
                                         "question is this ledger and nobody is obliged to read it", a.rel))
        elif missing:
            out.append(Finding(51, FAIL, f"names {DESIGN_DOC_NAME} 11-{missing[0]}, which section 11 does not have. A "
                                         f"question pointed at an entry that does not exist is not recorded, and "
                                         f"reads as though it were", a.rel))
    if out:
        return out
    return [Finding(51, PASS, f"{len(held)} held threads name a section 11 entry that exists")]


def check_52_target_is_a_decision(b: Bundle) -> list[Finding]:
    """A target is a decision, so it is not also a graded number -- and a
    carried copy still says what the goal said.

    Carried inline in `targets[]` with no source and no grade, the way a
    ceiling lives in envelope/safety.json: a grade says how far a claim can be
    trusted, and a decision is correct by being made (5.3.1). The slot makes a
    grade inexpressible rather than merely absent (c8ee7b3), which is the
    difference between a chokepoint and an opt-in guard.

    Written against shapes rather than names. A name rule would refuse
    `target_relative_error`, which is an axis's *derived* statistical
    requirement -- a claim about what the statistics need, graded and sourced
    like any other. The split runs between the person's decision and
    everything computed from it, not between names beginning with target.

    Two things this check inherited when the target left `numbers[]`, both
    because the commit that opens a hole closes it.

    The unit. A numbers[] entry has its unit checked by check 2; an inline
    target does not. Today they are all `count`, and a target is exactly the
    field someone writes `%` or `decades` into, neither of which is
    registered.

    The comparison. Check 12 made a plan's carried number cite the goal's, so
    drift was impossible. A plan carries the target because a plan_approval
    fixes the plan and not the goal: a plan that pointed at the goal's target
    would have its accuracy move after approval with nothing recording that it
    had -- the same defect kb_version pinning exists to prevent, since a pin
    that resolves to whatever the source says now is not a pin. Carrying is
    right and uncompared carrying is not, so the copy is checked here.

    Reads a declaration and not comprehension; section 8 states that limit
    once, for this kind.
    """
    carriers = [c for c in b.cards if c.data.get("targets")]
    if not carriers:
        return [Finding(52, NA, "no card states a target")]

    goals = {c.data.get("qid"): c for c in b.of_kind("goal")}

    def stated(goal: Card, metric: str):
        """The goal's target for this metric, in whichever shape it is in."""
        named = {n.get("name"): n for n in goal.data.get("numbers", []) or []}
        for t in goal.data.get("targets", []) or []:
            if t.get("metric") != metric:
                continue
            if "value" in t:
                return (t["kind"], t["value"], t["unit"])
            n = named.get(t.get("number"))
            if n:
                return (t["kind"], n.get("value"), n.get("unit"))
        return None

    out: list[Finding] = []
    n_inline = n_legacy = n_carried = 0
    for c in carriers:
        inline = [t for t in c.data["targets"] if "value" in t]
        legacy = [t for t in c.data["targets"] if "number" in t]
        named = {n.get("name") for n in c.data.get("numbers", []) or []}
        n_inline += len(inline)
        n_legacy += len(legacy)

        for t in inline:
            entry = unit_entry(t["unit"])
            if entry is None:
                out.append(Finding(52, FAIL, f"the target on {t['metric']!r} is in {t['unit']!r}, which "
                                             f"units.json does not define. Leaving numbers[] took its unit out "
                                             f"of check 2's reach, so this is the only thing looking", c.rel))
            elif entry.get("si_factor") is None:
                out.append(Finding(52, FAIL, f"the target on {t['metric']!r} is in {t['unit']!r}, which has no "
                                             f"fixed SI factor, so nothing can be compared against it", c.rel))

        for t in legacy:
            if t["number"] not in named:
                out.append(Finding(52, FAIL, f"the target on {t['metric']!r} names the number "
                                             f"{t['number']!r}, which this card does not carry. A target "
                                             f"pointing at nothing states no target", c.rel))

        for metric in sorted({t["metric"] for t in inline} & {t["metric"] for t in legacy}):
            out.append(Finding(52, FAIL, f"{metric!r} carries a target in both shapes: inline, where a grade "
                                         f"cannot be written, and by reference into numbers[], where P2 makes "
                                         f"one mandatory. That is the same decision recorded twice with only "
                                         f"one copy graded (11-11), and the graded copy is the wrong one",
                               c.rel))

        if c.kind == "goal":
            continue
        goal = goals.get(c.data.get("qid"))
        if goal is None:
            out.append(Finding(52, FAIL, f"carries a target and no goal for {c.data.get('qid')!r} is in this "
                                         f"tree, so nothing can say the copy still says what was decided", c.rel))
            continue
        for t in inline:
            n_carried += 1
            was = stated(goal, t["metric"])
            if was is None:
                out.append(Finding(52, FAIL, f"carries a target on {t['metric']!r} that {goal.rel} does not "
                                             f"state. A carried decision nobody made is not a decision", c.rel))
            elif was != (t["kind"], t["value"], t["unit"]):
                out.append(Finding(52, FAIL, f"carries {t['kind']} {t['value']} {t['unit']} on {t['metric']!r} "
                                             f"where {goal.rel} decided {was[0]} {was[1]} {was[2]}. A carried "
                                             f"copy is pinned to what the goal said, and this one has drifted",
                               c.rel))
    if out:
        return out
    tail = f", {n_carried} of them carried unchanged" if n_carried else ""
    legacy_tail = f"; {n_legacy} still by reference while the migration runs" if n_legacy else ""
    return [Finding(52, PASS, f"{n_inline} targets are stated as decisions{tail}{legacy_tail}")]


def check_53_deny_rules_do_not_block_reading(b: Bundle) -> list[Finding]:
    """A settings file in this repository may deny writing and never reading.

    6.2 rule 3: reading `contracts/` is refused at no seat. The reason is not
    access but what a refused seat does next -- it stops reading and starts
    guessing. A contract is a contract because the consumer need not read the
    producer's source; a consumer that cannot read the contract itself has
    nothing left but guesswork, and 2026-09-19 was spent paying for that.

    `Read`, `Grep` and `Glob` are read tools, so denying them is the rule's
    opposite whatever the pattern says. `Bash` is not: a deny that stops a
    hardware script from *running* is legitimate and P0 may require one. What
    is refused is a `Bash` pattern that would catch a *read* -- one naming a
    reading utility, or naming `contracts/` itself. The first draft of this
    check failed every `Bash` deny and would have refused
    `Bash(python3*hardware*)`, which blocks execution and nothing else; a gate
    that refuses correct work is one that gets bypassed.

    **This sees only settings files inside the repository.** A refusal can
    come from user-level settings or from the harness, and this check cannot
    see either: on 2026-09-19 an execution seat was refused a `sed` of
    `contracts/validate.py` while every deny entry in this repository named
    `Write` or `Edit`. A pass here therefore means the repository is clean,
    not that no refusal can happen -- and a seat that meets one it cannot
    find the source of should report it rather than work around it, which is
    the contract-defect report 6.2 rule 3 already describes.
    """
    out: list[Finding] = []
    files = sorted(REPO.glob("*/.claude/settings.json")) + sorted(REPO.glob(".claude/settings.json"))
    if not files:
        return [Finding(53, NA, "no settings files in this repository")]
    n = 0
    for p in files:
        rel = str(p.relative_to(REPO))
        try:
            doc = json.loads(p.read_text())
        except json.JSONDecodeError as exc:
            out.append(Finding(53, FAIL, f"is not readable JSON: {exc}", rel))
            continue
        for entry in (doc.get("permissions") or {}).get("deny") or []:
            if not isinstance(entry, str):
                continue
            n += 1
            tool, _, pattern = entry.partition("(")
            why = None
            if tool in ("Read", "Grep", "Glob"):
                why = f"{tool} is a read tool, so this denies reading whatever the pattern matches"
            elif tool == "Bash":
                low = pattern.lower()
                hit = [c for c in ("cat", "sed", "head", "tail", "less", "awk", "grep", "read")
                       if c in low]
                if "contracts" in low:
                    why = "it names contracts/, which 6.2 rule 3 says is readable at every seat"
                elif hit:
                    why = f"its pattern names {hit[0]!r}, which reads rather than runs"
            if why:
                out.append(Finding(53, FAIL,
                    f"denies {entry!r}: {why}. A refused seat stops reading and starts guessing, "
                    "which is what 6.2 rule 3 is about rather than access", rel))
    return out or [Finding(53, PASS,
        f"{n} deny entries across {len(files)} settings files block no reading "
        "(repository settings only; a user-level or harness refusal is invisible here)")]


def check_54_kb_basis_resolves(b: Bundle) -> list[Finding]:
    """A `kb:` basis must name an entry the same card cites in `kb_refs`.

    5.3.2 widened `basis` to take `kb:<entry_id>` so a bound resting on served
    knowledge rather than on a computed number could be written at all -- A4's
    numbers[] is empty and all five of its basis entries are `kb:`. The
    widening was declared with the claim that **this reference resolves**, and
    that claim is what separates it from the checks that read a declaration
    and trust it. A claim that separates one class from another and is not
    enforced gives the next reader no reason to believe the separation.

    Resolving against the card's own `kb_refs` and not against the store: the
    point is that the card asked for the entry and recorded what came back. An
    entry that exists in the store but was never cited here means the bound
    rests on something this card never obtained, which is the false-grounding
    that an empty basis was going to be.

    **A CARRIED BOUND RESOLVES AGAINST THE CARD IT CAME FROM** (4.5.4, ruled
    2026-09-20 at 061ee6d). A synthesis card carries bounds up from the axes
    and does not query: 4.5.4 rule 4 forbids S4 a caller_id. So every `kb:`
    basis it carries would fail the paragraph above, and microscope-1 raised
    that as a contradiction with two ways out -- a new carriage marker, or an
    exemption. It is neither. The marker exists, and so does the right card:
    `allowed_sets[].from_axes` and `preconditions[].axis` name the axis, the
    axis asked under its own caller_id, and its `kb_refs` hold what came back.

    So this is not an exemption, it is the correct card. Carriage preserves
    the isolation record rather than spending it, and the guarantee the
    widening was declared with is the same one: the entry was obtained by
    somebody who asked for it.

    AT LEAST ONE of the named axes must cite it, not all of them. An
    allowed_set that is an intersection of two axes has a basis drawn from
    whichever contributed each part, and requiring every axis to cite every
    entry would refuse a correctly carried bound. What it still catches is the
    one that matters: an entry no named axis ever obtained.

    This covers the `kb:` form only, which is what 8 declares. The other half
    -- a basis naming a number that is not in numbers[] -- is still
    unguarded: check 2 compares units for basis entries it finds and skips
    the ones it does not, so a basis naming nothing passes. Reported rather
    than folded in here.
    """
    # (config, axis) -> what that axis card obtained. Built once, because a
    # carried bound resolves against the axis and not against its carrier.
    axis_refs: dict[tuple, set] = {}
    axis_seen: set = set()
    for c in b.cards:
        if "__unreadable__" in c.data or c.data.get("card") != "axis":
            continue
        key = (c.data.get("config"), c.data.get("axis"))
        axis_seen.add(key[0])
        axis_refs[key] = {r.get("entry_id") for r in (c.data.get("kb_refs") or [])
                          if isinstance(r, dict)}

    out: list[Finding] = []
    seen = 0
    for c in b.cards:
        if "__unreadable__" in c.data:
            continue
        refs = {r.get("entry_id") for r in (c.data.get("kb_refs") or [])
                if isinstance(r, dict)}
        found: list[tuple] = []

        def carried(node):
            """A synthesis wrapper around an axis bound: which axes to resolve against."""
            if not isinstance(node.get("bound"), dict) or "config" not in node:
                return None
            names = node.get("from_axes") or ([node["axis"]] if node.get("axis") else None)
            if not isinstance(names, list) or not names:
                return None
            return node["config"], [n for n in names if isinstance(n, str)]

        def walk(node, refs=refs, whose=None):
            if isinstance(node, dict):
                c_and_axes = carried(node)
                if c_and_axes:
                    cfg, axes = c_and_axes
                    union: set = set()
                    known = [a for a in axes if (cfg, a) in axis_refs]
                    for a in known:
                        union |= axis_refs[(cfg, a)]
                    # A named axis this run never collected cannot vouch for
                    # anything. Say which, rather than passing on an empty set
                    # that would fail with the wrong message.
                    missing = [a for a in axes if (cfg, a) not in axis_refs]
                    walk(node["bound"], union,
                         (cfg, axes, missing) if missing else (cfg, axes, []))
                    for k, v in node.items():
                        if k != "bound":
                            walk(v, refs, whose)
                    return
                if isinstance(node.get("basis"), list) and "parameter" in node:
                    for x in node["basis"]:
                        if isinstance(x, str) and x.startswith("kb:"):
                            found.append((node.get("parameter"), x[3:], refs, whose))
                # Same rule, second field. 5.3 let `inputs` name the store on
                # 2026-09-20 for the reason that let `basis` do it, and the
                # claim that made that safe was this check. A widening whose
                # guarantee is not extended with it is the guarantee quietly
                # dropped.
                if isinstance(node.get("inputs"), list) and "name" in node:
                    for x in node["inputs"]:
                        if isinstance(x, str) and x.startswith("kb:"):
                            found.append((node.get("name"), x[3:], refs, whose))
                for v in node.values():
                    walk(v, refs, whose)
            elif isinstance(node, list):
                for v in node:
                    walk(v, refs, whose)

        walk(c.data)
        for parameter, entry_id, against, whose in found:
            seen += 1
            if entry_id in against:
                continue
            if whose:
                cfg, axes, missing = whose
                gone = (f"; this run holds no axis card for {missing} under {cfg!r}, so those "
                        f"could not vouch for it") if missing else ""
                out.append(Finding(54, FAIL,
                    f"the carried bound on {parameter!r} rests on kb:{entry_id}, which none of the "
                    f"axes it came from ({', '.join(axes)}) cites in kb_refs. A carried bound "
                    "resolves against the card that asked (4.5.4), and no card here asked for "
                    f"this{gone}", c.rel))
            else:
                out.append(Finding(54, FAIL,
                    f"the bound on {parameter!r} rests on kb:{entry_id}, which this card does not "
                    "cite in kb_refs. A bound may rest on knowledge this card obtained; resting it "
                    "on an entry that was never asked for is the false grounding an empty basis "
                    "would have been (5.3.2)", c.rel))
    if not seen:
        return [Finding(54, PENDING, "no bound rests on a kb: basis yet")]
    return out or [Finding(54, PASS,
                           f"{seen} kb: basis references resolve, each to the card that asked")]


def check_67_entry_units_are_declared(b: Bundle) -> list[Finding]:
    """A KB entry uses declared units everywhere a quantity appears in it.

    Check 2 requires this of cards. Entries had it only for `numbers[]`, by
    check 43's grade derivation happening to touch them, and `validity` was
    unguarded -- which is where it bit. On 2026-09-20 eight polystyrene
    entries carried `validity.temperature` in `degC`, a unit units.json does
    not hold and says it never can: the registry is multiplicative and an
    offset scale has no place in it.

    It was not cosmetic. `mcp_server._si` raises on an unregistered unit and
    the matching loop did not catch it, so ANY query naming a temperature
    condition was refused outright -- ten well-formed entries unreachable
    because a unit in one of them could not be converted, and the caller told
    its query was at fault. Task 025 moved that boundary in the server; this
    is the commit-time half, and it is the half that stops the entry being
    written in the first place.

    Both places, because the same quantity appears in both and only one was
    checked. A value in `numbers[]` and a bound in `validity` are the same
    claim about the same dimension.
    """
    if not KB_DIR.exists() or not (KB_DIR / "entries").exists():
        return [Finding(67, NA, "no knowledge store")]
    try:
        units = set(json.loads((CONTRACTS / "units.json").read_text()).get("units", {}))
    except (OSError, json.JSONDecodeError, AttributeError):
        return [Finding(67, NA, "contracts/units.json is not readable, so nothing can be compared")]

    out: list[Finding] = []
    seen = 0
    for path in sorted((KB_DIR / "entries").glob("*.json")):
        try:
            e = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        eid = e.get("entry_id")
        where: list[tuple[str, str]] = []
        for n in e.get("numbers") or []:
            if isinstance(n, dict) and n.get("unit"):
                where.append((f"numbers[{n.get('name')}]", n["unit"]))
        for q, r in (e.get("validity") or {}).items():
            if isinstance(r, dict) and r.get("unit"):
                where.append((f"validity[{q}]", r["unit"]))
        for place, unit in where:
            seen += 1
            if unit not in units:
                out.append(Finding(67, FAIL,
                    f"{eid} {place} uses unit {unit!r}, which contracts/units.json does not "
                    "declare. The registry is what makes a bound comparable; an undeclared unit "
                    "in `validity` refuses every query that names that condition, not just this "
                    "entry (5.7)", _rel(path)))
    if out:
        return out
    return [Finding(67, PASS, f"{seen} units across entry numbers and validity are declared")]


def check_69_no_entry_cites_itself(b: Bundle) -> list[Finding]:
    """A `kb:` source in an entry may not resolve to the entry it lives in.

    `kb:<entry_id>` is how a CARD cites the store and inherits the cited
    entry's grade. An entry writing it about itself is a loop: the grade is
    derived from the grade of the thing being derived, so it rests on nothing
    and comes out looking derived. Check 43 reads the prefix and is satisfied,
    because the prefix is legal; what is wrong is where it points.

    One in the store on 2026-09-20 and it was the dangerous one to leave:
    `water_viscosity_293k`, whose top-level `source` correctly says
    `literature:src_water_properties` while its number says
    `kb:water_viscosity_293k`. It was cited to another seat as the precedent
    to follow for a new entry, so the one-off was about to become three.
    """
    if not KB_DIR.exists() or not (KB_DIR / "entries").exists():
        return [Finding(69, NA, "no knowledge store")]
    out: list[Finding] = []
    seen = 0
    for path in sorted((KB_DIR / "entries").glob("*.json")):
        try:
            e = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        eid = e.get("entry_id")
        for n in e.get("numbers") or []:
            if not isinstance(n, dict):
                continue
            src = str(n.get("source") or "")
            if not src.startswith("kb:"):
                continue
            seen += 1
            if src[3:] == eid:
                out.append(Finding(69, FAIL,
                    f"{eid} numbers[{n.get('name')}] is sourced {src}, which is this entry. A "
                    "grade derived from its own grade rests on nothing, and check 43 cannot see "
                    "it because the prefix is legal. An entry states where its knowledge came "
                    "from; `kb:` is how a CARD says it got it from the librarian", _rel(path)))
    if out:
        return out
    if seen == 0:
        # Zero is the right end state and it must not read as a dead counter.
        # 61 settled the idiom: all-clear says so, because silence and clean
        # look the same and one of them is a check that stopped working.
        return [Finding(69, PASS, "no entry number carries a kb: source at all, which is where "
                                  "this ends: `kb:` is how a CARD says it got a value from the "
                                  "librarian, and an entry has no use for a card's prefix")]
    return [Finding(69, PASS, f"{seen} kb: sources inside entries point elsewhere")]


# The one determinism violation the log already holds, named rather than cut
# away by a watermark. Two server builds 37 minutes apart on 2026-09-19
# answered `immersion` at kbv-49feb73662b7 two ways, either side of the fix to
# `published_table_for`. It is real, it happened, and an append-only log
# cannot forget it.
KNOWN_LOG_DIVERGENCE = {
    ('["kb_query", "kbv-49feb73662b7", "mic", "immersion", null]',
     '[[], ["in_published_table"], {}]',
     '[[], ["absent"], {}]'),
}


def check_70_one_version_one_answer(b: Bundle) -> list[Finding]:
    """One `kb_version` never answered the same question two ways (4.3.1 rule 2).

    Determinism is what lets a fan-out's siblings be compared: pin the
    version, and the constraints they derive rest on one knowledge state. The
    librarian's own `query_log.verify()` has audited this since the log
    existed and NOTHING RAN IT -- no check called it, so it fired only when a
    seat happened to audit something else. It found the violation below that
    way, while checking whether its own change had dirtied the log.

    RE-IMPLEMENTED HERE AND NOT IMPORTED. `contracts/` may not import an
    agent's source (check 16's direction), so the comparison exists twice, the
    same cost check 61 pays for `envelope_lag()` and for the same reason: one
    copy is the librarian's tool and one runs in every seat's gate. If the two
    disagree about a line, one of them is wrong and neither is authoritative.

    The key is the tool, the version, the question, and the caller's AGENT --
    the prefix of the caller_id, not the whole of it. 4.3.1 rule 1 isolates by
    caller_id and rule 2 forbids depending on call history; the agent is
    neither, it is an argument, and one answer legitimately varies with it
    because a gap pointing into a published table names the asker's own
    snapshot. Keying on the whole caller_id would compare nothing, since every
    axis has its own id.

    EXCLUDED BY NAME, NOT BY WATERMARK. The log is append-only, so the one
    violation it holds can never be removed, and a check over the whole log
    would be red from birth and red forever. A watermark -- verify from line N
    -- would forgive every violation before it, including ones nobody has
    found. Naming the one pair forgives exactly the one pair: 412 answered
    calls stay under audit, and a second violation anywhere, including earlier
    in the log, still fires.
    """
    log = KB_DIR.parent / "queries" / "log.jsonl"
    if not log.exists():
        return [Finding(70, NA, "no query log, so nothing has been answered twice")]

    seen: dict[str, tuple[int, str]] = {}
    out: list[Finding] = []
    answered = 0
    forgiven = 0
    for n, line in enumerate(log.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue                       # check 29's business, not this one
        if rec.get("outcome") == "refused":
            continue                       # nothing was answered
        answered += 1
        agent = str(rec.get("caller_id") or "").split("-", 1)[0]
        qk = json.dumps([rec.get("tool"), rec.get("kb_version"), agent,
                         rec.get("observable"), rec.get("condition_range")], sort_keys=True)
        ak = json.dumps([rec.get("returned"), rec.get("gaps"), rec.get("coverage")],
                        sort_keys=True)
        if qk not in seen:
            seen[qk] = (n, ak)
            continue
        first_line, first_ak = seen[qk]
        if first_ak == ak:
            continue
        if (qk, first_ak, ak) in KNOWN_LOG_DIVERGENCE:
            forgiven += 1
            continue
        out.append(Finding(70, FAIL,
            f"line {n} answered the same query at the same kb_version as line {first_line} "
            f"differently. query={qk}; then={first_ak}; now={ak}. 4.3.1 rule 2 is what lets a "
            "fan-out's siblings be compared, and this is that guarantee failing",
            _rel(log)))
    if out:
        return out
    tail = (f"; the 1 known divergence of 2026-09-19 is excluded by name, so a second one "
            f"anywhere in the log still fires") if forgiven else ""
    return [Finding(70, PASS,
                    f"{answered} answered calls, {len(seen)} distinct questions, one answer "
                    f"each{tail}", _rel(log))]


def check_71_every_check_is_assigned_to_a_seat_that_can_write_it(b: Bundle) -> list[Finding]:
    """Every check in section 8's table is held by a seat that holds `contracts/`.

    Checks live in `contracts/validate.py`. An execution seat writes only
    inside its own agent directory, so assigning one a check is not a backlog
    item, it is an impossibility -- the seat cannot discharge it however long
    it holds it. The librarian seat hit exactly that on 2026-09-20: it read
    that check 67 was declared, assigned to it, and pending, and reported that
    it could not write the file.

    Two of seven were in that state and both had been written that same day,
    by the seat that owns the table. Nothing looked until an execution seat
    walked into the wall and said so, which is what this check replaces.

    It reads `paths` in seats.json rather than the boundary table, because
    holding the boundary is not enough: 11-11 makes a path need both, and the
    narrowing is the half that says WHICH manager. `design` covers every
    manager and architecture at once, so a boundary test would pass a seat
    that cannot touch contracts/ at all.
    """
    rows = re.findall(r"^\| (\d+) \| (.+?) \| ([a-z0-9\-]+) \|\s*$",
                      DESIGN_DOC.read_text(encoding="utf-8") if DESIGN_DOC.exists() else "",
                      re.M)
    if not rows:
        return [Finding(71, NA, f"no seat-bearing check rows found in {DESIGN_DOC_NAME}")]
    try:
        seats = json.loads((CONTRACTS / "seats.json").read_text())["seats"]
    except (OSError, json.JSONDecodeError, KeyError):
        return [Finding(71, NA, "contracts/seats.json is not readable, so nothing can be compared")]
    can_write = {s.get("seat") for s in seats
                 if any(str(p).startswith("contracts/") or str(p) == "contracts/"
                        for p in (s.get("paths") or []))}
    out = []
    for number, _what, seat in rows:
        if seat not in can_write:
            known = "is not a seat in seats.json" if seat not in {s.get("seat") for s in seats} \
                    else "holds no path under contracts/ in seats.json"
            out.append(Finding(71, FAIL,
                f"section 8 assigns check {number} to {seat!r}, which {known}. A check lives in "
                "contracts/validate.py, so a seat that cannot write it cannot discharge the "
                "assignment -- that is an impossibility rather than a backlog, and it reads as a "
                "backlog", DESIGN_DOC_NAME))
    if out:
        return out
    return [Finding(71, PASS,
                    f"{len(rows)} assigned checks are held by seats that hold contracts/",
                    DESIGN_DOC_NAME)]


def check_66_irreversible_run_reads_back_compliance(b: Bundle) -> list[Finding]:
    """An irreversible action's run says whether compliance was read back (4.6.6.1).

    57's sibling, and a second check rather than a second clause in it. Two
    different failures block an irreversible action: the limit is unconfirmed
    -- **a person did not measure** -- and the limit is confirmed while nothing
    reads back whether it held -- **a machine cannot see**. 57 reads the
    envelope and the plan's `actions[]`; this reads the run record, which may
    not exist yet. Architecture put both on 57 in a message and the seat
    holding it followed the document instead, writing "not handled here" into
    the docstring. This is the not-handled half.

    2.1 rule 8 is the substance. A confirmed ceiling bounds what may be
    DEMANDED and says nothing about what HAPPENED, and where nothing reads
    back there is no signal at all -- an absent signal does not permit.

    Three ways to fail, and the third is the one prose cannot catch:

      - the event records no `verification` at all -- the run does not stand,
        and this is separate from recording `none`, which is a statement
      - `verification: none` -- the demand was legitimate, the outcome unknown
      - `verification: readback` on a channel the registry marks
        `read_back: false` -- the log claims something the instrument cannot
        do. `laser_combiner` and `optical_tweezers` are that pair, and they
        are exactly the two 4.6.6.1 rule 3 was written about

    WHAT IT DOES NOT DO. It does not fail a device the channel table has never
    heard of. That is check 38's finding and already open on two names; having
    two checks red on one defect would say the registry is wrong twice.
    """
    logs = b.of_artifact("run_log")
    if not logs:
        return [Finding(66, NA, "no run logs")]

    plans = {c.data.get("id"): c.data for c in b.of_kind("plan")
             if "__unreadable__" not in c.data}

    # read_back is a property of the CHANNEL; a plan may name an element
    # instead, so both resolve to the channel's answer (check 38's rule).
    devices, _dev_rel = _device_table()
    reads_back: dict[str, bool] = {}
    for ch in (devices or {}).get("channels", []) or []:
        rb = ch.get("read_back")
        if not isinstance(rb, bool):
            continue
        reads_back[ch["id"]] = rb
        for el in ch.get("elements") or []:
            reads_back[el["id"]] = rb

    out: list[Finding] = []
    cleared = unresolved_plan = 0
    for log in logs:
        doc = log.data
        plan = plans.get(doc.get("plan_id"))
        if plan is None:
            plan = plans.get(f"{doc.get('plan_id')}-r{doc.get('revision')}")
        if plan is None:
            # Which plan a run carried out is check 15's question, not this
            # one. Counted so the pass line cannot read as "all verified"
            # when it means "nothing was resolvable".
            unresolved_plan += 1
            continue
        by_id = {a.get("id"): a for a in plan.get("actions", []) or []}
        irreversible = {aid for aid, a in by_id.items() if not a.get("reversible")}

        for ev in doc.get("events", []) or []:
            m = re.match(r"actions\[([^\]]+)\]", str(ev.get("from") or ""))
            aid = m.group(1) if m else ev.get("action")
            if aid not in irreversible:
                continue
            device = ev.get("channel") or by_id[aid].get("device")
            v = ev.get("verification")
            if v is None:
                out.append(Finding(66, FAIL,
                    f"action {aid!r} is irreversible and its dispatch records no `verification` at all. "
                    f"4.6.6.1 rule 3: the run record carries the read-back for that channel, and if that "
                    f"is empty the run does not stand. Recording `none` is a statement; recording nothing "
                    f"is not", log.rel))
            elif v == "none":
                out.append(Finding(66, FAIL,
                    f"action {aid!r} is irreversible and ran on {device!r} with nothing reading back "
                    f"whether the limit held. 2.1 rule 8: no read-back is no signal, and an absent "
                    f"signal does not permit. A confirmed ceiling bounds what may be demanded, not what "
                    f"happened (4.6.6.1 rule 3)", log.rel))
            elif reads_back.get(device) is False:
                out.append(Finding(66, FAIL,
                    f"action {aid!r} claims `verification: readback` on {device!r}, which the channel "
                    f"table marks read_back false -- that channel reports nothing back, so the claim "
                    f"describes something the instrument cannot do (4.6.6.1 rule 3)", log.rel))
            else:
                cleared += 1

    if out:
        return out
    if unresolved_plan and not cleared:
        return [Finding(66, PENDING, f"{unresolved_plan} run log(s) name a plan that is not in this tree, "
                                     f"so which of their actions are irreversible cannot be read "
                                     f"(check 15 owns that link)")]
    if not cleared:
        return [Finding(66, PASS, f"{len(logs)} run log(s) dispatched no irreversible action; there is "
                                  f"nothing whose compliance had to be read back")]
    return [Finding(66, PASS, f"{cleared} irreversible dispatch(es) read compliance back from a channel "
                              f"that can report it")]


def check_68_a_gap_names_a_quantity_not_a_subject(b: Bundle) -> list[Finding]:
    """A gap names the QUANTITY it wanted, never the subject or the locus.

    quantities.json rule 1, and this check is the sentence that rule wrote
    about itself: when check 44 refused the `subject` field on those entries
    the claim did not disappear, "**it moved into the name where nothing
    checks it. A name that asserts its own subject is a subject nothing can
    refuse.**" That clause stayed literally true until 2026-09-20 -- nothing
    read `kb_gaps[].observable` against the registry at all.

    BOTH DIRECTIONS, because the two instances went opposite ways. An A6 card
    carried `immersion_refractive_index`: the registered quantity with a
    SUBJECT in front. An A1 card carried `pixel_size_in_sample`: the
    registered quantity with a LOCUS behind. Rule 1 names both --
    `tracer_particle_density` and `na_mrd70040` for the first,
    `ambient_temperature` for the second -- and an `endswith` test alone
    catches only half. The half it misses was found by reading data, not by
    reasoning about the rule.

    NARROW ON PURPOSE, and the wide form was measured and thrown away.
    Failing every gap name the registry does not hold gives 31 findings and
    is unusable: a gap pointing at an unregistered name is normal, and is
    frequently the very reason it is a gap.

    THE GUARD THAT MATTERS: a name that is ITSELF registered is skipped
    before either test. Without it `tracer_diffusivity_expected` -- a
    registered quantity in its own right -- trips the prefix rule against
    `tracer_diffusivity`. The seat fixing the A1 card warned of this before
    the check landed.

    WHAT THIS DOES NOT BUY, which matters more than what it does. **Naming
    hygiene, not safety.** On the A6 instance the malformed name was the
    SAFER outcome: asked by its registered name, `refractive_index` returns
    eight entries at E3 and every one is polystyrene -- the bead material,
    not the immersion medium. The bad name returned `absent` and the axis
    abstained; the good name would have handed it eight numbers for the wrong
    substance, produced an `axial_range` computed from a bead, and reddened
    nothing. **Rule 1 being broken is what stopped it.** What the danger
    needs is the subject matching, which is check 44's ground. This check is
    worth having because a name nothing can refuse is a permanent hole, not
    because it closes that one.
    """
    qreg = CONTRACTS / "quantities.json"
    if not qreg.exists():
        return [Finding(68, PENDING, "contracts/quantities.json is not in this tree")]
    try:
        doc = json.loads(qreg.read_text())
        registered = {q["id"] for q in doc.get("quantities", [])
                      if isinstance(q, dict) and q.get("id")}
    except (json.JSONDecodeError, AttributeError, TypeError):
        return [Finding(68, NA, "contracts/quantities.json does not parse; check 1 owns that")]
    if not registered:
        return [Finding(68, NA, "the quantity registry is empty")]

    pending = set(doc.get("not_yet_registered") or [])
    out: list[Finding] = []
    seen = 0
    for c in b.cards:
        if "__unreadable__" in c.data:
            continue
        for g in c.data.get("kb_gaps") or []:
            if not isinstance(g, dict):
                continue
            name = g.get("observable")
            if not isinstance(name, str) or not name:
                continue
            seen += 1
            if name in registered or name in pending:
                continue                  # a registered name is its own quantity
            glued = [(q, "subject", name[: -(len(q) + 1)]) for q in registered
                     if name.endswith("_" + q)]
            glued += [(q, "locus", name[len(q) + 1:]) for q in registered
                      if name.startswith(q + "_")]
            if not glued:
                continue                  # unregistered, and that is a gap's prerogative
            quantity, kind, extra = max(glued, key=lambda t: len(t[0]))
            out.append(Finding(68, FAIL,
                f"gap {g.get('gap_id')!r} asks for {name!r}, which is the registered quantity "
                f"{quantity!r} with the {kind} {extra!r} glued to it. quantities.json rule 1: a "
                f"name states the quantity and never its subject or its locus, because a name "
                f"that asserts its own subject is a subject nothing can refuse -- check 44 "
                f"refuses the `subject` field and cannot see into a string. Ask for "
                f"{quantity!r} and carry {extra!r} where it can be refused", c.rel))
    if out:
        return out
    if not seen:
        return [Finding(68, NA, "no cards record kb_gaps")]
    return [Finding(68, PASS, f"{seen} gap names state a quantity without a subject or a locus "
                              f"glued into the string")]


def check_73_a_result_names_an_approval_and_a_run_that_exist(b: Bundle) -> list[Finding]:
    """A result's `approval_id` and `run_id` resolve to things in this tree.

    Assigned by architecture on 2026-09-21 after an audit found the chain
    verified up to the plan and stopping before the result: `plan_hash` is
    checked, and `approval_id` appeared **nowhere** in this file. So nothing
    asked whether a reported run was a run that happened, or whether the
    approval it names ever existed. 2.1 rule 7 is assumed on the way IN --
    `operator.run()` refuses a Tier 2 plan whose own `status` says APPROVED
    while no approval card names it -- and there was no equivalent on the way
    OUT.

    **`approval_id: null` is not a hole.** It is the honest Tier 0-1 case and
    result.schema.json keeps the key required precisely so that *needed none*
    is written rather than omitted. Two of the three results in the tree say
    null and are correct.

    WHAT IT COMPARES. A `plan_approval` names one (plan_id, revision) and the
    result names its own, so the two must agree -- an approval for another
    revision is not an approval for this one (5.5). A `scope_approval` names
    no plan by design, so only its existence is checked here; whether its
    range covers this plan is check 19's.

    THE RUN HALF SPLITS, and the split is the expand-migrate-contract idiom
    this file uses elsewhere. A run id that names no directory is a defect
    once the agent has runs at all, and is an artifact a later milestone
    produces when it has none -- `microscope_agent/runs/` does not exist, so
    `contracts/examples/result.json` names `run-20260917-001` and nothing is
    yet capable of holding it. Failing that today would refuse an example for
    being ahead of M1. It flips the moment that agent writes its first run.
    """
    results = [c for c in b.of_kind("result") if "__unreadable__" not in c.data]
    if not results:
        return [Finding(73, NA, "no result cards")]

    approvals: dict[str, dict] = {}
    for c in b.of_kind("plan_approval", "scope_approval"):
        if "__unreadable__" not in c.data and c.data.get("id"):
            approvals[c.data["id"]] = c.data

    runs_by_agent: dict[str, set[str]] = {}
    for d in REPO.glob("*_agent/runs/*"):
        if d.is_dir():
            runs_by_agent.setdefault(d.parent.parent.name, set()).add(d.name)

    out: list[Finding] = []
    resolved = tier01 = 0
    ahead: list[str] = []
    for c in results:
        data = c.data
        aid = data.get("approval_id")
        if aid is None:
            tier01 += 1
        elif aid not in approvals:
            out.append(Finding(73, FAIL,
                f"names approval {aid!r}, which is not a card in this tree. A result is the record "
                f"that a run happened under an approval, and an approval nobody can open is not one "
                f"(2.1 rule 7, 5.5)", c.rel))
        else:
            appr = approvals[aid]
            if appr.get("card") == "plan_approval":
                want = (data.get("plan_id"), data.get("plan_revision"))
                got = (appr.get("plan_id"), appr.get("revision"))
                if want != got:
                    out.append(Finding(73, FAIL,
                        f"names approval {aid!r}, which approves {got} and this result carries "
                        f"{want}. An approval for another revision is not an approval for this one "
                        f"(5.5)", c.rel))
                else:
                    resolved += 1
            else:
                resolved += 1          # scope: existence only; check 19 owns the range

        rid = data.get("run_id")
        agent = c.rel.split("/")[0]
        held = runs_by_agent.get(agent, set())
        if not rid:
            continue                   # check 1 owns the missing field
        if rid in held:
            continue
        if not held:
            ahead.append(f"{rid} in {c.rel}")
        else:
            out.append(Finding(73, FAIL,
                f"names run {rid!r} and {agent}/runs/ holds {sorted(held)}. A result reports what a "
                f"run produced, so a run id that opens no directory is a report of something with "
                f"no record (P1)", c.rel))

    if out:
        return out
    if ahead:
        return [Finding(73, PENDING,
                        f"{resolved} approval reference(s) resolve and {tier01} say null for Tier 0-1; "
                        f"{len(ahead)} run id(s) name an agent that has written no runs at all, which "
                        f"M1 produces: {ahead[0]}. This becomes a failure for that agent the moment it "
                        f"writes its first run")]
    return [Finding(73, PASS, f"{resolved} result(s) name an approval that covers their plan revision "
                              f"and {tier01} say null for Tier 0-1; every run id opens a directory")]


def check_60_observables_are_registered_quantities(b: Bundle) -> list[Finding]:
    """Every observable id is declared in contracts/quantities.json (section 7).

    Section 7 says every observable is a quantity and not the reverse. That is
    true of the KINDS and was false of the FILES: the quantity registry was
    written on 2026-09-19 from the ids already used as `subject: {kind:
    quantity}`, and neither observable was among them. A sentence true of
    kinds and false of files is read by a person as the first and by code as
    the second, and the reading side reads files.

    The direction is what makes this cheap, and it is one way on purpose.
    Nothing compares the two lists for agreement: `quantities.json` holds a
    dozen names no observable will ever carry -- a coverslip thickness, a
    pixel size -- and that is correct, because the two files answer different
    questions. observables.json registers what two agents can PRODUCE and
    COMPARE; quantities.json registers what a name MEANS. Only the inclusion
    is enforced, so both may grow at their own rate as long as the smaller
    stays inside the larger.

    `not_yet_registered` is deliberately NOT honoured as an escape, unlike
    check 47's `retired_names`. It exists for names in use that the registry
    declines to bless yet, and an observable is not in that class: registering
    one is the HARDER commitment of the two -- it carries an estimator, a
    window parameter and a producible_by, and the bridge resolves
    answerability against it. A name already blessed at that cost cannot be
    pending at the cheaper one, and letting it be would make the section 7
    sentence opt-out.

    WHAT A PASS DOES NOT SAY: that the two entries agree. Units, definition
    and wording are not compared -- an observable admits several units and a
    quantity names one canonical one, so they cannot be equal and a check that
    demanded it would be wrong. Section 8 states that limit for the kind that
    reads a declaration rather than comprehends it.
    """
    observables = load_observables()
    if not observables:
        return [Finding(60, NA, "no observables are registered")]
    qreg = CONTRACTS / "quantities.json"
    if not qreg.exists():
        return [Finding(60, PENDING, "contracts/quantities.json is not in this tree")]
    try:
        declared = {q["id"] for q in json.loads(qreg.read_text()).get("quantities", [])
                    if isinstance(q, dict) and q.get("id")}
    except (json.JSONDecodeError, AttributeError, TypeError):
        return [Finding(60, NA, "contracts/quantities.json does not parse; check 1 owns that")]
    out = [Finding(60, FAIL,
                   f"observable {oid!r} is not declared in contracts/quantities.json. Section 7 "
                   "requires every observable to be a registered quantity: the bridge compares two "
                   "sides by quantity id, and an observable whose name means nothing in the registry "
                   "is a comparison with no declared operand",
                   "contracts/observables.json")
           for oid in sorted(observables) if oid not in declared]
    return out or [Finding(60, PASS,
                           f"{len(observables)} observable ids are all declared quantities, of the "
                           f"{len(declared)} the registry holds", "contracts/observables.json")]


def check_61_envelope_currency(b: Bundle) -> list[Finding]:
    """How far each envelope trails the published export. ADVISORY: a number
    in a passing message, never a status of its own.

    Three things looked at snapshots and none of them looked at this. Check 26
    compares an envelope against the commit it NAMES, which is integrity, and
    it is right to pass an honest envelope of any age. `export_snapshot.py
    --check` compares the exports against the store, which is the publisher's
    end. Nobody compared an export against the envelope that copied it, so a
    microscope envelope sat 34 entries behind inside a repository reading
    `0 failed`, and the only reason anyone noticed was a manager opening two
    files by hand (task 018).

    IT DOES NOT FAIL, AND THAT IS NOT SOFTNESS. A stale envelope is not a
    defect: a consumer may pin deliberately, and an agent that has not run
    today is in breach of nothing. Make it red and the gate reddens whenever a
    seat is idle -- which on 2026-09-19 was most of them -- and a gate that
    reddens for correct inaction is one people learn to skip. No new ADVISORY
    status either: five meanings are enough to relearn, and a sixth would
    reopen how --strict counts it. The idiom already exists -- check 52 says
    "4 still by reference", check 3's UNDECIDED line carries per-plan counts.

    TWO LEGS, NAMED SEPARATELY, BECAUSE THEY HAVE DIFFERENT OWNERS. An
    envelope behind a STALE export cannot be fixed by the consumer -- copying
    gets them the stale export -- so one merged number would hide whose move
    it is. The useful output of a currency check is a distance plus an owner.
    (librarian-3, `kb/distilled/`.)

    THE PUBLISHER'S LEG WAS LEFT OUT UNTIL 2026-09-20 AND HAD TO COME BACK.
    The argument for leaving it out was that `export_snapshot.py --check`
    already has it, which is true -- it prints `exports are current` and names
    the store version when they are not. What is also true is that `--check`
    is the librarian's tool and its own source says the consumer never runs
    it, so that leg runs in one seat, by hand, on the days that seat happens
    to look. It ran in no gate.

    What that cost, on the morning it was written: the store moved twice and
    the exports sat at the previous night's version for hours, while every
    seat's gate read `0 failed` and THIS CHECK CALLED THE MICROSCOPE ENVELOPE
    `current`. It was -- current with an export two versions stale. A word
    that means up-to-date was true of the comparison and false of the
    situation, which is worse than silence, because silence does not reassure.
    The person was choosing how to write a safety limit against that envelope
    at the time.

    So the leg is here as its OWN count with its OWN owner named, which is
    what the original argument actually forbade merging. Duplication cost:
    this is a third copy of a one-line comparison, and the docstring below
    already says what to do when copies disagree.

    Three shapes it has to get right, and all three are in task 018 rather than
    in anyone's context:

    1. `kb_version` is a hash over every entry, so an EDIT moves it with no
       change in count. A delta-only report prints "0 entries behind" for a
       store that really moved, so the version and the count are two
       statements and both go in the line.
    2. An envelope AHEAD of the export means the EXPORTS are the stale side,
       and the librarian closes that by republishing. Different owner, so it
       is worded differently rather than called "behind".
    3. An agent with no envelope has not fallen behind, it has not started.
       Its own category, not an infinite lag.

    THE COMPUTATION IS DUPLICATED FROM `envelope_lag()` AND THAT IS A COST.
    contracts/ may not import an agent's source -- check 16's direction, and
    section 7 makes contracts the thing agents depend on -- so the two halves
    read the same two files by two copies of one rule. This is 11-11's shape
    with the audiences deliberately split: the publisher's tool tells the seat
    that cannot act, and this one runs in every seat's gate. If the two ever
    disagree about an agent, one of them is wrong and neither is authoritative
    over the other.

    MUTATION-TESTED AGAINST SYNTHETIC TREES ON 2026-09-20, because the real one
    exercises only some of it. Six shapes, each built in a scratch tree with
    KB_DIR and REPO pointed at it: same count on a moved version reports the
    edit rather than "0 behind"; AHEAD names the publisher; a missing envelope
    lands in its own category; a plain lag counts; all-current SAYS SO rather
    than printing nothing, because silence and clean read the same and one of
    them is a check that stopped working; and nothing published is N/A.

    THE TEST IS NOT IN THE REPOSITORY, and that is the gap to name rather than
    leave. contracts/ has no home for a validator unit fixture -- examples/
    holds cards -- and inventing one is a shared-surface convention that binds
    four manager seats, so it is not this seat's to add alone. Today the tree
    itself exercises the behind row and the absent row; when the simulation
    envelope catches up, the moved-version and AHEAD shapes are tested by
    nothing. That is 018's own warning turned on this check: a property that
    waits for real lag passes vacuously on a day with none.
    """
    exports = KB_DIR / "exports"
    if not exports.exists():
        return [Finding(61, NA, "nothing has been published, so no envelope can trail it")]
    published = sorted(exports.glob("snapshot_*.json"))
    if not published:
        return [Finding(61, NA, "nothing has been published, so no envelope can trail it")]

    try:
        store_version = json.loads(KB_INDEX_PATH.read_text()).get("kb_version")
    except (OSError, json.JSONDecodeError):
        store_version = None

    current, absent, rows, unreadable = [], [], [], []
    stale_exports = []
    for target in published:
        agent = target.name[len("snapshot_"):-len(".json")]
        try:
            pub = json.loads(target.read_text())
        except json.JSONDecodeError:
            unreadable.append(f"the export for {agent} does not parse; check 1 owns that")
            continue
        if store_version and pub.get("kb_version") != store_version:
            stale_exports.append(f"{agent} at {pub.get('kb_version')}")
        env = REPO / agent / "envelope" / "snapshot.json"
        if not env.exists():
            absent.append(agent)
            continue
        try:
            copy = json.loads(env.read_text())
        except json.JSONDecodeError:
            unreadable.append(f"{agent}'s envelope does not parse; check 5 owns that")
            continue
        if copy.get("kb_version") == pub.get("kb_version"):
            current.append(agent)
            continue
        delta = (pub.get("entry_count") or 0) - (copy.get("entry_count") or 0)
        if delta > 0:
            rows.append(f"{agent} is {delta} behind at {copy.get('kb_version')}, which the "
                        f"consuming agent closes by re-copying")
        elif delta < 0:
            rows.append(f"{agent} is {-delta} AHEAD at {copy.get('kb_version')}, so the exports "
                        f"are the stale side and the librarian closes it by republishing")
        else:
            rows.append(f"{agent} is at the same entry count on a different kb_version "
                        f"({copy.get('kb_version')}), so entries were edited rather than added")

    parts = []
    if store_version is None:
        parts.append("the store's own version could not be read, so nothing is said about "
                     "whether the exports are current with it")
    elif stale_exports:
        parts.append(f"{len(stale_exports)} export{'' if len(stale_exports) == 1 else 's'} "
                     f"published from before the store's {store_version} "
                     f"({'; '.join(stale_exports)}), which only the librarian closes by "
                     f"republishing -- an envelope matching one of these is current with a "
                     f"stale copy and not with the store")
    else:
        parts.append(f"every export is at the store's {store_version}")
    if current:
        parts.append(f"{len(current)} current ({', '.join(current)})")
    parts += rows
    if absent:
        parts.append(f"{len(absent)} with no envelope yet ({', '.join(absent)}), which is not "
                     "behind but not started")
    parts += unreadable
    return [Finding(61, PASS,
                    f"{len(published)} published export{'' if len(published) == 1 else 's'}, "
                    "checked against the store that fed them and against the envelopes that "
                    "copied them, as two legs with two owners: " +
                    "; ".join(parts) +
                    ". Reported and not failed -- a consumer may pin deliberately and an idle "
                    "seat is in breach of nothing",
                    "librarian_agent/kb/exports")]


def check_58_one_fanout_reads_one_store(b: Bundle) -> list[Finding]:
    """Every axis card under one question and configuration pins one store.

    Check 33 asks the same thing and cannot see this. It groups by
    (scope, qid, **revision**), and it has to: a revision is a re-run (4.5.5),
    caller_id carries no revision component, so grouping without it makes
    "caller_id reused" fire on a card and the card that replaced it. Correct
    for that question, and it partitions the fan-out for every other question
    asked in the same pass -- including the kb_version agreement, which then
    holds trivially inside each partition.

    Intersecting intervals derived against different stores compares two
    knowledge states, and the abstentions are the worse half: an axis at an
    older pin reports `absent` for what the newer store holds, and nothing
    downstream can tell that from a real absence.

    **What counts as one fan-out is the set S4 reads together, and that is the
    artifact prefix, not the `revision` field.** This docstring said a revision
    counts re-runs of one axis and ignored the field on those grounds. The
    field turned out to mean two things at once: `mic-20260918-001` carries
    seven axes at revisions 2, 4 and 5 in one unprefixed filename set, all
    pinned to one store -- a per-axis counter -- while `sim-20260917-001`
    re-ran its whole fan-out and wrote `v2_axis_*` alongside, question-level
    per 4.5.5. Grouping by the field is wrong for the microscope and ignoring
    it is wrong for the simulation; grouping by the prefix is right for both,
    because `v2_axis_*` and `axis_*` are exactly the two sets S4 reads
    separately. Which of the two meanings 4.5.5 intends is a real question and
    it is architecture's -- this check no longer depends on the answer.

    Not a duplicate of 33 -- the half of 33's question that 33's grouping had
    to give up.

    When written, mic-20260918-001 had six axes at kbv-7c77fa74ee5a and a5
    alone at kbv-49feb73662b7, six commits and fifty-eight entries apart, and
    check 33 passed. Re-deriving a5 found all seven of its inputs still
    absent, so the split had not yet produced a wrong answer -- which is the
    argument for closing it then rather than the argument that it did not
    matter.
    """
    out: list[Finding] = []
    groups: dict[tuple, list] = {}
    for c in b.cards:
        if "__unreadable__" in c.data or c.data.get("card") != "axis":
            continue
        qid, cfg, ver = c.data.get("qid"), c.data.get("config"), c.data.get("kb_version")
        if not qid or not ver:
            continue
        m = re.match(r"^v(\d+)_", pathlib.Path(c.rel).name)
        fanout = m.group(1) if m else "1"
        groups.setdefault((card_scope(c), qid, cfg, fanout), []).append((ver, c))
    if not groups:
        return [Finding(58, NA, "no axis cards")]
    for (_where, qid, cfg, fanout), members in sorted(groups.items(), key=lambda kv: str(kv[0])):
        by_ver: dict[str, list[str]] = {}
        for ver, c in members:
            by_ver.setdefault(ver, []).append(c.data.get("axis") or c.rel)
        if len(by_ver) > 1:
            spread = "; ".join(f"{v} <- {', '.join(sorted(a))}" for v, a in sorted(by_ver.items()))
            out.append(Finding(58, FAIL,
                f"the fan-out for {qid} on {cfg} (artifacts at v{fanout}) reads {len(by_ver)} stores: {spread}. S4 intersects "
                "these together, and an axis left at an older pin reports absent for what the newer "
                "store holds -- indistinguishable downstream from a real absence. Re-derive the "
                "stragglers; do not re-pin them without re-asking", members[0][1].rel))
    return out or [Finding(58, PASS,
        f"{len(groups)} fan-outs each read one store, across revisions")]


def check_65_history_checks_have_a_built_repository(b: Bundle) -> list[Finding]:
    """A check that reads git history has a fixture that builds one.

    `--expect-fail contracts/examples/rejected` proves a check still works by
    handing it a card. A check whose evidence is history cannot be reached
    that way, and until 2026-09-20 the four that read it had no fixture at
    all -- their only evidence was a sentence in a commit message, which is
    what 11-7 calls a check nobody has tested.

    **The four are derived, not listed.** Restating them here would put the
    same fact in two places with nothing comparing them (11-11), and the copy
    would go stale the first time someone writes a fifth. What this reads is
    which check functions touch `GIT_REPO` or a commit range, which is what
    reading history means in this file. So a new history-reading check that
    arrives without a fixture fails here, on the commit that adds it.

    Reads a declaration and not a run; section 8 states that limit once, for
    this kind. It sees that a fixture is listed for each check and that the
    builder it names exists -- not that running it still produces the verdict
    it claims. Running them from here was rejected on cost: each builds a
    repository and runs a second validator inside it, seconds apiece on a
    gate that runs for every commit in every session.
    `python3 contracts/history_fixtures.py` is what proves they fire.
    """
    src = (CONTRACTS / "validate.py").read_text()
    reads_history = set()
    for m in re.finditer(r"(?m)^def check_(\d+)_\w+\(", src):
        n = int(m.group(1))
        # This check reads source for a token and therefore matches itself:
        # the words it searches for are in its own body. It reads files and
        # no history, so excluding it is not a hole -- and the exclusion is
        # named rather than silent, because the first run of this check
        # failed on exactly this and the reason is not visible from the
        # message it produced.
        if n == 65:
            continue
        body = src[m.end():].split("\ndef ")[0]
        if "GIT_REPO" in body or "commit_range" in body:
            reads_history.add(n)
    if not reads_history:
        return [Finding(65, NA, "no check reads git history")]

    harness = CONTRACTS / "history_fixtures.py"
    rel = "contracts/history_fixtures.py"
    if not harness.exists():
        return [Finding(65, FAIL, f"{len(reads_history)} checks read git history and {rel} does not exist, "
                                  f"so none of them has ever been seen to fail (11-7)", rel)]
    text = harness.read_text()
    listed = {int(n): name for n, name in
              re.findall(r'(?m)^\s*\((\d+),\s*"[A-Z/]+",\s*"[^"]*",\s*(\w+)\)', text)}

    out: list[Finding] = []
    for n in sorted(reads_history - set(listed)):
        out.append(Finding(65, FAIL, f"check {n} reads git history and {rel} builds no repository for it, "
                                     f"so nothing has ever watched it fail (11-7)", rel))
    for n, builder in sorted(listed.items()):
        if f"def {builder}(" not in text:
            out.append(Finding(65, FAIL, f"the fixture listed for check {n} names {builder}, which this "
                                         f"file does not define", rel))
    if out:
        return out
    return [Finding(65, PASS, f"{len(reads_history)} checks read git history and each has a fixture that "
                              f"builds one; run {rel} to see them fire")]


def check_59_the_hook_reports_an_unattributed_commit(b: Bundle) -> list[Finding]:
    """The gate says out loud when a commit carries no attribution.

    `seats.json` sets `unknown_committer` to `report` rather than `refuse`, so
    a seat that has not adopted an identity is not blocked -- and the registry
    records what that costs: an unattributed commit gets **no boundary
    checking at all**, because nothing says whose paths those were. The report
    is the only thing between that and silence.

    Nothing reported, for as long as both halves existed. Check 41 returns
    PENDING for it, PENDING is not a failure, and the hook printed only on
    failure -- so a commit with zero coverage passed without a word. A policy
    of `report` that reports nothing is a declaration whose other end nobody
    reads, in the gate itself.

    **What this compares is the two halves against each other**, which is the
    part a reader should not mistake for a spelling check. The finding check
    41 emits and the string the hook greps for are one fact in two files, and
    changing the wording in either one silently stops the warning -- the hook
    keeps running, finds nothing, and says nothing, which is
    indistinguishable from a commit that was attributed. So the phrase is
    read out of this file rather than written here, and the hook is required
    to carry the same one.

    What it does not check, so nobody expects more: that the hook prints the
    paths rather than a count, that it does not refuse (the policy is
    `report`), or that any of it runs. Those are read by eye and by
    `contracts/history_fixtures.py`, whose check 41 fixture builds an
    unattributed commit and asserts the PENDING.
    """
    hook = REPO / "contracts" / "hooks" / "pre-commit"
    rel = "contracts/hooks/pre-commit"
    if not hook.exists():
        return [Finding(59, FAIL, "the pre-commit hook is missing, so nothing reports an unattributed "
                                  "commit and nothing runs the validator at commit time", rel)]

    text = hook.read_text()
    needles = re.findall(r'ATTRIB=\$\(echo "\$OUT" \| grep "([^"]+)"', text)
    if not needles:
        return [Finding(59, FAIL, "the hook does not look for an unattributed commit at all. check 41 "
                                  "returns PENDING for one, PENDING is not a failure, and a hook that "
                                  "prints only on failure passes it in silence -- which is what "
                                  "`report` meant in practice until 2026-09-20", rel)]

    # The relation runs this way round on purpose: the hook's needle has to
    # occur in what check 41 says, not the other way about. Check 41's
    # sentence is free to grow -- it gained the path list the same day --
    # and the warning survives that. What it may not do is move out from
    # under the needle, which is the change that stops the warning while
    # both halves keep running and neither says anything.
    src = (CONTRACTS / "validate.py").read_text()
    body = src.split("def check_41_seat_attribution", 1)[-1].split("\ndef ")[0]
    missing = [n for n in needles if n not in body]
    if missing:
        return [Finding(59, FAIL, f"the hook greps for a phrase of {len(missing[0])} characters to report "
                                  f"an unattributed commit and check 41 no longer says it, so the warning "
                                  f"is emitted and never shown. A grep that matches nothing is "
                                  f"indistinguishable from a commit that was attributed. Compare the hook "
                                  f"against check 41's finding", rel)]
    # Deliberately not quoting the needle back. Printing it put the phrase
    # into a passing line, the hook's grep matched that, and the gate
    # reported an attributed commit as unattributed -- a check describing a
    # string became an instance of it. Say the length instead.
    return [Finding(59, PASS, f"the hook looks for the {len(needles[0])}-character phrase check 41 emits "
                              f"for an unattributed commit, and check 41 still emits it")]


def check_63_a_tie_carries_the_worse_grade(b: Bundle) -> list[Finding]:
    """A tie is a verdict about two values, and it carries a grade too (5.8.1).

    P15's 10x band compares two VALUES. It does not compare two bodies of
    evidence, and on 2026-09-19 that gap had teeth: the simulation held
    `bead_diameter` 2 um as `assumed:` E5 while the store held the tracer
    diameter at 5 um as `calibration:` E2. Since D goes as 1/d the
    diffusivities are 2.5x apart, inside the band, so formally a tie -- and
    the band **endorsed keeping the placeholder**, because a difference
    inside it is no disagreement to report. The distance between the values
    had not moved at all and whether a conclusion could stand had changed
    entirely.

    The answer is not a narrower band and not a new threshold. 5.8 already
    says a computed value inherits the worst input in its chain; the rule
    simply had not been applied to comparison. **So does the verdict of a
    comparison.** A tie between E2 and E5 is an E5 tie, and `worse()` -- the
    function 5.8 already uses for the chain -- is the one this reads with.

    **It is the ungraded tie that misleads.** "No disagreement at E5" reads
    correctly; "no disagreement" alone reads as agreement, which is a far
    stronger statement than two placeholders can support.

    Recomputed, never read. The grade is derived from the two operands' own
    numbers, and a card claiming better than they support is refused the way
    check 8 refuses an answerability verdict the tables do not support: a
    verdict the writer can choose is not a gate (check 21's rule).

    This does not say the weaker value is wrong. A model may run at a
    diameter that is not on the bench, as long as the choice is recorded as a
    choice -- what changed is that a placeholder stopped being the best
    available and became a choice against evidence.
    """
    asks = [c for c in b.of_kind("ask_simulation", "ask_experiment") if c.data.get("value_comparison")]
    if not asks:
        return [Finding(63, NA, "no round compares two values yet; the opening round of a thread has no "
                                "counterpart to compare against (4.4)")]

    numbers_by_card: dict[str, dict[str, dict]] = {}
    for c in b.cards:
        cid = c.data.get("id")
        if cid:
            numbers_by_card[cid] = {n.get("name"): n for n in c.data.get("numbers") or []}

    out: list[Finding] = []
    checked = 0
    for c in asks:
        vc = c.data["value_comparison"]
        if vc.get("verdict") != "tie":
            continue
        operands = vc.get("of") or []
        if len(operands) != 2:
            out.append(Finding(63, FAIL, "reports a tie and does not name the two values it compared, so "
                                         "the grade it carries rests on nothing that can be read back "
                                         "(5.8.1)", c.rel))
            continue
        grades, unresolved = [], []
        for o in operands:
            num = numbers_by_card.get(o.get("card"), {}).get(o.get("number"))
            if num is None or not num.get("grade"):
                unresolved.append(f"{o.get('card')}#{o.get('number')}")
            else:
                grades.append(num["grade"])
        if unresolved:
            out.append(Finding(63, FAIL, f"reports a tie against {', '.join(unresolved)}, which this tree "
                                         f"does not carry as a graded number, so the tie's own grade "
                                         f"cannot be recomputed (5.8.1)", c.rel))
            continue
        want = worse(*grades)
        got = vc.get("grade")
        checked += 1
        if got is None:
            out.append(Finding(63, FAIL, f"reports a tie between {grades[0]} and {grades[1]} and carries no "
                                         f"grade. It is the ungraded tie that misleads -- 'no disagreement' "
                                         f"reads as agreement, where 'no disagreement at {want}' reads "
                                         f"correctly (5.8.1)", c.rel))
        elif got != want:
            out.append(Finding(63, FAIL, f"reports a {got} tie between a {grades[0]} value and a {grades[1]} "
                                         f"one. A comparison inherits the worse of what it compared, the "
                                         f"way a computed value inherits the worst input in its chain "
                                         f"(5.8, 5.8.1), so this is a {want} tie", c.rel))
    if out:
        return out
    if not checked:
        return [Finding(63, NA, "no round reports a tie; a comparison that found a difference carries no "
                                "grade of its own")]
    return [Finding(63, PASS, f"{checked} ties carry the worse grade of the two values they compared")]


CHECKS = [
    check_01_schema, check_02_units, check_03_source_and_grade, check_04_assumptions_explained,
    check_05_envelope, check_06_criteria, check_07_state_and_approval, check_08_bridge,
    check_09_md_vs_json, check_10_degraded, check_11_axis_independence, check_12_synthesis_closure,
    check_13_paths, check_14_command_provenance, check_15_approval_precedes_run,
    check_16_dependency_direction, check_17_derived, check_18_scope_range, check_19_scope_validity,
    check_20_alternatives, check_21_grade_derivation, check_22_irreversible, check_23_manual_lockout,
    check_24_calibration_validity, check_25_kb_refs, check_26_snapshot, check_27_knowledge_ownership,
    check_28_precision, check_29_failure_record, check_30_lessons, check_31_candidate_preservation,
    check_32_purpose, check_33_caller_isolation, check_34_compare_arms, check_35_session_boundary,
    check_36_symbol_collision, check_37_time_base, check_38_one_table, check_39_estimate_justified,
    check_40_window_condition, check_43_entry_grade, check_46_vocabulary_pin, check_48_registry_grants, check_44_subject_resolves, check_49_absent_searched_the_neighbourhood, check_62_computed_grade_derived, check_64_every_rejected_fixture_is_reached, check_55_section_7_names_are_allowed,
    check_50_delivery_has_a_reader,
    check_51_open_question_has_a_home,
    check_52_target_is_a_decision,
    check_65_history_checks_have_a_built_repository,
    check_59_the_hook_reports_an_unattributed_commit,
    check_63_a_tie_carries_the_worse_grade, check_53_deny_rules_do_not_block_reading,
    check_54_kb_basis_resolves, check_58_one_fanout_reads_one_store,
    check_45_undegraded_is_backed_by_the_log,
    check_47_registry_prose_names_real_seats,
    check_56_undecided_names_the_settled_unit,
    check_57_irreversible_rests_on_a_confirmed_limit,
    check_66_irreversible_run_reads_back_compliance,
    check_68_a_gap_names_a_quantity_not_a_subject,
    check_73_a_result_names_an_approval_and_a_run_that_exist,
    check_60_observables_are_registered_quantities,
    check_61_envelope_currency,
    check_67_entry_units_are_declared,
    check_69_no_entry_cites_itself,
    check_70_one_version_one_answer,
    check_71_every_check_is_assigned_to_a_seat_that_can_write_it,
    check_42_check_registry, check_41_seat_attribution,
]


# --------------------------------------------------------------------------- #
# driver
# --------------------------------------------------------------------------- #


def run(roots: list[Path], include_rejected: bool = False, commit_range: str | None = None,
        staged: bool = False) -> list[Finding]:
    bundle = collect(roots, include_rejected)
    findings: list[Finding] = []
    for fn in CHECKS:
        try:
            if fn in (check_35_session_boundary, check_41_seat_attribution):
                findings.extend(fn(bundle, commit_range, staged))
            else:
                findings.extend(fn(bundle))
        except Exception as exc:                      # a broken check must not pass silently
            no = int(fn.__name__.split("_")[1])
            findings.append(Finding(no, FAIL, f"check raised {type(exc).__name__}: {exc}"))
    return findings


def describe_design_doc() -> str:
    """Which design document this run read, said out loud every time.

    `plan.md` is the record. `plan_ko.md` was canonical for a few hours on
    2026-09-20 and then left version control without leaving the disk, so a
    working copy can still hold it -- and a reader who opens it gets a stale
    document with no sign that it is one. Saying so here is the only warning
    there is. Same reason the tree line exists.
    """
    other = "plan.md" if DESIGN_DOC_NAME == "plan_ko.md" else "plan_ko.md"
    if not DESIGN_DOC.exists():
        return (f"design: neither {DESIGN_DOC_NAME} nor {other} is in this tree, so sections 7, 8 "
                "and 11 were read from nothing")
    if not (REPO / other).exists():
        return f"design: {DESIGN_DOC_NAME}, which is the only one present"
    # Tracked or not changes what the other file IS: a second document, or a
    # leftover that no clone has and nothing updates.
    import subprocess
    try:
        tracked = subprocess.run(["git", "-C", str(GIT_REPO), "ls-files", "--error-unmatch", other],
                                 capture_output=True, text=True).returncode == 0
    except OSError:
        tracked = True
    if not tracked:
        return (f"design: {DESIGN_DOC_NAME}, the document of record; {other} is also present, is "
                "in no commit, and was not read -- editing it changes nothing")
    return (f"design: {DESIGN_DOC_NAME}, the document of record; {other} is also present and "
            "was not read")


def describe_tree(staged: bool = False) -> str:
    """Which tree the verdict above is about.

    Five sessions share one working copy, so a bare run is nobody's commit: it
    holds everyone's half-finished edits at once. Twice in one day two seats
    quoted counts at each other and both were stale, and once a count that was
    read honestly off a run belonged to another agent's in-flight revision
    bump. The rule "read it off the run" is not enough on a shared copy -- the
    run has to say which tree it ran against, and saying it is cheaper to
    automate than to remember.
    """
    import subprocess

    def git(*args: str) -> str:
        return subprocess.run(["git", "-C", str(GIT_REPO), *args],
                              capture_output=True, text=True, check=True).stdout.strip()

    try:
        head = git("rev-parse", "--short", "HEAD")
        dirty = [x for x in git("status", "--porcelain").splitlines() if x.strip()]
    except (OSError, subprocess.CalledProcessError):
        return "tree: not a git checkout, so this verdict names no commit"
    if staged:
        return f"tree: the index as it would be committed, on top of {head}"
    if not dirty:
        return f"tree: {head}, clean"
    return (f"tree: {head} plus {len(dirty)} uncommitted paths, which is nobody's commit -- "
            f"a failure here may belong to another session")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="the deterministic gate (plan.md section 8)")
    ap.add_argument("paths", nargs="*", type=Path, default=None)
    ap.add_argument("--strict", action="store_true", help="UNDECIDED and PENDING count as failures")
    ap.add_argument("--expect-fail", action="store_true", help="every card given must fail at least one check")
    ap.add_argument("--commit-range", help="git range for check 35, e.g. HEAD~1..HEAD")
    ap.add_argument("--staged", action="store_true", help="run check 35 against the staged set; used by the pre-commit hook")
    ap.add_argument("--quiet", action="store_true", help="only print the verdict")
    args = ap.parse_args(argv)

    roots = args.paths or [REPO]
    roots = [r if r.is_absolute() else Path.cwd() / r for r in roots]
    include_rejected = args.expect_fail or any(REJECTED in r.parts for r in roots)
    findings = run(roots, include_rejected, args.commit_range, args.staged)

    counts = {s: sum(1 for f in findings if f.status == s) for s in (PASS, FAIL, UNDECIDED, PENDING, NA)}
    if not args.quiet:
        for f in findings:
            if f.status == PASS and args.expect_fail:
                continue
            print(f)
        print()

    if args.expect_fail:
        collected = collect(roots, True)
        cards = collected.cards + collected.artifacts
        failing_paths = {f.path for f in findings if f.status == FAIL}

        groups: dict[str, int] = {}
        flat: list[Card] = []
        for c in cards:
            g = fixture_group(c.rel)
            if g is None:
                flat.append(c)
            else:
                groups[g[0]] = g[1]

        unbroken = [c.rel for c in flat if c.rel not in failing_paths]
        print(f"expect-fail: {len(flat) - len(unbroken)}/{len(flat)} cards rejected as intended")

        ungrouped: list[str] = []
        for gdir, want in sorted(groups.items()):
            fails = [f for f in findings if f.status == FAIL and f.path.startswith(gdir + "/")]
            if want < 0:
                ungrouped.append(f"{gdir} does not name the check it is a fixture for (11-7)")
            elif not any(f.check == want for f in fails):
                got = sorted({f.check for f in fails})
                ungrouped.append(f"{gdir} is a fixture for check {want} and check {want} did not fail"
                                 + (f" (only {got})" if got else " (nothing failed)"))
        if groups:
            print(f"expect-fail: {len(groups) - len(ungrouped)}/{len(groups)} groups rejected as intended")

        if unbroken or ungrouped:
            for rel in unbroken:
                print(f"  NOT REJECTED  {rel}")
            for msg in ungrouped:
                print(f"  NOT REJECTED  {msg}")
            print("a card that stopped failing means a check stopped working")
            return 1
        return 0

    print(f"verdict: {counts[PASS]} passed, {counts[FAIL]} failed, "
          f"{counts[UNDECIDED]} undecided, {counts[PENDING]} pending, {counts[NA]} not applicable")
    print(describe_tree(args.staged))
    print(describe_design_doc())
    if counts[UNDECIDED]:
        print("undecided means a threshold nobody has chosen; it is not a threshold that is satisfied")
    if counts[FAIL]:
        return 1
    if args.strict and (counts[UNDECIDED] or counts[PENDING]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
