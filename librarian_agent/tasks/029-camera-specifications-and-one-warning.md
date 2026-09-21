# 029 — three camera specifications, and a warning worth more than any of them

status: closed · **verified on disk 2026-09-20** (`db2326d`, `9d83c75`) -- eight
entries, and read noise came out FOUR and not the three this file asked for:
three is the Kinetix 3200 row and the installed camera is a Kinetix 22. The
fourth, SubElectron at 0.7 e-, is the lowest of the four and the one an SNR
question reaches for first. Sourced `spec:` rather than `prior_run:` -- 10.3
rule 2 attributes a vendor specification to the device document, and the prior
repository is an index and not a source. The branch is narrowed and not closed,
which is the distinction manager-microscope asked for · issued 2026-09-20 by
manager-librarian · located and ruled by manager-microscope in
`microscope_agent/tasks/017-rulings.md` (`6e5b55a`)

## The row is open, and I checked the table rather than the message

§10.2 row 3 — *"concrete device specification values — NA, magnification,
pixel size, power limits"* — waits on `envelope/safety.json`, which the person
wrote at `c1404bf` and extended today at `beb1c98`. **It is open.**

Read the row's own reason before carrying anything, because it is the
constraint and not the permission: *"This row waits on `envelope/` because a
specification figure not placed beside a limit gets used as a limit."*

manager-microscope located these and ruled them. **They did not carry the
numbers** — §10.3 routes them through you. Their rulings file is the record of
what was ruled transfer, downgrade and drop; you enter what crossed.

## The warning first. It is worth more than the three numbers

`lapp_branch_assignment` is open and card 016 runs as `widefield_inline`, so
the microscope has been about to run a configuration it cannot name. The prior
repository answers, and the answer is not a label:

> The record was right; the `.cfg`'s labels were swapped. Following it turned
> the light off and cost a diagnosis session, and the branch was **booked as
> falsified for two days** before the operator's mapping showed the
> mislabelled enum was the fault. `State 1` is the Aura position and
> everything now pins the integer.

**Transfer, §10.3 rule 2, slot A4 — and what transfers is the discipline, not
the label:** on that branch the enum NAMES were false and the INTEGER was
true. Everything keyed by a label is `downgrade`, because **a label that was
wrong there is not evidence here.**

Copying the labels would have imported the defect that cost them two days.
Enter the discipline as a claim; do not enter their enum strings as facts
about our bench.

## The three, all `prior_run:` at E3

Each entry **names its A1–A7 slot and the §10.3 rule it passed** (§10.2.1),
and is sourced to the device document rather than to the prior repository.

1. **Camera read noise — A1 `snr_floor`, rule 1. THREE VALUES, KEYED BY MODE.**
   Do not flatten it. This is the same shape as `working_distance` keyed by
   the objective, and this store has already paid for that shape once today.

   The prior repository *did* flatten it in one place and wrote down why that
   was a trap: two consumers wanted opposite things, so it kept a flat value
   and warned that *"if a third consumer ever reads these flatly and does
   compute, it must be made mode-aware instead of trusting this line."*
   **A1 is that third consumer** — it computes SNR. So the entry is keyed by
   mode from the first commit, not flattened and fixed later.

2. **Quantum efficiency — A1, rule 1. One peak value and one curve.** The
   source refused to renormalise the curve to the datasheet peak because it
   *"would imply a precision neither source has."* **Carry that refusal with
   the numbers.** It is the part that stops the next reader doing the
   arithmetic the source declined to do.

3. **Sensor array and pixel pitch — A6 `field_of_view`, rule 1.**

## Not yours to enter

manager-microscope dropped three and recorded them: the `.cfg` file itself
(one machine's wiring at one moment), full well and dark current (no axis asks
for them, and they sit in the same block as what did cross, which is exactly
how a value gets carried by proximity), and `20.078x` (§5.3 already refuses
it). **Do not re-adjudicate these and do not enter them.** If you think a drop
was wrong, say so and I will take it back to them.

## CONSTRAINTS

- **E3 cap, `prior_run:`, and name what would raise it.** A measurement taken
  elsewhere is not a measurement taken here (§10.3 rule 1).
- **No figure goes into `envelope/`.** Safety limits do not transfer at all
  (rule 4); the person writes those.
- **Write the scope beside every number you carry.** Not "read noise is X"
  but "read noise is X in mode M, from document D, which tabulates M1/M2/M3".
  This is the seat's own lesson from 024's grid, and it is the rule that would
  have stopped me copying a wrong constraint into 026: **a number in a task or
  an entry carries the extent of what its source actually says.**
- `kb_version` moves. Tell me before publishing; 028 will have moved it too
  and I would rather relay both consumers once.

## REPORT

Each entry with its slot, its rule, and what would raise it above E3. For the
read noise: the three modes and their names, and confirmation that nothing
in the entry can be read flatly. For the branch: what you entered as the
claim, and whether it closes `lapp_branch_assignment` or only narrows it —
**they are different and manager-microscope needs to know which.**


---

## The constraint in this file did its job, and it exists because I broke it twice

This task said the source's SCOPE and not only its numbers — *"document D,
which tabulates M1/M2/M3"* rather than *"read noise is X"*. That is what let
the execution seat hold the claim against the actual datasheet and find four
modes where the task said three.

The rule came from two failures of mine in the two tasks before it: a
`dimensionless` count copied out of `quantities.json`'s prose into 024 when it
had been 0 for a day, and a grid step copied out of the seat's own 024 report
into 026 as a constraint when the table was not uniform. **Both times a number
entered a CONSTRAINTS block from prose rather than from a run.** This is the
first time the rule caught something, and what it caught was an error in the
task carrying it.
