# 019 — detect the engine, and say so when it is missing

Written by `manager-simulation`. You read this; you do not edit it (§6.2-2).
**Held by `simulation-2`, which asked for a number after starting** — the
work was already under way when the ruling arrived, and this card records it
rather than assigning it.

## The ruling this implements

Architecture amended §4.6.5 on the person's instruction (`de438d0`):

> mock is a first-class backend, and **where HOOMD is present it does not
> run**. The pipeline still has to run with no hardware and no HOOMD — that
> is what keeps the mock first-class — but **the engine's presence decides
> which one executes.**
>
> **A mock-only run says so and says what to do about it.** Falling back
> quietly is what the amendment forbids: the operator runs the mock **and
> emits an install instruction naming the platform it is on**. The point is
> that the mock stops being an invisible default, the same shape as
> `degraded` carrying the librarian's name: **the reduced path is legitimate
> and never silent.**

`018` put a default swap in — `backend or HoomdBackend(seed=seed)` — and that
is one notch short: on a machine without HOOMD it dies mid-run at the import.
The ruling asks for **detection**, and `simulation-4` said so rather than
fixing it into a file another seat was editing.

## What is already in, and the part that is right

`85acb62` and what follows it: `engine_check.py`, `engine_build` in the
preflight report, the existing-run-dir refusal, `environment.yml`.

**Recording the fallback as a log event, not only on stderr, is the part
worth keeping.** `engine_missing` with `fell_back_to` and the instruction
means a session reset cannot lose that the reduced path was taken — stderr
belongs to whoever was watching. That is `degraded`'s shape exactly, and it
was not asked for.

## The one ruling this card adds: `environment.yml` is a stopgap and must say so

Architecture chose **pixi**, in `pyproject.toml` as `[tool.pixi.*]`, one file
with platform branching: shared dependencies in the base, the split ones in
`sim` and `mic` features, and `sim` omitting `win-64` so a Windows solve has
no simulation environment rather than failing.

**So `src/environment.yml` and the pixi tables are two manifests for one
machine.** Architecture named that risk and it is real: the seat kept
`jsonschema` and `referencing` in the yml for a reason that holds — dropping
them yields an interpreter that cannot run `contracts/validate.py`, and the
file's whole point is one interpreter for validator, mock and engine.

**Keep them, and make the file say what ends it.** pixi is not installed on
this machine and `pixi.lock` does not exist, so the yml is the only thing that
currently produces a working environment. That is a true reason and it expires.
Write into the file:

- that it is a stopgap while pixi is unavailable here,
- that `pyproject.toml`'s `[tool.pixi.*]` is the declaration of record,
- and **the condition under which this file goes**: `pixi.lock` exists and
  resolves on this platform.

Without that line the two drift silently, which is the class this repository
spent two days counting. **A second manifest with an expiry is a bridge; one
without is a fork.**

`gsd` carrying its why-now line is right and matches architecture: it enters
the pixi tables in the commit where `013` first imports it, not before.

## Open, and not yours to settle

**Who declares `jsonschema` and `referencing` for conda** is with architecture.
If the ruling is to cut them from the yml, the seat has said it is a two-line
change. Do not pre-empt it in either direction.

## Closed at f15b436, with this card's own condition corrected

Both items above are settled, and one of them was settled against what this
card wrote.

**The expiry condition here was the weaker of the two available.** This card
asked for "`pixi.lock` exists and resolves on this platform". Architecture
narrowed it to **"`pixi install -e sim` succeeds and `contracts/validate.py`
runs in that interpreter"**, and that is the better line for the reason this
repository keeps arriving at from other directions: a file existing is prose,
and the validator running under that interpreter is execution. A lock file can
sit on disk while the environment it describes has never once been built, which
is the same shape as a constant a contract names and no code reads. The
condition I wrote would have been satisfiable without anyone ever having run
the thing the bridge exists to make unnecessary.

Recorded rather than quietly matched: a card whose condition is replaced should
say which one it had, or the next reader cannot tell a sharpened rule from a
rule that was always this.

**`jsonschema` and `referencing` are no longer open.** They are declared of
record in `pyproject.toml`'s `[tool.pixi.dependencies]` workspace base, so
there was nothing left to rule. The seat held in neither direction while it was
open, which was the right handling of a question that was not its to settle.

`gsd` is unchanged and still enters the pixi tables in the commit where `013`
first imports it, not before.
