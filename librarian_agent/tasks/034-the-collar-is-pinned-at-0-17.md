# 034 — the 40× collar is pinned at 0.17 mm, and the store already said so

status: open · issued 2026-09-22 by manager-librarian · **relayed fact from
the person, via microscope-5** · **small, and it closes nothing**

## The fact

The 40× WI (MRD77400) correction collar is **set to 0.17 mm and will be left
there.** The person said so on 2026-09-22.

**It reached me through microscope-5, who flagged that it was a relay.** That
is the right handling and it leaves one thing open: **if the grade turns on
how the person knows it — read off the collar just now, or recalled from
when they set it — ask them directly.** A relayed fact is a fact; a relayed
grade is not.

## The store already inferred this, which is most of the answer

`objective_mrd77400`'s own `validity_conditions` says it:

> The working distance is collar-dependent, and **the collar setting is
> determined once the coverglass thickness is fixed** — so at the 170
> micrometres this laboratory uses (`coverslip_thickness_in_use`) the working
> distance is a single value rather than a range.

A collar scale is marked in coverglass thickness, so **0.17 mm collar is
170 µm coverslip** — the number `coverslip_thickness_in_use` already holds.
**The person has not supplied a new value. They have confirmed an inference
and pinned it.**

So the work is small: record that the condition the entry was waiting on is
**met and held fixed**, and join it to `coverslip_thickness_in_use`. Do not
write it as a discovery.

## `operator_set:` does not exist, and that is deliberate

microscope-5 proposed it. It is not in the pattern, and
`common.schema.json` records why it was removed:

> An `operator_set` prefix was added for one and reverted: **SOURCE_GRADE is
> a function from source to grade** and P2 derives one from the other, so a
> decision either yields a grade it should not have or leaves a hole in the
> invariant.

The prefix you use depends on how the person knows it, which is the question
above. **Do not mint one.** And note the neighbouring rule before you decide:
a number the operator CHOSE — a target, a budget — carries neither source nor
grade at all. **A collar position is arguably chosen**, and arguably a state
of the instrument that anyone can walk over and read. That is the judgement,
and it is yours with the person.

## IT DOES NOT CLOSE THE GAP, and microscope-5 said so before I could

The catalogue's 0.16–0.20 mm spans **the whole collar range**, not the value
at 0.17. So the gap changes kind and does not close:

```
was   condition_mismatch   the collar setting was not fixed
now   the condition is met and THE VALUE IS STILL ABSENT
```

**The second is better and still open.** Do not let the pin read as an
answer, and do not interpolate inside the quotation — the rule that refused
0.18 before refuses it now.

## Two uses of the missing number, and only one of them is unblocked

**The safety floor does not need it.** The person ruled `fallback:
["working_distance_min"]`, and 0.16 is still the near end of 0.16–0.20 at any
collar setting, so **that ruling stands unchanged by this pin.**

**Autofocus does need it.** microscope-5's point: choosing an end is wrong by
up to 40 µm in either direction, and at 40× water 40 µm is fully out of
focus. Those are two different demands on one absent number and the report
should not merge them.

## The limit to write into the entry

**The collar is a manual selector with no read-back.** §2.1 does not count it
as a verified state, so *"we do not change it often"* is not a guarantee —
and a value nobody changes often is one whose change date nobody records.
**Write that limit into the entry**, so a consumer can hang a visual check on
it rather than assume.

## How it closes properly

Focus the 40× on the coverslip interface and read the encoder: that is the
working distance at collar 0.17, **measured here**, which clears §10.3's E3
cap on the catalogue figure. microscope-5 reports the 018 bench visit already
carries interface offsets for all six lenses, so **this adds no visit** — it
is a by-product of one already planned.

## REPORT

The entry or entries, the prefix and why, and whether the person had to be
asked. Confirm the gap is still open and say which kind it now is. And say
whether anything else in the store was waiting on the same condition — the
`validity_conditions` sentence above suggests this entry was not the only one
holding its breath.
