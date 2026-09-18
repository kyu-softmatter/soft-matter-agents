# Examples

Two sets of cards, and the second is the more important one.

## The round trip

A question carried by hand from a human sentence to a measured result, which is
what plan.md section 9 sets as M0's done condition. No agent wrote any of it:

```
goal.json                              purpose screen, intent explore
  ├─ axis_brightfield_a1.json          exposure window from signal and blur
  ├─ axis_brightfield_a2.json          record length from the diffusive time
  ├─ axis_darkfield_a1.json            darkfield needs at least 0.5 s
  └─ axis_darkfield_a2.json            blur caps darkfield at 0.02 s
synthesis.json                         darkfield drops: the sets do not overlap
plan_microscope_mic-20260917-001.json  the plan, and its generated .md
plan_approval.json                     a human clears that revision
result.json                            0.18 um^2/s, one decade resolved
failures.jsonl                         the refusal, a deviation, the success
scope_approval.json                    an operating licence over the same range
```

A second question, `mic-20260917-002`, exists to exercise the comparison path:

```
goal_compare.json                      purpose compare, compare_variable temperature
axis_compare_a1.json                   the exposure window, re-derived
axis_compare_a5.json                   temperature drift tolerance
synthesis_compare.json                 one configuration, exposure fixed across arms
plan_microscope_mic-20260917-002.json  two arms differing only in temperature
```

The exposure is deliberately **not** optimised per arm. Optimising each arm
separately would give each a different systematic error and destroy the
comparison, which is what purpose `compare` exists to prevent (check 34).

Run it:

```
python3 contracts/validate.py
```

Four things in this example are worth looking at, because they are the parts
that were hard to get right rather than the parts that were easy:

**Darkfield is rejected with numbers.** Both of its axes are individually
feasible; the intersection is empty. That is the refusal path of section 4.5.4,
and it is the case a single-axis design cannot express.

**The operating point is computed, not chosen.** `exposure_time_chosen` is the
geometric middle of the allowed decade, with the formula in the card. S4 may not
introduce a number nobody can trace (check 12), and "the model picked 7 ms" is
such a number.

**Every carried number cites where it came from.** `origin` points at the card
that produced it, and check 12 compares value, unit and grade against that card.
Transport is verified by comparison, not by recomputing a formula somewhere with
fewer inputs.

**The librarian is unreachable throughout.** Every card says
`degraded: ["librarian_agent"]`, and both exposure bounds are estimates rather
than literature values, which is why they are E5 and why the plan says so in its
open risks. The system works alone and admits what is missing (D5, section 3.1).

## The store

`librarian_agent/kb/` exists as a plain store from the start — a person curates
it, agents read the files, and there is no librarian agent until M3
(`plan.md` §4.3.0). That is already enough to make grade inheritance checkable:
`axis_brightfield_a2.json` cites `kb:water_viscosity_293k` as E3, and the
validator compares that against what the store actually says. Editing an entry
without rebuilding `kb/index.json` fails check 25.

## The bridge thread

One round, and it is held rather than completed — which is the honest state of
this repository rather than a placeholder:

```
r1_ask_simulation.json   the microscope's result card, wrapped and carried
r1_ask_simulation.md     the same round for a person, with no number in it
r1_hashes.json           the source card's id, revision and hash
status.json              whose turn it is, and what is blocking
```

`contracts/observables.json` defines `tracer_diffusivity` and
`capabilities/simulation.json` declares `bd_overdamped` as producing it, so the
derived verdict is **yes** and `status.json` puts the turn on the engine side.

Until 2026-09-17 both tables were empty and the verdict was **undeclared**, so
this round was held with the turn on a person — and undeclared is not
impossible. Refusing would have recorded an impossibility nobody established;
answering yes would have claimed a capability nobody declared. What is worth
looking at is how it moved: two other files changed, and the verdict stored in
this envelope then failed check 8 until it was brought into line. The envelope
records what the gate said, and the gate is recomputed from the tables rather
than trusted.

Three things here are worth looking at:

**The verdict is derived, not declared.** The validator recomputes
`answerability.producible` from the vocabulary and the receiving side's
capabilities table, and rejects a card claiming more than the two of them say. It
is the move check 21 makes on grades: give the bridge a boolean it can fill in
itself and the gate becomes a formality.

**The envelope's own hash proves only that it agrees with itself.** A bridge that
changed a number could change the hash with it, so `r1_hashes.json` records the
source card as it stood in the sender's directory, with its revision. If that
card later moves to a new revision the round is no longer comparable, and check 8
says so by counting zero rounds verified rather than passing quietly.

**The markdown restates none of the payload's numbers.** The envelope's
`numbers[]` is empty because the bridge authors no numbers, and check 9 requires
every number in a markdown file to appear in its card. The constraint arrived by
itself and it is the right one: a courier that recites the values puts one
quantity in two places (P3).

## The cards that must fail

`rejected/` holds one card per defect that a single card can carry, and the
table says which check each one breaks. The totals come from the run rather
than from this sentence: three hand-counted numbers in this repository were
wrong on 2026-09-17.

| card | check | what it does |
|---|---|---|
| `bad_self_reported_grade.json` | 21 | claims E1 for a specification value |
| `bad_e6_value.json` | 3 | puts a made-up value in a card |
| `bad_false_precision.json` | 28 | writes an estimate to three significant figures |
| `bad_missing_assumption.json` | 4 | an assumed number with no rationale |
| `bad_unknown_unit.json` | 2 | a unit outside the registry |
| `bad_md_number.json` | 9 | markdown that drifted from its JSON |
| `bad_sibling_a.json`, `bad_sibling_b.json` | 11 | two axes reading each other |
| `bad_kb_grade.json` | 21, 25 | promotes a stored E3 to E1 on the way in |
| `bad_unjustified_estimate.json` | 39 | estimates with the librarian reachable and no gap to stand on |
| `bad_bridge_authored.json` | 8 | the bridge adds an assumption of its own |
| `bad_bridge_direction.json` | 8 | an envelope for the engine carrying a card the engine wrote |
| `bad_bridge_hash.json` | 8 | the payload and its hash disagree |
| `bad_bridge_claimed_capability.json` | 8 | claims an observable the tables have not declared |
| `bad_bridge_not_producible.json` | 8 | a refused gate delivered as an envelope instead of a refusal |
| `bad_bridge_unit_skip.json` | 8 | round two with the unit comparison skipped |
| `bad_bridge_escalation.json` | 8 | a pair that came back twice, with the thread still open |
| `bad_bridge_wrong_configs.json` | 8 | the right verdict, naming configurations the table does not list |
| `bad_bridge_unknown_observable.json` | 8 | asks for an observable the vocabulary does not define |
| `r2_ask_simulation.json` | 13 | a filename naming a round the card does not claim |

The last of those is a thread ledger rather than a card (`artifact:
thread_status`), and `--expect-fail` counts it the same way: a ledger nobody
checks is a ledger that quietly stops saying whose turn it is.

`bad_bridge_authored.json` authors an *assumption* rather than a number, and
that is deliberate. The schema caps the envelope's `numbers` at zero and check 8
reads the same field, so a fixture carrying a number fails twice and check 8's
rule is never the reason it failed — the rule could break and the card would go
on failing. `assumptions` has no cap in the schema, so authoring one leaves
exactly one check to fail. The two layers both stay: the schema states the shape
and the check states the reason.

The one fixture not named `bad_…` is `r2_ask_simulation.json`, and it cannot
be: the rule it breaks is read off the filename (7.1 rule 3), so the filename is
the defect. It says round two and the card says round one.

## Fixtures that need two files

Some defects cannot be put in one file. A ledger that disagrees with its
envelope leaves the envelope correct; two refusals repeating one
`(reason_code, parameter)` that the thread ledger does not record leave both
refusals correct. Requiring every file to fail on its own excluded exactly those
cases, and check 8's ledger rules went untested because of it — testability was
deciding the shape of the contract, which is the wrong way round (plan.md 11-7).

So a folder one level down is one fixture:

```
check08_ledger_payload_mismatch/   envelope + ledger + status, and only the ledger is wrong
check08_unrecorded_repeat/         two well-formed refusals + a ledger that omits the repeat
                                   (r1_refusal.json, r3_refusal.json: the round leads, 7.1 rule 3)
```

**The folder names the check it is a fixture for, and the count requires a FAIL
from that check.** Without that condition a group would stay green on any
unrelated failure long after the defect it claims to hold had gone. A flat file
is nailed to its own line in the table above; widening the unit pulls that nail
out, and the folder name puts it back. A group naming a check that did not fail
is reported with what did:

```
NOT REJECTED  …/check99_ledger_payload_mismatch is a fixture for check 99 and check 99 did not fail (only [8])
```

A normal sweep steps over this folder. To run the gate on it:

```
python3 contracts/validate.py --expect-fail contracts/examples/rejected
```

The exit code inverts: every card must fail, and **a card that stops failing
breaks the run.** A check nobody tests is a check that quietly stopped working,
and the way it stops working is that someone loosens it to make a real card pass.
