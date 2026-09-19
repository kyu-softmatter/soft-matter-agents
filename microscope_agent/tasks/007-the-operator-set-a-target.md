# 007 — the operator set a target, and a standing preference

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

**This card is `microscope-1`'s**, because it revises the goal card and re-runs
A2, both of which are that seat's.

## The number

**`target_relative_error = 0.5` on `tracer_diffusivity`.** The person set it on
2026-09-19, asked directly, because A2 said only the operator could.

Write it into `goal.json` as a new revision — `numbers[]` gains

```json
{"name": "target_relative_error", "value": 0.5, "unit": "1",
 "source": "operator_set:kyuhwan_20260919", "grade": "E5",
 "precision": "order_of_magnitude"}
```

and `targets[]` gains `{"metric": "tracer_diffusivity", "number":
"target_relative_error", "kind": "uncertainty"}`.

**Use `operator_set:`, which did not exist until `b47dc3d`.** Not `assumed:` —
that says nobody chose it when a person did. Not `operator_recall:` — nothing
was recalled. The three operator prefixes are not interchangeable and only
`read` and `recall` are claims about the world at all. Its E5 is there to
match the two targets already on the card and the schema says outright that
the grade is the wrong axis for a decision; do not read it as low confidence.

`target_decade_resolution` and `snr_target` are the same kind of thing and are
still written `assumed:`. **Move them to `operator_set:` in this same
revision** if you can attribute them; leave them if you cannot, and say which.

## What it unblocks, and what it does not

Half of A2. `frame_count` was missing `target_relative_error` **and**
`localisation_error`, and only the first arrives here — no localisation error
has been measured on this instrument and it cannot be derived without the
pixel size and the SNR actually achieved. So re-run A2 and expect
`frame_count` to stay `no_input` with a **shorter** `missing` list. That is
progress and it must show as progress: one input arriving is not an interval.

`repeat_count` is blocked twice and the second block does not move at all —
the goal says the sample is consumed and cannot be remounted, so repeats are
capped at one whatever the target is. Say so rather than letting the target
look like it helped.

At 50%, roughly four independent displacements carry the estimate. If that
turns out to make A3's dose and A5's duration non-binding, say that too — a
target chosen to be cheap should visibly be cheap.

## The standing preference

The person also stated, the same day: **where relative motion is needed,
prefer moving the piezo stage over steering the trap**, so the object stays
fixed on the sensor for image analysis. It is in
`microscope_agent/CLAUDE.md` now; read it there rather than from this card.

It does not belong in this goal card. It is standing and not per-question, and
`configuration_preference` is for choosing a configuration, not an actuator
inside one.

Two things it does **not** do, both easy to get backwards and both worth a
sentence in A7 when A7 is next written:

- The escape condition `v_max ~ k·x_max/γ` still binds. It is about relative
  velocity, so driving it from the stage produces the same drag.
- What changes is which limits enter: piezo travel, bandwidth and settling
  rather than trap steering rate. `stage_velocity` becomes the binding bound.

## What holds

The pin does not move: `kbv-49feb73662b7`.

A goal revision bumps `goal_revision`, and `configs.json` names
`goal-mic-20260918-001-r6`. Carry it forward so the two do not disagree.

`degraded` stays `[]` on the re-run and stays honest.

## Done when

`goal.json` carries the target at the new revision, `configs.json` agrees on
the revision, A2 is re-run and committed, `python3 contracts/validate.py` ends
`0 failed`, and one commit as `seat:microscope-1`.

Then one sentence up: what A2's `missing` lists say now.

## Not this task

**Card 006**, the `near_names` migration, which still waits on the first E2.
If that E2 lands before you start here, do 006 first and fold this re-run into
it — A2 is in both, and running it twice is the thing to avoid.
