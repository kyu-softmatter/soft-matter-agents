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
    cap = LIMITS.get("max_e5_per_plan")
    if cap is None:
        counts = ", ".join(f"{k}: {v}" for k, v in e5_by_plan.items()) or "none"
        out.append(Finding(3, UNDECIDED, f"per-plan E5 cap is unset ({LIMITS['max_e5_per_plan_open_question']}); counted E5 = [{counts}]"))
    else:
        for rel, n in e5_by_plan.items():
            if n > cap:
                out.append(Finding(3, FAIL, f"{n} E5 numbers exceed the cap of {cap}", rel))
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


def check_05_envelope(b: Bundle) -> list[Finding]:
    """The ceilings a person wrote, and whether a run could read them (2.1 rule 7).

    The shape is envelope_safety.schema.json's business and check 1 holds it.
    What a schema cannot hold is the unit: it would have to name the units it
    allows, and a second list of units drifts from units.json. So the one thing
    checked here is that every ceiling converts -- because the alternative is
    that it does not, at run time, inside si(), long after the person wrote it.
    """
    envs = sorted(REPO.glob("*_agent/envelope/safety.json"))
    if not envs:
        return [Finding(5, PENDING, "no envelope/safety.json yet; a person writes it (2.1 rule 7, 10.3 rule 4)")]
    out: list[Finding] = []
    n = 0
    for env in envs:
        rel = str(env.relative_to(REPO))
        try:
            doc = json.loads(env.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            out.append(Finding(5, FAIL, f"cannot be read: {exc}", rel))
            continue
        for target in doc.get("targets", []) or []:
            where = f"targets[{target.get('target')!r}]"
            rows = [(where, target)] + [
                (f"{where}.smoke_budget", target.get("smoke_budget") or {})
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


def check_06_criteria(b: Bundle) -> list[Finding]:
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
            for cr in items:
                if cr.get("number") not in nums:
                    out.append(Finding(6, FAIL, f"{kind}[{cr.get('id')}] points at {cr.get('number')!r}, which is not in numbers[]", c.rel))
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
    by_thread: dict[str, list[Card]] = {}
    for c in asks:
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
            continue          # the source moved on; the round is not comparable, and saying so beats a false pass
        if card_sha(on_disk) != src.get("sha256"):
            out.append(Finding(8, FAIL, "the source card at the recorded revision does not hash to the recorded value: either it was edited without a revision bump, or the payload is not what was sent. Stop the round; do not repair it (4.4 failure table)", h.rel))
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
ORIGIN_RE = re.compile(r"^(axis_[a-z0-9_]+\.json|goal[a-z0-9_]*\.json|synthesis[a-z0-9_]*\.json|plan_[a-z0-9_.-]+\.json)#[a-z][a-z0-9_]*$")


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
    r"^(plan\.md|CLAUDE\.md|ARCHITECT\.md|README\.md|\.gitignore|\.mcp\.json)$",
    r"^contracts/(units\.md|units\.json|observables\.json|seats\.json|validate\.py|validation_limits\.json)$",
    r"^contracts/schemas/[A-Za-z0-9_.-]+\.json$",
    r"^contracts/hooks/[a-z-]+$",
    r"^contracts/capabilities/[A-Za-z0-9_.-]+\.json$",
    r"^contracts/examples/(rejected/)?[A-Za-z0-9_.-]+\.(json|md|jsonl)$",
    r"^contracts/examples/rejected/check[0-9]{2}_[a-z0-9_]+/[A-Za-z0-9_.-]+\.(json|md|jsonl)$",
    r"^microscope_agent/tasks/[A-Za-z0-9_.-]+$",
    r"^simulation_agent/tasks/[A-Za-z0-9_.-]+$",
    r"^(microscope|simulation)_agent/CLAUDE\.md$",
    r"^(microscope|simulation)_agent/envelope/[A-Za-z0-9_.-]+$",
    r"^(microscope|simulation)_agent/approvals/[A-Za-z0-9_.-]+$",
    r"^(microscope|simulation)_agent/questions/[a-z0-9-]+/[A-Za-z0-9_.-]+$",
    r"^(microscope|simulation)_agent/runs/[a-z0-9-]+/([A-Za-z0-9_.-]+|raw/.*)$",
    r"^(microscope|simulation)_agent/src/([A-Za-z0-9_.-]+|devices/[A-Za-z0-9_.-]+)$",
    r"^librarian_agent/CLAUDE\.md$",
    r"^((microscope|simulation|librarian)_agent|bridge)/failures\.jsonl$",
    r"^librarian_agent/kb/(index\.json|(sources|distilled|entries|lessons|staging|exports)/[A-Za-z0-9_.-]+)$",
    r"^librarian_agent/queries/[A-Za-z0-9_.-]+$",
    r"^librarian_agent/tasks/[A-Za-z0-9_.-]+$",
    r"^bridge/tasks/[A-Za-z0-9_.-]+$",
    r"^librarian_agent/src/[A-Za-z0-9_.-]+$",
    r"^bridge/CLAUDE\.md$",
    r"^bridge/threads/[a-z0-9-]+/[A-Za-z0-9_.-]+$",
    r"^(microscope|simulation|librarian)_agent/\.claude/.*$",
    r"^bridge/\.claude/.*$",
    r"^\.claude/.*$",
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
            out.append(Finding(13, FAIL, "path is not declared in plan.md section 7 (7.1 rule 7)", rel))
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
    runs = list(REPO.glob("*_agent/runs/*"))
    if not runs:
        return [Finding(15, NA, "no runs on disk")]
    return [Finding(15, PENDING, "run directories exist; approval precedence not implemented yet")]


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
            missing = [i for i in inputs if i not in env and i not in CONSTANTS]
            if missing:
                out.append(Finding(17, FAIL, f"{name} reads {missing}, which are not numbers of this card", c.rel))
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
    return out or [Finding(17, PASS, f"{n_computed} computed values recompute from their formulas")]


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
    envs = list(REPO.glob("*_agent/envelope/safety.json"))
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


def check_21_grade_derivation(b: Bundle) -> list[Finding]:
    out: list[Finding] = []
    n = 0
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
            elif prefix == "computed":
                inputs = num.get("inputs") or []
                grades = [nums[i]["grade"] for i in inputs if i in nums]
                expect = "E4"
                for g in grades:
                    expect = worse(expect, g)
                if declared != expect:
                    out.append(Finding(21, FAIL, f"{name}: computed from {grades or 'constants'} gives max(E4, worst) = {expect}, card says {declared}", c.rel))
    return out or [Finding(21, PASS, f"{n} grades follow from their sources")]


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
                    # Compared by content hash, not field by field. Which
                    # fields reach a card is not written down anywhere, so
                    # choosing a subset would invent a contract; over-reporting
                    # is the safe direction until one exists.
                    continue
                out.append(Finding(25, PENDING, f"kb_ref {eid} pins {r['kb_version']} ({sha[:7]}) and the entry has changed since; the grade it claims held then, and what moved needs reading", c.rel))
                continue
            stored = (KB_INDEX.get("entries") or {}).get(r.get("entry_id"))
            if stored is None:
                out.append(Finding(25, FAIL, f"kb_ref cites {r.get('entry_id')!r}, which the store does not have", c.rel))
            elif stored.get("grade") != r.get("grade"):
                out.append(Finding(25, FAIL, f"kb_ref {r.get('entry_id')} claims {r.get('grade')} but the store says {stored.get('grade')}", c.rel))

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
    snaps = list(REPO.glob("*_agent/envelope/snapshot.json"))
    if not snaps:
        return [Finding(26, PENDING, "needs envelope/snapshot.json (M1) and the KB it is exported from (M3)")]
    return [Finding(26, PENDING, "snapshot hash comparison not implemented yet")]


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
            owners = {k for k in ("qid", "task") if rec.get(k)}
            if not owners:
                out.append(Finding(29, FAIL, f"line {i}: names neither a qid nor a task, so nothing says what this attempt belonged to", str(p.relative_to(REPO))))
            elif len(owners) == 2:
                out.append(Finding(29, FAIL, f"line {i}: names both a qid and a task; one record belongs to one of them", str(p.relative_to(REPO))))
            if rec.get("kind") not in kinds:
                out.append(Finding(29, FAIL, f"line {i}: unknown kind {rec.get('kind')!r}", str(p.relative_to(REPO))))
    return out or [Finding(29, PASS, f"{n_records} failure records in {len(files)} files are well formed")]


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
    def scope(card) -> str:
        return str(Path(card.rel).parent)

    # And the same argument a second time, for the same reason. A revision is a
    # re-run (4.5.5), so two revisions are two fan-outs and their cards are not
    # each other's siblings. caller_id is <qid>:<config>:<axis> with no revision
    # component (4.3.1), so the same axis at two revisions necessarily shares
    # one -- grouping without the revision made "caller_id reused" fire on a
    # question that had done nothing wrong, and made 4.5.5's own instruction
    # unfollowable.
    groups: dict[tuple[str, str, object], list] = {}
    for c in axes:
        groups.setdefault((scope(c), c.data.get("qid"), c.data.get("revision")), []).append(c)

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
SHARED_PATHS = re.compile(r"^(plan\.md|CLAUDE\.md|ARCHITECT\.md|README\.md|\.gitignore|\.mcp\.json|\.claude/)")

# An agent's CLAUDE.md and .claude/ belong to the design seat, not to the agent
# (6.2). Counting them as the agent's made every ordinary design commit look
# like a boundary crossing, which is the fastest way to teach someone to ignore
# a check.
DESIGN_OWNED = re.compile(r"^((microscope|simulation|librarian)_agent|bridge)/(CLAUDE\.md|\.claude/|tasks/)")


def seat_boundary_of(path: str) -> str:
    """Whose territory a path is in (6.2.1).

    The same split check 35 counts, named instead of counted. One table, so a
    seat's boundary and a commit's boundary cannot drift apart.
    """
    if SHARED_PATHS.match(path) or DESIGN_OWNED.match(path) or path.startswith("contracts/"):
        return "design"
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
        if SHARED_PATHS.match(p) or DESIGN_OWNED.match(p):
            design_paths.append(p)
            continue
        if p.startswith("contracts/"):
            contracts_touched.append(p)
        for rx, agent in AGENT_OF_PATH:
            if rx.match(p):
                touched.setdefault(agent, []).append(p)
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


def check_37_time_base(b: Bundle) -> list[Finding]:
    results = b.of_kind("result")
    if not results:
        return [Finding(37, NA, "no result cards")]
    out: list[Finding] = []
    for c in results:
        tb = c.data.get("time_base") or {}
        align = tb.get("alignment")
        if align == "software_monotonic":
            out.append(Finding(37, FAIL, "physics rests on the software monotonic clock; use a trigger counter or a device timestamp (4.6.9)", c.rel))
        if not tb.get("t0_wall"):
            out.append(Finding(37, FAIL, "no t0_wall: events cannot be placed on a common axis", c.rel))
    if not list(REPO.glob("*_agent/runs/*/log.json")):
        out.append(Finding(37, PENDING, "per-event offsets need run logs from M1"))
    return out or [Finding(37, PASS, f"{len(results)} results rest on a hardware time base")]


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
        elif prefix == "computed":
            # the formula is itself an assumption, so a computed value is E4 at
            # best and follows its worst input down (5.3)
            if declared not in ("E4", "E5"):
                out.append(Finding(43, FAIL, f"{eid}: computed: is E4 at best and never better, the entry says {declared}", rel))
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
        return [Finding(43, PENDING, f"{derived} entry grades derive from their source; {len(without)} carry no `source` yet, so those grades are still self-reported ({shown}{more}). The librarian seat fills the field, and then it becomes required")]
    return [Finding(43, PASS, f"{derived} entry grades follow from their source kind")]


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

    registries = {"device": (device_ids, dev_rel or "the device table"),
                  "configuration": (config_ids, path_rel or "the optical path table"),
                  "observable": (observable_ids, "contracts/observables.json"),
                  "quantity": (quantity_names, "the names used in numbers[]")}

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

    plan = REPO / "plan.md"
    if not plan.exists():
        return [Finding(42, PENDING, "plan.md is not in this tree, so the declarations cannot be read")]
    body = plan.read_text()
    try:
        section = body.split("## 8. 검증 계층")[1].split("### 8.1")[0]
    except IndexError:
        return [Finding(42, FAIL, "cannot find section 8's check list in plan.md", "plan.md")]
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
                                            f"as in progress under {who}", "plan.md"))
        elif not sides:
            out.append(Finding(42, PENDING, f"check {n} is assigned to {who} and neither declared nor implemented",
                               "plan.md"))

    for label, missing, where in (
        ("declared but not implemented", declared - implemented - set(in_progress), "plan.md"),
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
            return [Finding(41, unknown_status,
                            f"{pre}committer {email!r} is not a seat in contracts/seats.json, so these "
                            f"{len(paths)} paths carry no attribution")]
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
    check_40_window_condition, check_43_entry_grade, check_46_vocabulary_pin, check_44_subject_resolves,
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
    if counts[UNDECIDED]:
        print("undecided means a threshold nobody has chosen; it is not a threshold that is satisfied")
    if counts[FAIL]:
        return 1
    if args.strict and (counts[UNDECIDED] or counts[PENDING]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
