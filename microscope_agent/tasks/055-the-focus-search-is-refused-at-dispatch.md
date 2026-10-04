# 055 — the focus search is refused at dispatch

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to a microscope seat that architecture names.** If no one named
you, take nothing from this card and report up. It re-issues card 026's
walking approach (step 6) as plan.md 11-24 shapes it. 026's other
preconditions still stand: the retract interlock and the clearance
comparison it names.

## What exists and what does not, read at d293fc9

- A plan can carry `focus_search` (`contracts/schemas/plan.schema.json`), and
  check 88 refuses at commit time a search outside the person's
  `focus_z_<objective>_min/_max`. **Commit time is not dispatch time.** The
  operator does not know the block yet, so nothing at run time refuses
  anything about it.
- `ZDrive` is in `NAMED_REFUSALS` and off `SOFTWARE_MAY_COMMAND`, so every Z
  command is refused today. **Keep both exactly as they are.** This card opens
  Z through an exemption for an approved plan, the way card 040 opened the
  piezo (`operation_exemptions` + `_operation_gate`) and card 049 opened the
  tweezers. It never lifts a refusal.
- `orchestrator.py:259` says it plainly: *nothing compares a Z target against
  `objective_clearance_min` at the moment of the move yet.* **For the focus
  search, the person settled what replaces it** (2026-10-04, recorded at
  `250a138` in plan.md 11-24): `focus_z_<objective>_max` is the closest that
  lens may ever come to the coverslip. It is an absolute encoder value the
  person writes per lens, and nothing derives it from a measured coverslip
  position plus a working distance.
- **`PFS` is in `NAMED_REFUSALS` too**, so software cannot switch it off.
  "PFS off before any Z command" here means **read it, and refuse while it is
  engaged**. The person switches it off. Do not ask for PFS on the allow-list.
- No `focus_z_*` key exists in `envelope/safety.json`. Until the person writes
  them, every search must refuse. That is correct, and your tests have to show
  it.

## What to build

**1. A focus-search exemption, in the shape of the two that exist.** A command
is exempt only if all of these hold: the plan carries `focus_search` on
`stand_ti2e` / `z_drive`; the plan's revision carries the person's approval,
via `operator.authorise`; the command's `from` names a `focus_search` field;
and the command equals what the plan derives. Nothing the command says about
itself counts. Every other Z command meets the allow-list and is refused, as
today.

**2. The derivation is per move, so the gate re-derives every move.** A focus
search does not list its moves in advance. Each one comes from the branch the
decider picked and the last encoder read:

- `step_up` → last read + `step_um`
- `step_down` → last read − `step_um`
- `in_focus`, `no_sample_here`, `unsure` → no move

Send each move as an **absolute** target. The gate recomputes the target from
the plan, the last read and the branch, and refuses any command that differs.
The decider supplies a branch and never a number; a branch outside the plan's
`branches` refuses.

**3. Before the first Z command, refuse unless all of these hold:**

- the hand-over states an objective, and it **equals** `focus_search.objective`.
  A difference refuses, and no default fills in a missing one;
- `focus_z_<objective>_min` and `_max` both exist, form a range, and contain
  `range_um`. **A missing key refuses for every lens.** A dry lens the person
  has released carries wide values and is never absent (plan.md 4.6.8 and the
  schema both say so);
- PFS **reads** as not engaged;
- the plan has a stop criterion on position read-back error. Without one,
  "read back within tolerance" means nothing, so refuse;
- the search starts with the existing retract, which is read back, as
  `approach_from: retract` says. It never starts from wherever Z was left.

**4. At every step, before the move goes out:**

- the target lies inside `range_um` **and** inside the person's limits;
- **the clearance comparison, live: the next target against
  `focus_z_<objective>_max`, and nothing else.** A target above it refuses
  before the move goes out. That key is the person's written closest approach
  (`250a138`). Do not compute a clearance from a coverslip position, a working
  distance or `objective_clearance_min`, and do not combine it with one: that
  computation would itself become a safety number nobody wrote. **A missing
  key refuses.** Read the key again at every step rather than caching it from
  preflight, and record the comparison each time (`target`, `limit`,
  `compared: true/false`);
- the move count is under `max_moves`. Reaching the ceiling ends the search
  as **not found**, never as found.

**5. After every step, before the next one:** read the encoder. The next
target is derived from that read, never from the previous target. A read-back
outside the plan's tolerance stops the search, as card 040's moves do. The Z
found at `in_focus` is that read.

**6. Record**, as events: each decision, with its branch and the decider's
confidence; each derived command, with its `from`; each read-back; and each
refusal with its reason. `unsure` is recorded as an abstention and is never
counted as a miss.

## Tests, mock first, each watched failing before the code exists

1. With no `focus_z_*` keys, a search refuses before any Z command, with the
   missing key named.
2. A hand-over objective that differs from the plan's refuses; so does a
   missing one.
3. PFS reading engaged refuses; the fake records no Z write.
4. A plan with no approval for its revision gets no exemption, and the
   allow-list refuses ZDrive.
5. A command that is not the derivation, or carries a number the decider
   supplied, is refused; so is a branch not in `branches`.
6. A target outside `range_um` or outside the limits refuses at that step.
7. A step whose target is one `step_um` above `focus_z_<objective>_max` is
   refused before it goes out, with the comparison recorded and no Z write. A
   target exactly at the limit is allowed. With the `_max` key removed after
   preflight, the next step refuses.
8. `max_moves` reached ends as not found.
9. A read-back out of tolerance stops the search before the next move.
10. `named_refusals_hold()` is still empty, and `ZDrive` and `PFS` are still in
    `NAMED_REFUSALS`.

## The gate before the first real Z command

**Separate from the build, and the person must be present.** On the instrument,
with the person watching, run the refusals: no limits, the wrong objective,
PFS engaged, no approval, and a target above `focus_z_<objective>_max`. Each must be
seen to refuse with no Z motion. Only after that, and only with the person's
word, does a search send a real Z command. Card 033 asked for refusals on
mock; this asks for them on the instrument.

## Questions only the person can answer

Put these to the person in plain words. Do not answer them here:

- **Limits:** what Z range, in encoder micrometres, may the focus search use
  for each lens, including the wide range for each dry lens you have released?
  The top of each range is the closest that lens may ever come to the
  coverslip.
- **Watching:** when can you be at the microscope to watch the refusals before
  the first real focus move?

## Boundaries

Write in `microscope_agent/src/` and `microscope_agent/tests/` only. Never
write or reword `envelope/` or `approvals/`. No change to
`SOFTWARE_MAY_COMMAND` or `NAMED_REFUSALS`. **Open no device** until the gate
above.

Run the validator to `0 failed` under the interpreter `CLAUDE.md` names for
this computer, and read its `tree:` line. Then `git diff HEAD -- <paths>`,
then `git commit -F <file> -- <paths>` under your seat, naming each new file.
Confirm with `git log -1`, and push with
`git -c credential.helper=manager push origin feature/autofocus-ui`. Never
force, never amend.

## What comes back

To this seat, 8 lines at most: the commit, the ten tests' failing and then
passing output, the validator's `verdict:` and `tree:` lines, and the
person's answers if they came to you rather than to architecture.
