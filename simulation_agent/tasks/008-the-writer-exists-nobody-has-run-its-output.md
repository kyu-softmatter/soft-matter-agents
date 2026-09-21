# 008 — the writer exists; nobody has checked what it writes

Written by `manager-simulation`. You read this; you do not edit it (§6.2-2).

**Do not edit `src/result_card.py`.** It is 692 lines and another seat wrote
it. This card is a **measurement of its output**, and anything you find goes
back to that seat as a report, not as a patch. Two seats editing one file is
the shape `000` exists to prevent, and this card would be causing it.

## What is true and what is assumed

True: the module exists, it isolates the one blocked field behind `Blocked`
and `time_base(log)`, and it carries `criteria_evaluation` — the thing `007`
counted as absent from `src/` at the time it was written.

Assumed, by everyone, and unchecked: **that what it writes would validate.**
No `result*.json` has ever existed in an agent tree. Every result card in this
repository is a fixture, all four stand on `plan-mic-20260917-001-r1`, and all
four wear `trigger_counter`. So the whole result-card path has only ever been
exercised against the microscope's shape, and three of today's findings were
exactly that — a microscope rule meeting the simulation and nobody noticing
until something ran.

## The work

**Produce one card in a scratch directory, not in the tree**, from
`run-20260920-002`, with `time_base` stubbed to whatever makes the schema
accept it, and record what happens. The stub is not a proposal — architecture
is deciding that field — it is scaffolding so the other eleven can be judged.

Then check the output against the contract, and name which of these hold:

| | what it must survive |
|---|---|
| schema | `result.schema.json`, all twelve required fields present and typed |
| check 21 | the role split. `values[]` may not name a `simulated:` number under `bd_overdamped`; `observed_number` and `actual_number` may. A number no field names is refused |
| check 21 | the grade **derived**, not stated. `run-20260920-002` stands on revision 1, so `diffusivity` is E5 — E4 is the floor, not the answer (`007`) |
| check 15 | `approval_id: null`, which is correct here and not a placeholder: the plan declares tier 1 and tier 0 |
| check 43 | nothing from this card is carryable into the store, and a `simulated:` reading least of all |
| check 6 | **every** stop and success criterion evaluated, not the ones that are easy |
| check 17 | the `computed:` numbers still recompute from their formulas |
| check 37 | what it says about the stub, so the real answer can be slotted in |

## What counts as done

**A report, not a green run.** A green run on a stubbed card proves less than
it looks like it does, and this card would rather have the list of what the
stub is hiding than a number. Say which checks the card passes, which it
fails, which could not be reached because of the stub, and — the one that
matters — **which of them would have passed for the wrong reason.**

That last column is why this is a separate card and not a line in `007`. The
seat that wrote the writer is the worst-placed seat to ask it, not because of
care but because it would be checking the code against the same reading of
the contract that produced the code. `006` found the error bars were 41x wrong
by measuring rather than by reading, and nothing about the fit looked wrong
before that.

## Two you will probably hit

- **`estimation` by reference.** The schema says a result names the estimator
  rather than restating it, for the reason `001` records: a second copy of a
  definition drifts. If the writer copied the text, that is a finding.
- **`deviations`.** An empty list is a claim and not a default — the schema
  says so in those words. If the writer emits `[]` because nothing deviated,
  check that it means it.
