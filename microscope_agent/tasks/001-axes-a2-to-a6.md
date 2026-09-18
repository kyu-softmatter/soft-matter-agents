# 001 — the remaining axes, A2 to A6

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

## Where this picks up

A7 and A1 are done and committed, for `mic-20260918-001` on `widefield_inline`
— one configuration, seven `caller_id`s issued. Both abstained, with reasons
per inequality. That is the correct outcome and not a setback: the store holds
25 entries and almost none of them are about this instrument's detectors.

Read `microscope_agent/CLAUDE.md` first. It carries the rulings that already
apply — what transfers from the prior project and how, the plan-names-an-
element rule, the no-running-sum rule, and the operator questions still open.

## The task

Write A2, A3, A4, A5, A6 for the same configuration, then stop.

Order them by what the store can actually answer, not by number:

- **A4 first.** The device registry is the one table with real content, so this
  is the axis most likely to return an interval rather than abstain. Channels,
  read-back, automatability, path exclusivity. `optical_tweezers` and
  `laser_combiner` are `read_back: false`, and §4.6.6 rule 5 makes them manual,
  which makes an individual approval mandatory (§6.1). That consequence belongs
  in the card.
- **A6 next.** Six objectives carry NA and working distance at E3. The
  diffraction limit computes. Sampling does not — no pixel size is in the
  store, so Nyquist is `no_input` and says so.
- **A2, A3, A5** after. Expect mostly `no_input`. A3 is where the fluorescent
  widefield choice bites: bleaching runs during the record and the observable
  is a width over that record, so the bias grows with time. No bleaching rate
  exists, so the inequality abstains — but say the coupling in the reason.

## What holds

Every inequality the axis owns gets an entry: interval, or an abstention with
`kind` and `reason`, and `missing` named when `kind` is `no_input`. Silence is
refused (§4.5.2.1). An interval with neither bound is that same silence.

An axis states a range and does not choose inside it. It does not read another
axis's output, and it does not read lessons (P16).

## Done when

Five cards committed and `VALIDATED`, the validator at `0 failed`, dead ends
appended to `questions/<qid>/failures.jsonl`, and the one-sentence answer sent
up: what is not yet on disk.

## Not this task

S4 and S5. They come after, and they are what the bridge is waiting for — one
`plan` card, needing no execution, no `envelope/safety.json` and no approval.
Do not start them here; a task that grows while it runs cannot be finished.
