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

`.mcp.json` launches the server as
`${CLAUDE_PROJECT_DIR:-.}/librarian_agent/src/mcp_server.py`. In a session
opened at `simulation_agent/` that variable is unset, the fallback resolves to
`./librarian_agent/src/mcp_server.py`, and nothing is there — confirmed. The
server itself is fine: run from the repository root it answers `initialize`
normally. So the connection closes and the tools never appear.

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

- The validator is green. An earlier report of a red check 13 on
  `microscope_agent/.mcp.json` is stale: that file is gone and the tree reads
  `0 failed`.
