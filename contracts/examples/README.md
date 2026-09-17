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
```

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

## The cards that must fail

`rejected/` holds eight cards, each breaking one check on purpose:

| card | check | what it does |
|---|---|---|
| `bad_self_reported_grade.json` | 21 | claims E1 for a specification value |
| `bad_e6_value.json` | 3 | puts a made-up value in a card |
| `bad_false_precision.json` | 28 | writes an estimate to three significant figures |
| `bad_missing_assumption.json` | 4 | an assumed number with no rationale |
| `bad_unknown_unit.json` | 2 | a unit outside the registry |
| `bad_md_number.json` | 9 | markdown that drifted from its JSON |
| `bad_sibling_a.json`, `bad_sibling_b.json` | 11 | two axes reading each other |

A normal sweep steps over this folder. To run the gate on it:

```
python3 contracts/validate.py --expect-fail contracts/examples/rejected
```

The exit code inverts: every card must fail, and **a card that stops failing
breaks the run.** A check nobody tests is a check that quietly stopped working,
and the way it stops working is that someone loosens it to make a real card pass.
