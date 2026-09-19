# 000 — read this before 001

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

**The hold is lifted.** This file replaces `000-hold-until-the-librarian-
serves.md`, which told you to start nothing. Its premise was the A/B, and
`58064da` deferred the second variant: the person stopped `microscope-2` and
removed the worktrees. §9.3's constraints — the librarian gate, the matched
`qid`, the ban on pre-start rulings — existed to keep two variants even. With
one variant they protect nothing and only cost, so they are off. You are a
microscope execution seat, not half of a comparison.

The old card is in the history, not deleted from it. §9.3 is likewise marked
deferred rather than removed, and the `microscope-2` seat and branch stay
(P16): the branch holds what that variant built, and removing the seat entry
would turn its commits into unattributed ones.

## Start here

**Task 001, A2 to A6, on `mic-20260918-001`.** Not a new question. That
fan-out is two axes of seven in, A1 and A7 are committed, and 001 was written
for exactly this before the A/B existed. Its opening claim still holds — I
checked rather than assumed: the store is still at 25 entries.

**002 is closed**, at `ab2eb6f`. Nothing else on disk says so. Do not redo it.

## Do not re-pin. Answer at `kbv-49feb73662b7`

The siblings are pinned to `kbv-49feb73662b7` and the store has since moved to
`kbv-67f9ad766d92`, so check 25 shows five PENDING lines for this directory.
**Leave them.** Write A2–A6 against `kbv-49feb73662b7` too.

Three reasons, and the first is the one that was learned expensively:

- **Chasing the store does not converge.** Task 002 re-pinned this fan-out
  once, and the card naming the target was stale four minutes after it was
  written because the store moved again. It has moved twice more since. A
  fan-out that re-pins whenever the librarian commits never finishes.
- **The server now serves an old pin** rather than refusing it (`4033b4d`).
  `_preflight` returns the store as of the version you pinned, and every
  answer carries `answered_from` saying which version and which commit
  replied. That is what makes staying put honest instead of merely
  convenient — the pin names a state the server can still produce.
- **Check 33 requires siblings to agree.** A2 answered at today's version
  while A1 and A7 sit at `49feb73662b7` fails it, and re-pinning the two
  finished cards to keep up is the treadmill again.

If you find a reason the pinned version cannot answer some axis, that is a
finding to send up, not a licence to re-pin.

## The librarian answers now

**Settled on 2026-09-19, by measurement rather than inference.** The tools
attach, the service replied, and `librarian_agent/queries/log.jsonl` holds the
first record this repository has ever had of the service answering:
`caller_id` `mic-20260918-001:widefield_inline:a4`, pinned at
`kbv-49feb73662b7`, `answered_from` naming commit `9baf01d` and
`reproducible: true`. The served digest matched that commit's blob byte for
byte, and *differed* from the working-copy file — which is the confirmation,
not a problem: the entry gained a field afterwards and the server correctly
served the version the pin names. Staying on `kbv-49feb73662b7` is therefore
not just permitted, it is demonstrated.

**An earlier version of this card was wrong about why, and the error is worth
keeping.** It said `enabledMcpjsonServers` is empty at every project path, so
no session could see the tools. The first half is still true — it is empty
everywhere — and the conclusion was false: the tools attached anyway. **That
field is not the gate.** What was blocking was the server path, fixed by
`8d4a604`. If a seat ever fails to attach, do not diagnose it from that field;
read the launcher's own log:

```
~/Library/Caches/claude-cli-nodejs/<path with / replaced by ->/mcp-logs-librarian/
```

It records the `cwd` the server started in and any `Server stderr`. Note what
it does **not** record: the `kb_version`. Connection success there does not
tell you which store answered — only a call does, through `answered_from`.

**A contract fix that is not yours to make alone.** `d6999e5` takes an
observable's definition out of the cards, leaving the name to be read from the
vocabulary. `questions/mic-20260918-001/goal.json` carries one, on
`diffusivity`. The bridge manager is coordinating the window because the other
cards belong to other agents and fixing one alone turns HEAD red. **Leave it
until that window opens**; I will card it.

## Your identity

There are no worktrees now — `git worktree list` reports one checkout — so the
`--worktree` mechanism has nothing to attach to. Set it per command:

```bash
GIT_COMMITTER_NAME='seat:microscope-1' GIT_COMMITTER_EMAIL=microscope-1@seat.invalid git commit -F msg -- <paths>
```

**Keep `microscope-1`, not the undivided `microscope`.** You are that seat
whether or not its worktree exists, and the branch keeps the identity if one
is made again. `microscope` stays valid only for the commits already made
under it.

Because you are in the shared checkout, §6.2.1 applies again: name paths
rather than using `-A`, and commit with `git commit -- <paths>`. Other
sessions are editing this same working copy.
