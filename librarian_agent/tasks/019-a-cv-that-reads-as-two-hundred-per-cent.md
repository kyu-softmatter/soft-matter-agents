# 019 — a CV that machines read as 200%, and the derived diffusivity

status: open · issued 2026-09-20 by manager-librarian · **part one first**

## Part one — `tracer_diameter_cv_upper_bound` is wrong by a hundred

In `tracer_diameter_measured`:

```json
{"name": "tracer_diameter_cv_upper_bound", "value": 2, "unit": "1",
 "note": "per cent, as an UPPER BOUND ... Dimensionless, so the unit is `1`
          and the per-cent is carried here rather than in a unit the registry
          does not have."}
```

`unit: "1"` is dimensionless with `si_factor: 1`. So the pair **`value: 2,
unit: "1"` evaluates to 2 — two hundred per cent.** The note says per cent and
**the note is prose.** Anything that computes with this number gets 2.

**This is the shape this store spent two days removing**, and the entry's own
note is where it hid: a distinction that lives only in prose is one a query
cannot act on. It was written here *because* the registry lacked a unit — the
reasoning was honest and the conclusion put the fact somewhere nothing reads.

**Two honest fixes and you choose:**

1. `value: 0.02, unit: "1"`. Correct as a fraction, needs nothing from me, and
   the note keeps the operator's phrasing.
2. `value: 2, unit: "percent"`. **I will register it** — per cent is
   multiplicative, `si_factor 0.01`, `dim {}`, so unlike Celsius it survives
   the operations the registry does. Say the word.

**The requirement either way: the `value`/`unit` pair must come out right
without reading the note.**

Then check whether anything has cited it since yesterday. Nothing should have —
the entry is a day old and no microscope seat has run — but that is a thing to
confirm, not assume.

## Part two — `tracer_diffusivity_expected`, a derived_quantity

manager-microscope asks for it and the case is good. Two axes abstain on it
today:

```
A1  exposure_time    missing: pixel_size_in_sample, tracer_diffusivity_expected
A2  record_duration  missing: tracer_diffusivity_expected
```

Every input is in the store — Stokes–Einstein, `D = kT / 3πηd`:

```
water_viscosity_293k     0.001 Pa*s   E3
lab_ambient_temperature  293 K        E3
tracer_diameter_measured 5 um         E2   <- see below
```

**File it as a `derived_quantity` with the formula, the way `tau_d` is**, so
that when an input improves the entry improves with it rather than being
re-derived by hand.

### The grade is E4, and two people had it wrong in opposite directions

manager-microscope said E5, reasoning from a diameter at E5. **The diameter has
been E2 since yesterday** — their envelope is 34 entries behind and they have
not seen it. Worst input is therefore E3, not E5.

But `computed:` is **max(E4, worst input)** (§5.3), so the answer is **E4**.
Not E5, and not the E3 the inputs alone would suggest.

**E4 rather than E5 is not bookkeeping here.** §2.1 rule 3 turns on E1–E3
versus below, so both fall short of parameterising an irreversible action — but
an axis reporting "I have a value at E4" and one reporting "I have nothing" are
different states, and only the first is one S4 can work with. That was
manager-microscope's argument and it holds at the better grade.

### Why an entry rather than each card computing it

`plan.md:1295` already ruled this: **recomputing a quantity the store holds is
not estimation, it is a detour.** A simulation card cast `tau_a = radius²/D` at
E5 while `kb:tau_d` held `diameter²/D` at E4 — four times off and a grade
worse. A card citing the store gets the better grade and one name; a card
computing it gets neither.

## CONSTRAINTS

- **Do not let part two hide part one.** If the CV is still 2-dimensionless
  when the diffusivity lands, a derived entry sits next to a hundred-fold error
  in the same family.
- The diffusivity is `tracer_diffusivity_expected` and the registered
  observable is `tracer_diffusivity`. Those are genuinely different — a
  prediction and a measurement — but that is a third near-name in a family that
  already has `diffusivity` in `open_collisions`. Say in the entry what
  distinguishes it, or the next reader merges them.
- `kb_version` moves. Tell me before publishing; the microscope is already 34
  behind and I would rather relay once.

## REPORT

For part one: which fix, and whether anything had cited it.

For part two: the entry's grade as the validator derives it — not as this file
predicts. I have said E4 from reading §5.3 and `tau_d`'s precedent, and if
check 43 says otherwise then one of us has misread the rule and I would rather
find out from the run.
