# 000 — read this before anything else

Written by `manager-simulation`. You read this; you do not edit it (§6.2-2).

This directory exists because a message is a notice and disk is the record.
Everything this seat was told on 2026-09-18 was told by message, and the
instructions that mattered survived only as long as the sessions did. That was
the defect §6.2-2 names, and this file is the repair.

## Two seats, one identity — do not commit until this is settled

There are two live simulation execution sessions and **one** identity,
`simulation@seat.invalid`. `contracts/seats.json` says what that costs:
`one_identity_per_session` records that two sessions sharing an identity is not
a seat but a hole, that it happened twice on 2026-09-17, and that **both times
check 41 passed and the pass was the defect.**

The registry's own `growth` note prescribes the fix — a second execution
session gets its own identity with the same `owns` and no `paths`, following
the `microscope-2` precedent, so `simulation-2@seat.invalid`. `seats.json` is
in `manager-simulation`'s `excludes`, so this seat cannot issue it. **Raised to
the architecture seat.**

Until it lands:

- **Session 1** (the one that committed `d1364e5`) holds `simulation@seat.invalid`
  legitimately and may commit.
- **Session 2** does not commit. Read, audit and prepare; leave the writing.

The same message raised the worktree question. `seats.json` says the seat is
the worktree rather than the session, and two seats sharing one boundary in one
working copy overwrite each other. No branch has been assigned to this agent.
Do not create one: a branch switch in a shared working copy moves the files
under every other session.

## The librarian is unreachable, and the cause is known

M2's remaining completion condition is one pass with the librarian **on** —
`kb_refs` filled, `kb_gaps` filled, `degraded` **empty** (§9.1). It cannot be
met today, and not because of approval.

**The path is fixed as of `8d4a604`** and the remaining obstacle is smaller.

Three forms have been tried and the history is in §7. A plain relative path
resolved against the session's cwd. `${CLAUDE_PROJECT_DIR:-.}` fell back to
`.` because that variable is not set here, so a session at `simulation_agent/`
looked for `./librarian_agent/src/mcp_server.py`, which does not exist. An
absolute path into the shared checkout worked and was measured to be wrong for
a different reason: `microscope-1`'s worktree held `kbv-fdef964aca56` while
the shared copy answered `kbv-67f9ad766d92`, so a worktree session's cards
would cite a version whose bytes are not in its own checkout. The current form
resolves `git rev-parse --show-toplevel`, which gives each worktree its own
store and gives this directory the repository root. Confirmed to resolve here.

**Resolving is not the same as connecting, and nobody has checked the second.**
The test is not that the path is right; it is that `mcp__librarian__*` appears
in a session opened at an agent directory. Only a session started after
`8d4a604` can make that observation, because project MCP config is read at
session start.

**A session that cannot see the tools must not produce a card claiming the
service answered.** `degraded: ["librarian_agent"]` is the honest value while
this holds, and session 1 already made that structural: `cards.evidence`
defaults to degraded and only clears when a reply names the librarian server.
Do not reintroduce a hardcoded `degraded` anywhere.

`.mcp.json` is the architecture seat's path. **Raised there**, with the
constraint stated: the path must not depend on the launching session's working
directory, and `CLAUDE_PROJECT_DIR` is not set in this context.

## What is startable right now

**`001`.** It needs no librarian and no new identity — but see the seat rule
above for who commits it.

## What is already true, so do not redo it

- The fan-out emits the three calls it would make, and stops there:
  `python3 -m src.fanout <qid> <created_at> --queries`. A1 and A4 want
  `kb_group(symbol='tau_d')`, A3 wants `kb_query`. MCP tools are called by the
  model, not by Python, and that boundary is already in the code. When the
  tools appear, the work starts at the call, not at the wiring.
- `caller_id` is issued by the fan-out runner as `<qid>:<config>:<axis>`
  (§4.3.1). An axis module never chooses its own — the rule exists so a
  sibling's id cannot be worn, including by text arriving from a search.
- **The cards of `sim-20260917-001` read `kbv-9bc3910f1886`.** That is what
  `e36b6f7` (2026-09-18 07:44) was built against — checked against the store's
  own history, not against the cards — and `failures.jsonl` records the same
  value at 11:45. Any other value in those cards is a re-stamp, not a reading.

  **This line was right, then this seat corrected it to a wrong value, and the
  correction is reverted.** The mistake is worth more than the value. Session 1
  reported the cards no longer held `9bc3910f1886`; that was true, and this
  seat checked it — by looking at what the cards say **now**. All twenty
  references read `49feb73662b7`, so the file looked stale and was "fixed".

  **That is the wrong question.** A pin does not mean "what does this card say";
  it means "what did this question read", and only the history answers that.
  Checking the cards to validate a pin is checking the subscription to validate
  the record. Session 2 went to the history and found four silent moves:
  `898241c` stamped `49feb`, `d1364e5` stamped a value the store had left
  twenty seconds earlier, `4a754c2` stamped `67f9ad` in a commit whose message
  is about observables, and a fifth was in progress.

  So the rule, stated twice because it has now been broken in both directions:
  a document that has gone stale is corrected against **the history**, never
  against the cards, and the cards are never corrected against the document.

  **And the rule that would have prevented all four moves: regenerating a
  finished question in place is the defect.** §4.5.5 already says it — a re-run
  reuses the `qid` and **raises `revision`**, and the earlier outputs stay
  beside it under an `r2_` prefix (P9, §7.1 rule 6). Every card here is
  `revision: 1`. The fan-out was rebuilding revision 1 over itself, so each run
  had to choose a version for cards that had already read one, and there is no
  right answer to that question.

  This also answers the objection that pinning `9bc3910f1886` is unusable
  because `kb_group(symbol=…)` did not exist in that store version. It is
  unusable **for a new query**, and a new query is not revision 1's business.
  When the librarian is reachable, the fan-out makes **revision 2**: it pins
  the store as of that run, asks with the vocabulary that store has, and leaves
  revision 1 alone as the record of what was read in the first place. Nothing
  has to be re-stamped for the gate to open.

- **`sim-20260917-001` is revision 1, and stays revision 1 despite six edits.**
  `45b2b5f` made §4.5.5 a mechanism — `r<N>_` prefixes, and `refuse_overwrite`
  stops rather than replacing a card of another revision — and running it
  surfaced six intermediate states. They were collapsed back into revision 1
  on purpose.

  The reason is worth keeping, because it is not "they were small". A
  `revision` is the unit an approval names and a result cites (§5.5, §6.1).
  Checked: nothing anywhere in this repository cites this qid, there is no
  approval card and no run, so none of those six was ever named or acted on.
  They were saves. Numbering them would make `revision` mean *how many times
  the author edited*, and restoring `r2_`–`r6_` would put numbered revisions
  on disk that nobody ever cited — the same confusion pointed the other way.
  What changed between them is in the history, which is where that belongs.

  Revision 2 is the librarian run, when it happens. Not a save.

- The validator is green. An earlier report of a red check 13 on
  `microscope_agent/.mcp.json` is stale: that file is gone and the tree reads
  `0 failed`.
