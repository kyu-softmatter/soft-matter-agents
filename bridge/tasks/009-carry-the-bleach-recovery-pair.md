# 009 — carry the bleach-recovery pair, both directions, when each card is ready

**For bridge-kyuhwan-macbook-20260930-3**, from
`manager-bridge-kyuhwan-macbook-20260930-3`, 2026-09-30 evening PDT. This is
standing work and does not open anything today: **no card for it exists yet.**

## The question

How fast our 100 nm fluorescent beads diffuse, measured by bleaching a round
spot and watching it recover. The person gave the question to the architecture
seat. Architecture split it: the simulation side predicts the recovery, and the
microscope side designs the experiment, both at the same time. Architecture
asked this seat to have the bridge carry each side's card across, so that the
predicted recovery reaches the microscope design and the design's chosen
settings reach the simulation **as cards, not by chat.** The relay came from
architecture, and as usual it grants nothing by itself. Everything below rests
on the bridge's own contract.

## What crosses, and what opens each round

The bridge carries a **plan or a result**. It does not carry a question or a
goal. A goal is what the receiving side writes from a delivered envelope.

| direction | payload | trigger |
|---|---|---|
| experiment → simulation | the microscope **plan** for this question, once it is validated and past DRAFT | `plan_completion`. No person needed: a finished plan crossing is the normal opening of a thread |
| simulation → experiment | the simulation **result** carrying the predicted recovery | `human`. A result crosses only when a person hands it over, and that person has to do it **in a window directly**. A relay naming the person is not a hand-over. Ask this seat, and this seat asks the person |

Do not open either round before its card meets that condition. If a plan is
still DRAFT, or a result has no hand-over, there is nothing to carry yet.

## What to check before wrapping (all yours to recompute; nothing here is a verdict)

1. **The observable.** At `a83b36d` the vocabulary has `tracer_diffusivity`, and
   both capability tables name it. Its estimator, though, is a single-particle
   mean-squared-displacement fit, which bleach recovery is not. If a card names
   a recovery observable the vocabulary lacks, answerability comes out
   `undeclared`. **Hold** the round as `bridge/CLAUDE.md` says and report to
   this seat. An unregistered name is a registration to make, not a refusal,
   and registering it is not the bridge's job. If a card instead names
   `tracer_diffusivity` with an estimator that does not match its entry, that
   is not your judgement either: carry it unchanged and say in the envelope
   note what the gate compared.
2. **An existing thread.** `thr-tracer-diffusivity-001` already carries
   `tracer_diffusivity` between the two sides. Before opening a new thread, run
   the duplicate check against the store under your own `caller_id`. Then
   decide, from the observable and the conditions on the two cards, whether this
   is a new thread or a new round of that one. **Write the reason in the
   ledger's note either way.** The handover of that thread to a new seat was
   never written into card 001. If you take a round on it, write the move there
   first.
3. **Units.** Check consistency against whatever the other side holds. The two
   cards land on different clocks, so `no_counterpart` on the first crossing is
   the honest answer and not a failure.
4. **Carry, do not judge.** No number added, rounded or "improved" in transit.
   The markdown names the payload and carries no number.

## Mechanics (as in 008)

- Deliver into `<agent>/inbox/<thread>/`: the envelope and its markdown,
  nothing else.
- `.git/config.worktree` pins every commit here to `seat:bridge-4`. Commit with
  `GIT_COMMITTER_NAME='seat:bridge-kyuhwan-macbook-20260930-3'` and
  `GIT_COMMITTER_EMAIL` set to your row's `committer_email` in
  `contracts/seats.json`. Read it from the file, not from a message. Check with
  `git var GIT_COMMITTER_IDENT`.
- Run `git diff HEAD -- <paths>`, then `git commit -F <file> -- <paths>`, then
  read the last lines and `git log -1`. Do not amend.
- **Commit and push when done.** This is the person's standing instruction,
  given in architecture's window on 2026-09-30 ("완료시 커밋 푸시") and relayed
  through architecture to this seat and to you. When a piece of work is
  finished and `python3 contracts/validate.py` ends `0 failed`, commit your own
  paths as above. Then `git fetch`, merge if origin moved, and
  `git push origin main`. Never force. Unfinished or failing work stays
  uncommitted, and another seat's paths are never yours to commit. If a commit
  prints `fatal:` because another seat holds `.git/index.lock`, it was not
  made. Retry once the lock is gone, and confirm with `git log -1`.

## Card 008

`thr-double-well-001` r1 is still unfiled, and card 008 names a seat that has
been archived. **The person was asked in this seat's window, on 2026-09-30,
whether to re-issue it to you, and answered no.** It is not yours. Do not file
`thr-double-well-001` r1. Card 008 stays as written, unassigned, and nothing
in this card waits on it.

## Report

To this seat, after each round lands or holds: the thread id, what crossed and
under which trigger, and whose turn `status.json` names.
