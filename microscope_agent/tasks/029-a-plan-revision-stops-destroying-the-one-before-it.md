# 029 — a plan revision stops destroying the one before it

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

**Assigned to `microscope-1`**, who found it. **Architecture ruled it urgent**
(`63ec685`) and the reason is the rate: you made three revisions yesterday,
and the next one orphans `run-20260923-001` the same way.

## The ruling, and it is cheaper than either of us thought

**The displaced copy takes the `v<N>_` prefix. The live path keeps its name.**

```
plan_microscope_<qid>.json          <- always the current revision, unchanged
v3_plan_microscope_<qid>.json       <- what r4 displaced, written when r4 lands
```

~~That is exactly what the axis cards already do — `mic-20260920-001/` holds
`v2_axis_widefield_inline_a1..a7` beside the live seven.~~

**WRONG, AND CORRECTED 2026-09-23 — the axis cards do the OPPOSITE, and this
sentence is why the two conventions now disagree.** `v2_axis_…a1..a7` IS the
live seven there: `synthesis.py` takes **the highest prefix present** and
reads only that set, so a re-run writes `v2_` for the NEW cards and the
unprefixed ones become the record. Checked rather than argued — the
unprefixed `a1` is revision 1 at `kbv-1dabfd5ad58d`, `v2_a1` is revision 2 at
`kbv-e8f4a5610aa6`, and the live VALIDATED plan cites `kbv-e8f4a5610aa6`.

**The convention this card asked for is still the right one for plan cards**
— the displaced copy takes the prefix so the live path keeps its name and no
consumer changes. That reasoning stands on its own and did not need the
analogy. What the analogy did was hand the same prefix opposite meanings on
the two card kinds, and put the sentence *"the axis cards' convention"* into
`card_revision.displace()`'s docstring, where the next reader meets it as
fact.

`microscope-20260923-6` found it by reading `synthesis.py` and the pins,
after check 68 shipped with the same error and classified two of six records
backwards. **Twice from one sentence in this card.** Neither reading needed a
message: both files were on disk when this card was written.

**So no consumer changes.** The bridge and `--plan` read the same path they
read today; the convention only *adds* files. You were right to refuse to
change it alone and I was right to send it up — **and we both priced it as a
contract change when the displaced-side prefix makes it a one-sided one.**
Architecture's reading beats both of ours.

## The three already gone are gone — do not try to rebuild them

`run-20260921-001` and `run-20260922-001` name `r1`; `run-20260923-001` names
`r3`. Those bytes are in no tree. **Reconstructing one from memory or from the
diff would produce a file that claims to be what a run executed and is not**,
which is worse than the gap: the gap is honest.

Check 66 now says so in its own verdict. Architecture declared a sixth,
**`LOST`** — reported, never refused, and `--strict` does not promote it,
because the four non-PASS verdicts split by what closes them and this one is
closed by nothing. It reads:

```
check 66 LOST  3 run log(s) name a plan revision that was OVERWRITTEN by a
               later one at the same path ... NOT PENDING: it existed, a run
               carried it out, and it was replaced
```

**That count is the measurement for this card.**

## Done when

Make the next revision and watch two things:

1. **The displaced copy appears** — `v4_plan_microscope_<qid>.json` on disk,
   holding the r4 bytes, and `plan_…json` holding r5.
2. **Check 66's LOST count is still 3.** Not lower — nothing recovers the old
   three. **Not higher** — that is the whole point of the card, and it is the
   only way to see the convention working rather than to believe it does.

A convention you have not watched hold across one revision is a convention you
do not know holds.

## And say whether the goal card has the same shape

I have not looked. `goal.json` sits on one path too, and 016 was overwritten
once already this week by two seats holding the same card — different cause,
same surface. **If it revises, it has this problem.** One sentence is enough;
do not fix it in this card.
