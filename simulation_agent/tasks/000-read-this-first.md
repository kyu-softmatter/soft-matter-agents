# 000 — read this before anything else

Written by `manager-simulation`. You read this; you do not edit it (§6.2-2).

This directory exists because a message is a notice and disk is the record.
Everything this seat was told on 2026-09-18 was told by message, and the
instructions that mattered survived only as long as the sessions did. That was
the defect §6.2-2 names, and this file is the repair.

## Two seats, two identities — settled, and session 2 may commit

`simulation-2@seat.invalid` was registered on 2026-09-18. This section used to
say session 2 must not commit, and **that instruction is withdrawn**: it was
right while one identity covered two sessions, and it went stale the moment the
registry grew. A standing order that outlives its cause stops being a
precaution and becomes a seat idling for no reason.

- **Session 1** keeps `simulation@seat.invalid`, where all of this agent's
  commits are.
- **Session 2** commits as `simulation-2@seat.invalid`, same `owns`, no
  `paths`.

The reason both exist is in the registry's `one_identity_per_session`: two
sessions sharing an identity is not a seat, it is a hole, because check 41
cannot tell them apart and passes their mixture. It happened twice on
2026-09-17 and **both times the check passed and the pass was the defect.**

No branch is assigned to this agent, and none should be created. Worktrees were
reverted on 2026-09-18 (`328176f`), so this is one shared working copy and a
branch switch moves the files under every other session. Name paths, never
`-A`, and use `git commit -- <paths>`.

## The librarian answers now, and what is left is smaller than it was

**`.mcp.json` landed and the service answered for the first time on
2026-09-19.** It resolves the server through `git rev-parse --show-toplevel`,
so each checkout gets its own store and no session depends on where it was
launched from. The history of the three forms that did not work is in §7 and is
worth reading once; it is no longer a blocker.

Two things about it still hold and are easy to get wrong:

- **Project MCP config is read at session start.** A session opened before
  `8d4a604` cannot see `mcp__librarian__*` no matter what the file says. If the
  tools are not in your session, the answer is a new session, not a workaround.
- **A session that cannot see the tools must not write a card claiming the
  service answered.** `degraded: ["librarian_agent"]` is the honest value, and
  session 1 already made that structural: `cards.evidence` defaults to degraded
  and clears only when a reply names the server. Do not reintroduce a hardcoded
  `degraded` anywhere.

**Check 45 now reads that claim against the query log** — a card whose
`degraded` omits the librarian must have a call logged under its `caller_id`.
Know what it does and does not do: the log **carries** the claim and does not
verify it, because `caller_id` is an argument and the server cannot see the
identity behind it. A line proves a call was made under that id, not that you
made it. What it forecloses is the card with no line at all.

## How a hold is written here, because two of them went stale in one day

A card that says *do not start yet* is the most perishable thing in this
directory, and this seat has now had to withdraw two of them within hours of
writing them: `000`'s *session 2 does not commit*, and `002`'s *do not start*.
Both named their release condition in prose. Both stayed after the condition
cleared, because **prose does not re-check itself and nobody re-reads a card
that says wait.**

So a hold in this directory carries a **condition you can run**, not a
sentence you have to remember to re-evaluate:

```bash
# 002 was held on this, and it now returns the inline branch:
python3 -c "import json;print(json.load(open('contracts/schemas/goal.schema.json'))['properties']['targets']['items'])"
# 003's third step is held on this returning 0:
python3 -c "
import json,glob,re
print(sum(1 for f in glob.glob('simulation_agent/questions/*/axis_*.json')
          if not re.search(r':v\\d+:', json.load(open(f)).get('caller_id',''))))"
```

**The cost of a stale hold is not confusion, it is an idle seat.** `simulation-2`
sat registered and not committing for a day because one sentence outlived its
reason, and the only thing pointing at that sentence was the sentence. A hold
whose release is a command is one line to check and cannot quietly outlive
itself.

**And a hold names who lifts it.** If that is this seat, say so, because a card
that holds on somebody unnamed holds forever.

## What is startable right now, in order

**1. `005` — one line, and it is the only thing between here and the first
entry in `runs/`.** `check_budget` reads the envelope's old flat shape, which
this seat's manager broke on 2026-09-19 when the schema gained a per-agent
`limits` block. The person saved `envelope/safety.json` on 2026-09-20 at 10:33,
so the path is live rather than hypothetical:

```
'smoke'  ->  KeyError: 'smoke_budget'
'full'   ->  'unavailable'   compared=0
```

The card carries the fix and the verification. Check the shape against
`contracts/schemas/envelope_safety.schema.json` rather than taking the diff —
the seat that wrote both is the one that got it wrong.

**2. Then a mock smoke run.** `runs/` is empty; nothing has ever run here,
`mock_backend` included. §9.2 rule 4 puts the engine after the pipeline passes
with mock, and §4.6 makes mock a first-class backend — so this run, not HOOMD,
is the next real milestone. HOOMD is not installed and is not on PyPI
(conda-forge only), which is correct rather than missing.

**3. Then `004` — revision 2, one commit.** Four things converge on it and the
card says why they are one: the diameter alignment, the target inline, the
librarian re-run, and the `caller_id` at `:v2:`. It needs the librarian, which
needs this session to have been approved for the server — see the root
`CLAUDE.md` on why approval is per session and does not inherit.

**Done, so do not restart them.** `001` (the observable definition). `003` (the
`caller_id` migration — zero old-form ids remain and `issue()` takes the
revision). `002` is not separate work; it folded into `004`.

**And read the inbox section of `CLAUDE.md` before you need it.** Rounds from
the bridge arrive in `simulation_agent/inbox/<thread>/`; an envelope sitting
there is the turn, and you never write into it. Taking a round is S2 and is
assigned by a task card the way an axis is — seeing one you have no card for,
report it up rather than starting it, because two seats share this tree and a
round each assumes the other took looks staffed while nobody holds it.

## What is already true, so do not redo it

- The fan-out emits the three calls it would make, and stops there:
  `python3 -m src.fanout <qid> <created_at> --queries`. A1 and A4 want
  `kb_group(symbol='tau_d')`, A3 wants `kb_query`. MCP tools are called by the
  model, not by Python, and that boundary is already in the code. When the
  tools appear, the work starts at the call, not at the wiring.
- `caller_id` is issued by the fan-out runner as **`<qid>:v<N>:<config>:<axis>`**
  (§4.3.1). An axis module never chooses its own — the rule exists so a
  sibling's id cannot be worn, including by text arriving from a search. **The
  revision is in the id** because the id is also the server's isolation unit:
  without it the same axis at two revisions shares one session context, and a
  re-run inherits the attempt it exists to replace. Revision 1 writes `v1`
  rather than omitting it. This file said the form without `v<N>` until
  2026-09-19; that form is still accepted while the cards that predate
  `a6dca6a` migrate, and stops being accepted after.
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

  Two things about it were settled after this file first said so. The prefix
  is **`v<N>_`**, not `r<N>_`: rule 3 had put rounds and revisions in one
  sentence, the check read the prefix as a round and compared it to the card's
  `round` field, and `a6ab72b` split them. And revision 2 **may cite revision 1
  as a record and may not take it as input** — the comparison "revision 1 said
  X, this differs because Y" is the point of keeping it, while feeding its
  numbers into a fresh calculation inherits the reason the re-run exists.

- The validator is green. An earlier report of a red check 13 on
  `microscope_agent/.mcp.json` is stale: that file is gone and the tree reads
  `0 failed`.
