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
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

CONTRACTS = Path(__file__).resolve().parent
REPO = CONTRACTS.parent

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

    def of_kind(self, *kinds: str) -> list[Card]:
        return [c for c in self.cards if c.kind in kinds]

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
    return b


def plan_hash(plan: dict) -> str:
    """sha256 of a plan card with status removed.

    Status moves along the state machine on the same file (5.5), so hashing it
    would void an approval at the instant it was granted.
    """
    body = {k: v for k, v in plan.items() if k != "status"}
    blob = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(blob.encode()).hexdigest()


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
        out.append(Finding(1, PENDING, "jsonschema not installed: only the card discriminator was checked"))
        return out

    resources = {}
    for f in (CONTRACTS / "schemas").glob("*.json"):
        resources[f.name] = Resource.from_contents(json.loads(f.read_text()))
    registry = Registry().with_resources(resources.items())

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
        out.append(Finding(1, PASS, f"{len(cards)} cards conform to their schema"))
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
    envs = list(REPO.glob("*_agent/envelope/safety.json"))
    if not envs:
        return [Finding(5, PENDING, "needs envelope/safety.json, which M1 produces (section 9)")]
    return [Finding(5, PENDING, "envelope comparison not implemented yet")]


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


def check_08_bridge(b: Bundle) -> list[Finding]:
    asks = b.of_kind("ask_simulation", "ask_experiment")
    if not asks:
        return [Finding(8, NA, "no ask cards")]
    out: list[Finding] = []
    for c in asks:
        payload = c.data.get("payload_card") or {}
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        expect = "sha256:" + hashlib.sha256(blob.encode()).hexdigest()
        if c.data.get("payload_hash") != expect:
            out.append(Finding(8, FAIL, f"payload_hash mismatch: expected {expect}", c.rel))
        ans = c.data.get("answerability") or {}
        capfile = CONTRACTS / "capabilities" / str(ans.get("checked_against", ""))
        if not capfile.exists():
            out.append(Finding(8, FAIL, f"answerability cites {ans.get('checked_against')!r}, which does not exist", c.rel))
            continue
        cap = json.loads(capfile.read_text())
        known = {o["id"] for o in json.loads((CONTRACTS / "observables.json").read_text()).get("observables", [])}
        for conf in cap.get("configurations", []):
            for o in conf.get("observables", []):
                if o.get("name") not in known:
                    out.append(Finding(8, FAIL, f"{capfile.name} claims observable {o.get('name')!r}, which contracts/observables.json does not define", c.rel))
        if cap.get("status") == "skeleton":
            out.append(Finding(8, PENDING, f"{capfile.name} is a skeleton; answerability cannot be verified until 11-10 lands", c.rel))
    return out or [Finding(8, PASS, f"{len(asks)} ask cards hash and check out")]


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
    names = {c.path.name for c in axes}
    ids = {c.data.get("id") for c in axes}
    callers = {c.data.get("caller_id") for c in axes}
    for c in axes:
        blob = json.dumps(c.data, ensure_ascii=False)
        for other in axes:
            if other is c:
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
    r"^(plan\.md|CLAUDE\.md|README\.md|\.gitignore|\.mcp\.json)$",
    r"^contracts/(units\.md|units\.json|observables\.json|validate\.py|validation_limits\.json)$",
    r"^contracts/schemas/[A-Za-z0-9_.-]+\.json$",
    r"^contracts/capabilities/[A-Za-z0-9_.-]+\.json$",
    r"^contracts/examples/(rejected/)?[A-Za-z0-9_.-]+\.(json|md|jsonl)$",
    r"^(microscope|simulation)_agent/CLAUDE\.md$",
    r"^(microscope|simulation)_agent/envelope/[A-Za-z0-9_.-]+$",
    r"^(microscope|simulation)_agent/approvals/[A-Za-z0-9_.-]+$",
    r"^(microscope|simulation)_agent/questions/[a-z0-9-]+/[A-Za-z0-9_.-]+$",
    r"^(microscope|simulation)_agent/runs/[a-z0-9-]+/([A-Za-z0-9_.-]+|raw/.*)$",
    r"^(microscope|simulation)_agent/src/([A-Za-z0-9_.-]+|devices/[A-Za-z0-9_.-]+)$",
    r"^librarian_agent/CLAUDE\.md$",
    r"^librarian_agent/kb/(index\.json|(sources|distilled|entries|lessons|staging|exports)/[A-Za-z0-9_.-]+)$",
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
    return out or [Finding(13, PASS, f"{n} files sit in declared paths")]


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
                    out.append(Finding(17, FAIL, f"{name} is marked derived but its source is {src!r}; a dimensionless group uses computed: (5.7)", c.rel))
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
        out.append(Finding(18, PENDING, "subset-of-envelope test needs envelope/safety.json from M3"))
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
                out.append(Finding(25, PENDING, f"kb_ref {r.get('entry_id')} pins {r['kb_version']}, which is not the store's current {KB_INDEX.get('kb_version')}; confirming an older version needs the store's git history", c.rel))
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
    required = {"at", "kind", "qid", "detail"}
    kinds = {"validator_failure", "refusal", "deviation", "scope_voided", "success"}
    for p in files:
        for i, line in enumerate(p.read_text().splitlines(), 1):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                out.append(Finding(29, FAIL, f"line {i}: {exc}", str(p.relative_to(REPO))))
                continue
            missing = required - set(rec)
            if missing:
                out.append(Finding(29, FAIL, f"line {i}: missing {sorted(missing)}", str(p.relative_to(REPO))))
            if rec.get("kind") not in kinds:
                out.append(Finding(29, FAIL, f"line {i}: unknown kind {rec.get('kind')!r}", str(p.relative_to(REPO))))
    return out or [Finding(29, PASS, f"{len(files)} failure records are well formed")]


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
    for qid, group in {q: [c for c in axes if c.data.get("qid") == q] for q in {c.data.get("qid") for c in axes}}.items():
        callers = [c.data.get("caller_id") for c in group]
        if len(set(callers)) != len(callers):
            dupes = {x for x in callers if callers.count(x) > 1}
            out.append(Finding(33, FAIL, f"qid {qid}: caller_id reused {sorted(dupes)}; each sub-agent gets its own (4.3.1)"))
        versions = {c.data.get("kb_version") for c in group}
        if len(versions) > 1:
            out.append(Finding(33, FAIL, f"qid {qid}: siblings cite different kb_version {sorted(versions)}; S3.0 pins one"))
        for c in group:
            want = f"{c.data.get('qid')}:{c.data.get('config')}:{c.data.get('axis')}"
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
SHARED_PATHS = re.compile(r"^(plan\.md|CLAUDE\.md|README\.md|\.gitignore|\.mcp\.json|\.claude/)")

# An agent's CLAUDE.md and .claude/ belong to the design seat, not to the agent
# (6.2). Counting them as the agent's made every ordinary design commit look
# like a boundary crossing, which is the fastest way to teach someone to ignore
# a check.
DESIGN_OWNED = re.compile(r"^((microscope|simulation|librarian)_agent|bridge)/(CLAUDE\.md|\.claude/)")


def check_35_session_boundary(b: Bundle, commit_range: str | None = None) -> list[Finding]:
    """One session writes inside one agent (6.2).

    A commit touching two agent directories came from a session that could see
    both, which is the thing the session split exists to prevent.
    """
    if not commit_range:
        return [Finding(35, PENDING, "pass --commit-range to inspect commits; hooks enforce this at commit time (6.2)")]
    import subprocess
    try:
        proc = subprocess.run(["git", "-C", str(REPO), "diff", "--name-only", commit_range],
                              capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        return [Finding(35, FAIL, f"cannot read commit range {commit_range!r}: {exc}")]
    paths = [p for p in proc.stdout.splitlines() if p.strip()]
    if not paths:
        return [Finding(35, NA, f"no files changed in {commit_range}")]
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
        return out
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
            if not num.get("derived") or num.get("origin"):
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
            if e.get("kind") != "dimensionless_group" or not e.get("symbol"):
                continue
            sym, formula = e["symbol"], e.get("formula")
            if sym in defs and defs[sym][0] != formula:
                out.append(Finding(36, FAIL, f"symbol {sym!r} is {defs[sym][0]!r} in {defs[sym][1]} but the store defines it as {formula!r} (5.7)", "librarian_agent/kb/index.json"))
    elif n:
        out.append(Finding(36, PENDING, f"{n} ad-hoc groups checked against each other; comparing them with the store needs kb/index.json"))
    return out or [Finding(36, PASS if n else NA, f"{n} dimensionless group definitions do not collide" if n else "no dimensionless groups")]


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

    Prefers kb/exports/, which is where the librarian publishes (4.3.2), and
    falls back to the flat staging table it has not decomposed yet (11.1).
    """
    for cand in sorted((KB_DIR / "exports").glob("optical_paths*.json")):
        return json.loads(cand.read_text()), str(cand.relative_to(REPO))
    staged = KB_DIR / "staging" / "optical_paths.v0.json"
    if staged.exists():
        return json.loads(staged.read_text()), str(staged.relative_to(REPO))
    return None, ""


def check_38_one_table(b: Bundle) -> list[Finding]:
    """A configuration list and an optical path list are one table (4.6.7).

    Two tables drift, and the drift shows up as a plan that is valid on paper
    while no light reaches the detector.
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

        for conf in configs:
            for oid in conf.get("produces", []) or []:
                if oid not in known_obs:
                    out.append(Finding(38, FAIL, f"configuration {conf.get('config')!r} produces {oid!r}, which contracts/observables.json does not define", rel))

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
        for conf in configs:
            ref = conf.get("optical_path")
            if ref is None:
                out.append(Finding(38, FAIL, f"configuration {conf.get('config')!r} declares no optical_path", rel))
            elif ref not in table_ids:
                out.append(Finding(38, FAIL, f"configuration {conf.get('config')!r} points at optical path {ref!r}, which {table_rel} does not have", rel))

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
]


# --------------------------------------------------------------------------- #
# driver
# --------------------------------------------------------------------------- #


def run(roots: list[Path], include_rejected: bool = False, commit_range: str | None = None) -> list[Finding]:
    bundle = collect(roots, include_rejected)
    findings: list[Finding] = []
    for fn in CHECKS:
        try:
            if fn is check_35_session_boundary:
                findings.extend(fn(bundle, commit_range))
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
    ap.add_argument("--quiet", action="store_true", help="only print the verdict")
    args = ap.parse_args(argv)

    roots = args.paths or [REPO]
    roots = [r if r.is_absolute() else Path.cwd() / r for r in roots]
    include_rejected = args.expect_fail or any(REJECTED in r.parts for r in roots)
    findings = run(roots, include_rejected, args.commit_range)

    counts = {s: sum(1 for f in findings if f.status == s) for s in (PASS, FAIL, UNDECIDED, PENDING, NA)}
    if not args.quiet:
        for f in findings:
            if f.status == PASS and args.expect_fail:
                continue
            print(f)
        print()

    if args.expect_fail:
        cards = collect(roots, True).cards
        failing_paths = {f.path for f in findings if f.status == FAIL}
        unbroken = [c.rel for c in cards if c.rel not in failing_paths]
        print(f"expect-fail: {len(cards) - len(unbroken)}/{len(cards)} cards rejected as intended")
        if unbroken:
            for rel in unbroken:
                print(f"  NOT REJECTED  {rel}")
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
