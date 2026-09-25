# 034 — the 20x question, which stands on today's preparatory run

Written by `manager-microscope-20260924-1`. You read this; you do not edit it
(§6.2-2).

**Assigned to `microscope-20260924-2`.** The person chose this work for that
session on 2026-09-24, in this seat's session. **Do not commit until your row
is in `contracts/seats.json`.** Check 41 reads the registry at a commit's
parent, so a commit made before the row exists stays unattributed for good.
The row has been asked of architecture. Read your email from the file, never
from a message.

**`microscope-20260924-1` holds card 033 and is at the instrument.** Nothing
here touches its files. **Do not edit `src/devices/micromanager.py`,
`src/session_033.py`, `src/orchestrator.py` or `src/operator.py`**, and do not
touch `runs/` or anything under `D:\soft-matter-agents-frames\`. If this card
seems to need any of them, stop and report up.

## What this question is, and what it is not

**Today's run is a preparatory run** (`plan.md`, settled 2026-09-24 at
`32e2263`). It has no plan, and it produces no result card and no KB entry
of its own. **Its numbers reach the record only when a later plan cites its
`run_id` as an input.**

**This question is that later plan.** It targets `tracer_brightness`, with
`bleaching_rate` beside it, for the Abvigen particles through the **20x dry
objective**, with the **Aura III's green line** and the **red camera**, and
the optics set by the person's hand. S5's plan is the **formal** measurement,
the one whose result card goes to the librarian. **Today's run is the input
that bounds its exposure and intensity**, which is what card 016 found the
100x question could not do without a run.

**It is not a way to file today's frames as a result.** Its plan governs a
run that has not happened yet. A plan written so that its "run" is today's
run would be the record saying a plan preceded a run it did not, and
`32e2263` rejected exactly that.

**Why not revise `mic-20260920-001`**: that question is the 100x oil lens
with software motion, and its axis ranges were computed for that
configuration. Citing them for 20x would be laundering. This is a new
question, `mic-20260924-001`.

## The order, and where it waits

1. **S2, the goal card** — now. `observable.name` is `tracer_brightness`,
   which is registered. `purpose: characterize`, as in `mic-20260920-001`.
   The sample is the Abvigen 5 µm particles, cited from the store, not from
   memory. **The objective, the intermediate magnification and the light
   path are the person's declarations**, carried as such and not as
   evidence. The constraint that matters: **no software motion in the
   plan**, because the retract and clearance interlocks still block the
   first software-driven motion (card 023). The configuration preference is
   `widefield_inline` only if S3.0 agrees; see 3
2. **S3.0, screening** — now
3. **The excitation is where the vocabulary runs out, and that is a
   finding, not a problem to paper over.** The registry names
   `widefield_source_a`, whose branch is unconfirmed (card 018 §5), and
   carries **no Micro-Manager labels at all**. That is one of the two gaps
   `033` §3b named. **Do not map `Aura` to `widefield_source_a` yourself.**
   That mapping is the disputed one, and today's run may settle it. State
   the excitation as the person's declaration, name the gap in `kb_gaps` or
   the axis abstention it causes, and report it up. The mapping is a card
   after today
4. **S3, all seven axes, for this configuration**, with the librarian on:
   `kb_refs` and `kb_gaps` filled and `degraded` empty. Pixel size is
   `pixel_size_20x_zoom_1x`, E2, at 1×1 binning, **from the store and never
   from frame metadata**: today's frames carry a figure from the loaded
   configuration, and it is not a source. **A1 and A3 will abstain** on
   `tracer_brightness` and `bleaching_rate`, and that is correct. Name the
   remedy in the abstention: *today's preparatory run, once its log is in
   `runs/`*
5. **S4 and S5 wait on two things, neither yours:** today's run finishing,
   and this seat landing the run-log schema field and the check for
   preparatory runs, so that today's log can enter `runs/` with a `run_id`
   a plan may cite. **Until both have landed, do not write a plan that cites
   a run_id.** A plan citing a log that is not in the tree cites nothing
   anyone can check

## What to bring back

- the goal card and the screening, committed once your row exists
- all seven axis cards, with every abstention naming its remedy
- **every place the registry or the vocabulary could not say what the
  person declared**: the excitation certainly, and anything else you find.
  Each one is a card after today, and a list is what makes them cards
- your rulings on anything taken from `C:\agentic_microscope`, in
  architecture's terms (`32e2263`): **transfer**, **downgrade** or
  **discard**, with no fourth word. Report them up and this seat writes
  `tasks/034-rulings.md`

## Before committing

`PYTHONUTF8=1 python contracts/validate.py`, and read the tree line. The
working copy has another seat's uncommitted work in it, so a failure there
may not be yours. Use `git commit -- <paths>` after `git diff HEAD --
<paths>`, and name new files individually. **Hooks are not installed in this
working copy**, so no gate runs; say so in the message.

**Re-read this card immediately before committing.**
