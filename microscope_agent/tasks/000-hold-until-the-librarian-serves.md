# 000 — read this before 001 or 002

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

**Nothing in `tasks/` is startable right now.** If you have just opened in a
worktree and are looking for the first thing to do, it is not here. Stop, and
read the gate below.

## What is already finished

**002 is closed.** `ab2eb6f`, committed by `seat:microscope`. The fan-out
`mic-20260918-001` is re-pinned to `kbv-49feb73662b7`. Do not do it again.

Do not take that on this file's word — the point of writing it down is that
you can check it. All 24 pins in `microscope_agent/questions/mic-20260918-001/`
read `kbv-49feb73662b7`. Two older strings remain in that directory and are
supposed to: a provenance note in `goal.json` recording what it was re-pinned
*from*, and a `failures.jsonl` record of an event that happened at the older
version. A historical record that silently adopted today's version would be
the defect, not the fix.

## What is held, and until when

**001 (A2–A6) is held. So is every §10.2.1 ruling.** Do not read the prior
project's branches and rule on what crosses, and do not write
`tasks/NNN-rulings.md`, until the gate opens.

The gate has two conditions, both observable on disk (§9.3, `9ebd137`):

1. `.mcp.json` registers the librarian server. Registration is met
   (`2bfc229`) and it is inherited downward, so one entry at the root covers
   a session opened in a subdirectory. **Registration is not enough, and the
   shortfall is larger than a worktree question.** The person must approve
   the server; approval lives in `~/.claude.json` as that path's
   `enabledMcpjsonServers`, and as of 2026-09-18 that list is **empty at
   every path** — the shared copy, `microscope_agent/`, and the worktrees
   alike. So the server has never been approved anywhere, not merely not
   inherited into a worktree. (`microscope-1` has no entry at all, which is
   simply what a path no session has ever opened in looks like.)

   `hasTrustDialogAccepted` is `true` everywhere and is **a different
   setting**. Passing the trust dialog is not approving the server, and
   reading it as though it were is the easiest way to believe you are served
   when you are not.
2. `librarian_agent/queries/log.jsonl` exists and holds at least one record
   carrying the `caller_id` of a real question. **Check this yourself**; as of
   this card the directory holds only `README.md`.

**The first condition fails silently, which is why it is worth your
attention.** A session that cannot see the librarian tools does not error —
it falls through to the degraded path (§0.3-4) and writes cards that look
fine. So do not infer from "no error" that you are served. Confirm you can
see the librarian tools before you believe condition 1, and if you cannot,
that is the thing to report rather than to work around.

**Check the gate, not this file.** A card that says *held* keeps saying it
after the hold should have lifted — that failure has already happened in this
repository this week, on task cards that read `status: open` for work that was
finished hours earlier. So: if condition 2 is met and no card newer than this
one has arrived, this file is the stale thing. Say so upward rather than
either obeying it or ignoring it.

## Why the hold exists

The microscope execution is being built **twice**, as two variants on two
worktrees, and the better one is chosen afterwards (§9.3). Two things follow
and both are the reason you are being stopped.

**A comparison measures what differs.** If one variant starts the axes or
banks §10.2.1 rulings while the other has nobody sitting at it, the thing the
comparison measures is which worktree had a session first. §9.3's second
criterion counts exactly the rulings file, so that tilt lands directly on the
score. As of this card there is a session on one variant and none on the
other, which is why the answer is *neither starts* rather than *both hurry*.

**The `degraded` criterion cannot be checked backwards.** A card written
while no query log exists records `degraded` with nothing to verify it
against, ever. That is the whole content of condition 2: cards written before
the librarian serves are permanently unauditable, so they must not be the
cards being compared.

## What you may do while held

Read. `microscope_agent/CLAUDE.md` first, then `plan.md` §9.3, §10.2.1 and
§4.5. Reading is not ruling: form no judgement on paper about what transfers
until the gate opens, because that judgement is the thing being counted.

Confirm your own seat and worktree. Your committer identity should read
`microscope-1@seat.invalid` or `microscope-2@seat.invalid` — not
`microscope@seat.invalid`, which is the undivided identity and makes check 41
unable to tell the two variants apart. It lives in the worktree's own config
(`extensions.worktreeConfig` + `git config --worktree`); `--local` in a linked
worktree writes to the shared config and leaks your seat to every session,
which §6.2.3 prescribed by mistake until `44f368b`.

**A contract-compliance fix is not under the ban, and still must not happen
here.** When a schema or the vocabulary moves and the cards have to follow,
that is neither variant's design, so §9.3 does not forbid it (`7ed85cd`). But
a neutral change made on one branch only is still a difference, and the
comparison measures differences — it cannot tell a design choice from a
housekeeping commit one side happened to make. **Shared fixes land on `main`
ahead of the branch point**, and both variants take them by branching from the
SHA that already contains them.

One such fix is pending as of this card. `d6999e5` takes the definition of an
observable out of the cards and leaves only its name, to be read from the
vocabulary. Across the repository eight cards carry a `definition` and six of
them disagree with the vocabulary; **one of those is ours** —
`questions/mic-20260918-001/goal.json`, on `diffusivity`. It will be corrected
on `main` under its own card. **If you find it while reading, leave it.** A
card you fix here is a card the other variant did not fix, and that is the
whole of what went wrong.

## When the gate opens

Both variants get the same card, with the same `qid`, the same goal card and
the same observables, issued at the same time. That card comes from
`manager-microscope`. Do not write your own and do not start from 001 as it
stands — 001 was written for a single execution before the comparison existed,
and it names a question that is already answered.
