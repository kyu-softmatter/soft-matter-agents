# 005 — `check_budget` reads the old envelope shape, and I broke it

Written by `manager-simulation`. You read this; you do not edit it (§6.2-2).

**The person saved `envelope/safety.json` on 2026-09-20 at 10:33, so this is
live rather than impending.** Until then `read_envelope()` returned `None` and
the branch below was never reached; it is reached now. Confirmed against the
real tree, not a clone:

```
'smoke'  ->  KeyError: 'smoke_budget'
'full'   ->  'unavailable'   compared=0
```

**This is the only thing between here and the first entry in `runs/`.** Check 5
counts six converting ceilings — the microscope's two and this agent's four —
and the validator is otherwise green.

## What I did

`5e05d58` split `envelope_safety.schema.json` into a shared frame and a
per-agent `limits` block, so a ceiling moved one level down:

```
target["wall_clock_max"]            ->  target["limits"]["wall_clock_max"]
target["smoke_budget"]              ->  target["limits"]["smoke_budget"]
```

`src/operator.py` still reads the flat shape:

```python
ceilings = targets[target]
limits = ceilings["smoke_budget"] if budget == SMOKE else ceilings
```

## What it does, run rather than reasoned

A clone with the real new-shape file in place, calling `check_budget` directly:

```
budget='smoke'  ->  KeyError: 'smoke_budget'
budget='full'   ->  status='unavailable'   compared=0
```

**Both are fail-closed, and only one of them is honest.** No wrong run escapes
— the design caught my mistake, because `check_budget` reports `unavailable`
rather than waving through, and *"an unavailable ceiling is not a satisfied
one"* is written into the module's own docstring. But a `KeyError` is a crash
and not a refusal, and `compared=0` is the check **saying it compared when it
compared nothing**. If a later change ever turned `unavailable` into a pass,
that second line is what would let a run through.

## The fix looks like two lines, and it is yours to make

Descend once where the target row is taken, and leave the smoke branch alone —
`smoke_budget` still sits inside `limits` and still carries its own
`wall_clock_max` and `storage_max`, each with its own `confirmation`:

```python
ceilings = targets[target]["limits"]
```

Check the shape yourself against `contracts/schemas/envelope_safety.schema.json`
rather than taking this diff — I am the one who got it wrong last time.

**Since verified end to end**, in a clone with a real simulation
`envelope/safety.json` in place. Before the change: `smoke` raises
`KeyError`, `full` returns `unavailable` having compared nothing. After the
single line above, and nothing else:

```
'smoke'  ->  'inside'   compared=2   exceeded=[]
'full'   ->  'inside'   compared=2   exceeded=[]
```

Two ceilings actually compared instead of zero, and the smoke branch reaches
`smoke_budget` inside `limits` without further change. The validator stays at
`0 failed` with that envelope present, and check 5 counts six converting
ceilings — the microscope's two and this agent's four.

## Why the gate did not catch it, which is the part worth keeping

I tested the schema in nine cases and every one passed. **I never ran the code
that reads the schema.** Check 1 validates a file against a schema; nothing
validates a *reader* against one, and no check in this repository does. So the
contract and its consumer drifted apart inside one commit and the gate was
green throughout.

That is the migrate step of loosen → migrate → tighten, and I skipped it. I
loosened the shape and went on. The rule is not "test the schema" — it is
**find who reads it and run them**, and here that was one file in this tree
that I could have named in a grep.

## The environment, while you are here

`uv` is installed and there is a `.venv` at the repository root —
`.gitignore` already carried `.venv/`, so the place was expected.

```bash
.venv/bin/python contracts/validate.py          # 42 passed, 0 failed
```

It holds `jsonschema`, `referencing` and `numpy`, counted off the imports in
`contracts/validate.py` and `simulation_agent/src/*.py` rather than listed from
memory. Nothing else in either is outside the standard library.

**HOOMD is not in it and cannot be.** `uv pip install --dry-run hoomd` returns
*not found in the package registry* — HOOMD-blue ships through conda-forge, not
PyPI. So the engine is a separate install on any machine and `uv sync` gets the
pipeline without it.

**That split matches the design rather than fighting it.** §9.2 rule 4 attaches
the engine only after the pipeline passes with mock, and §4.6 makes
`mock_backend.py` a first-class backend, so a machine with the validator and
the mock can do all of M2's verification. Worth saying plainly because
`runs/` is **empty** — not one run has happened, mock included, and that is a
long way in front of HOOMD. One of the two things blocking the first mock run
is the bug at the top of this card.

## What is not committed, and why

`pyproject.toml` and `uv.lock` are written and tested — `uv sync` from empty
pulls all three packages — and **neither can be committed yet.** Check 13
refuses both: *declared in neither `plan.md` §7 nor `ALLOWED_PATHS`, and it
needs BOTH.* §7 is architecture's and `ALLOWED_PATHS` is this seat's.

I did not land my half alone, and the reason is not caution. **A new root file
has no owner.** Architecture's `paths` enumerate the root files —`plan.md`,
`CLAUDE.md`, `ARCHITECT.md`, `README.md`, `.claude/`, `.mcp.json`,
`seats.json` — and `pyproject.toml` is in no seat's list. Opening the path in
`ALLOWED_PATHS` would let check 13 through while check 41 could not say who may
commit it: a path open with no boundary behind it, which is §11-11's shape.

The content, so it survives this session (§6.2-2):

```toml
[project]
name = "soft-matter-agents"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["jsonschema>=4.0", "referencing>=0.30", "numpy>=1.26"]
```

Raised with architecture — who was not reachable, which is why it is here.
