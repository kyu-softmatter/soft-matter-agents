# 001 — drop `observable.definition` from the cards and from `plan_card.py`

Written by `manager-simulation`. You read this; you do not edit it (§6.2-2).

**Startable now.** Needs no librarian. Read `000` first for who may commit it.

## What changed upstream

`47ee3b2` (bridge seat) loosened `goal`, `plan` and `result`: `observable` is
now `required: ["name"]` and `definition` is still allowed. Nothing broke —
that was the point of doing it in this order rather than as a synchronised
handoff across three seats in a shared working copy.

`4a754c2` (session 1) already removed the divergence a different way: the
definition is now copied mechanically from `contracts/observables.json` by
`cards.observable(name)`, so the cards match the vocabulary literally.

So what is left is a deletion, not an edit.

## The change

- `cards.observable(name)` stops emitting `definition`. It returns the name.
- `simulation_agent/questions/sim-20260917-001/*.json` — drop the key wherever
  it appears (`goal.json`, `plan_simulation_sim-20260917-001.json`, and any
  other card carrying an `observable`).
- The generated `.md` keeps reading the vocabulary. It is the only place a
  person can see which definition and which estimator a plan meant, and that
  stays true after the key is gone (P3: JSON authoritative, Markdown
  generated).

Keep the `.md` rendering of `estimator`. It is not decoration: the estimator
cannot ride in a card at all today, `comparable` is gated on both sides having
run the same one, and until a contract can carry it the rendered text is the
only record of which one this plan meant.

## Why, in one line you can check

A transport that restates a value holds a second copy of the same quantity,
and the second copy drifts. Eight cards had already drifted from the
vocabulary by 2026-09-18.

## The instructive part, worth keeping

Session 1 diagnosed why its own definition differed, and it was not
carelessness. What the card said was:

> read from the slope of the mean squared displacement against lag time over
> lags strictly below the diffusive time, with the intercept left free

What the vocabulary says is what the quantity **is** — a proportionality
between mean squared displacement and lag time in the free regime — and it
keeps *how the number is obtained* in a separate field, `estimator`.

**The card had written an estimator into a definition field.** That is the
category error the two-field split exists to prevent, and a schema that forces
you to restate a definition you cannot carry properly is how a careful author
arrives at it. Fixing the schema fixes the cause; this task removes the last
of the effect.
