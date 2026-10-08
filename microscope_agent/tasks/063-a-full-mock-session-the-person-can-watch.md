# 063 — one full mock session, with the console attached and the person watching

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-20261003-1`, after card 062 lands.** If you are not
that seat, take nothing from this card and report up. The person asked for it
on 2026-10-07, in architecture's window: finish live view, then one mock test
of the whole system they can watch in the console's web page.

**Mock only. Nothing touches the instrument. Nothing in this repository's
`envelope/` or `approvals/` is read or written: everything is a scratch copy.
The console runs no code of ours.**

## The scratch root — one path for the whole session

**`<SCRATCH>` = `D:/sma-scratch/063`.** Architecture, the console and you all
use this path. It is short on purpose, because a long scratch path on Windows
silently drops deep files. It mirrors this repository's layout, because the
console's store expects it:

```
D:/sma-scratch/063/microscope_agent/runs/<run_id>/     runs (the console reads here)
D:/sma-scratch/063/microscope_agent/envelope/safety.json   TEST values
D:/sma-scratch/063/microscope_agent/approvals/          TEST approvals and the live-view list
D:/sma-scratch/063/microscope_agent/questions/          the session's plan cards
D:/sma-scratch/063/librarian_agent/kb/entries/          one TEST store entry
```

The console is launched by its own session:

```
uv run --directory D:/codes/github/dino-autofocus-wt/console python -m dino_autofocus.server --backend placeholder --port 8792 --store sma --sma-root D:/sma-scratch/063
```

The person watches at `http://127.0.0.1:8792`.

**Every value in the scratch envelope, approvals and store is a TEST value,
and says so in its own `note`**: `TEST VALUE for card 063 on mock -- not the
person's, never copied to envelope/safety.json`. Test values never leave
`<SCRATCH>`: they are not committed and not copied anywhere else. **Leave
`<SCRATCH>` in place afterwards.** Whether to delete it is the person's call.

## Part A — what must exist first. Build it, with tests watched failing

Read the tree first; some of this may already exist from cards 055, 059 and
062. Build only what is missing, and say which parts were already there.

1. **The decider uses the copied focus core.** A `focus_search` with
   `decided_by: metric_maximum` takes its branch from `focus_verdict` over the
   frames the search takes, scored by `focus_classical`. The arguments come
   only from the plan's fields: `metric_arguments.bin_px`,
   `metric_arguments.blocks_per_side`, `max_extensions`, and `camera_ceiling`
   resolved through `numbers[]`. **A ceiling that is a gap refuses before the
   first Z command**, and nothing substitutes a value. The decider gives a
   branch, and the gate derives the move, as card 055 built.
2. **A scratch root, on mock only.** `operator.run` (and whatever reads the
   envelope, approvals, the store and the live-view lists) can be given one
   root to read and write under, instead of this repository's tree. **With
   any backend but `mock`, a non-default root refuses before anything is
   loaded.** A test proves that. A scratch envelope must never be able to
   reach the instrument.

Tests, each watched failing first:
- a gap ceiling refuses with no Z write;
- a sourced ceiling lets the core pick a branch on mock frames;
- the micromanager backend with a scratch root refuses;
- the default root still reads `microscope_agent/` exactly as before.

## Part B — the session, in this order

**Before starting:**

- **Write `<SCRATCH>`'s TEST files.**
  - The envelope has `focus_z_<objective>_{min,max}` for five lenses and
    **deliberately none for 20x**, which step 3 needs.
  - The live-view list follows `contracts/schemas/live_view_list.schema.json`,
    with a TEST lamp intensity and a frame ceiling.
  - The store entry is `TEST_mock_camera_full_scale`: the full-scale count of
    the frames `devices/mock.py` generates, read off that code, in ADU.
  - Write the plan approvals each step needs.
- **Run check 88 on the focus plan against the scratch envelope and store**,
  by calling `check_88_focus_search` with the envelope and `KB_DIR` pointed
  into `<SCRATCH>`. This is a measurement of the plan, not a validator run
  over this repository. It must PASS, with the ceiling citing the TEST entry.
- Tell the session **"AF 화면 · SMA 실행 보기와 멈춤 연결"** that `<SCRATCH>` is
  ready. Then, for every run below, send it the run id and the folder
  as the run starts.

**1. Live view on, then off, from the console.** The person or the console
sends `live_on` naming the TEST list's sha256. The host starts the run, and the
console views frames. Then Abort turns it off: the lamp goes off and the
sequence stops.

**2. A focus search on mock.** The plan passes check 88 as above, with its
approval in `<SCRATCH>/microscope_agent/approvals/`. It walks Z through the
gate with the copied core picking each branch. Record every decision, its
branch, the derived target, and the encoder read after each move.

**3. Each of card 055's refusals, once, with no Z write:**
- no limit: a plan at 20x;
- the wrong lens: a hand-over naming another lens than the plan's;
- PFS on: mock's PFS reading engaged;
- not approved: no approval for the revision;
- above the max: a target one step over `focus_z_<objective>_max`;
- and **the ceiling gap**: a plan whose ceiling is a gap.

**4. An Abort from the console in mid-run**, during a run that has the lamp on
and frames coming. The record must show:
- the lights off;
- the two turret shutters closed;
- the sequence stopped within a frame;
- `run_ended` as `stopped_from_outside`.

On mock nothing is a confirmation: **a row reading `true` that mock could not
have confirmed is a defect**, as in card 061.

**5. Throughout**, the console follows every run's `events.jsonl`, and each
run's `log.json` equals its stream between `run_started` and `run_ended`.

## What you record

One file in `microscope_agent/findings/`. It names each run's scratch path and
**the sha256 of its `events.jsonl`**, and records:
- step 1: the live-view run's start, stop and lamp rows;
- step 2: the search's decisions, targets and reads, and the branch it ended
  on;
- step 3: each refusal and its reason;
- step 4: the abort rows and `run_ended`;
- the console's classification of every reply it got.

**No test value appears in the findings as a fact about the instrument**:
each is cited as a TEST value with its `<SCRATCH>` path.

**Stop and report up** if any of these happens:
- any socket binds anything but `127.0.0.1`;
- a refusal moves Z;
- the scratch root works with a non-mock backend;
- a test value is about to be written outside `<SCRATCH>`.

## Boundaries

Part A writes `microscope_agent/src/` and `microscope_agent/tests/`. Part B
writes only under `<SCRATCH>`, plus the one findings file. **Never write this
repository's `envelope/` or `approvals/`.** No change to `SOFTWARE_MAY_COMMAND`
or `NAMED_REFUSALS`. Mock only.

Run the validator to `0 failed` under the interpreter `CLAUDE.md` names, and
read its `tree:` line. Then `git diff HEAD -- <paths>`, then
`git commit -F <file> -- <paths>` under your seat, naming each new file.
Confirm with `git log -1`, and push with
`git -c credential.helper=manager push origin feature/autofocus-ui`. Never
force, never amend.

## What comes back

To this seat, 8 lines at most:
- Part A's commit, and which parts already existed;
- the check-88 result on the plan;
- each step's run id and stream sha256;
- the refusals;
- the abort rows;
- the console's reply classifications;
- any stop.
