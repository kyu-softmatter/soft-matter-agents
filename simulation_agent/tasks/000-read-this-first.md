# 000 — read this before anything else

Written by `manager-simulation`. You read this; you do not edit it (§6.2-2).

This directory exists because a message is a notice and disk is the record.
Everything this seat was told on 2026-09-18 was told by message, and the
instructions that mattered survived only as long as the sessions did. That was
the defect §6.2-2 names, and this file is the repair.

## Identities — one per session, and the count keeps moving

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

## Who has what, because two seats share this tree

Two simulation sessions are open and there is **no worktree**, so nothing
refuses a collision — `seats.json` says so under `microscope-3` and names the
answer: *the manager allocates by card*. This is that card.

| | |
|---|---|
| **`simulation-3`** | **`004` — revision 2.** The person decided it. |
| **`simulation-2`** | hand `004` over; it cannot reach the librarian. |
| **a third session** | the `budget.json` split below — **ask first**, it collides with `004`. |

**`004` → `simulation-3`, 2026-09-20.** The person told the architecture seat
and it came down through this one, which is the right route: execution
allocation is the manager's. `simulation-3` is registered, its two commits pass
checks 35 and 41, and it **waited for an allocation rather than opening `004`
itself** — which is what made allocating possible instead of merging.

`simulation-2` hands it over because its window opened before the MCP fix and
settings are read at session start, so that seat cannot get the librarian
whatever the config now says. `004` is the librarian re-run by definition.

**`004` and the `budget.json` split both touch `src/plan_card.py`.** They cannot
run at once in a tree with no worktree. `004` goes first; the split waits or
takes the files `004` does not hold. Whoever picks up the split, say so here
before starting.

**Two things the arriving seat should read before starting, both learned the
hard way on 2026-09-20:**

- **The person's `envelope/safety.json` is guarded against `Write` and `Edit`
  and nothing else.** A heredoc reaches it and the gate cannot see a file that
  was written and reverted. `CLAUDE.md` now says so beside the path. Point
  `operator.ENVELOPE` at a scratch copy instead — one line, same coverage.
- **`failures.jsonl`'s row for `555317b` undercounts.** It says only `list`
  under `smoke` reached the wrong-field message; it is **two of eight, not
  one**, because `in` on a `str` is a substring test rather than a key test.
  `simulation-2`'s later row carries the correction — the seat that wrote the
  original had closed, and a post-mortem is append-only and another seat's, so
  it was not edited in place. **Read both rows.** The sharper lesson is not
  *check the type*: `in` means three different things — a key in a dict, an
  element in a list, a substring in a str — and `str` is the likelier hand-edit,
  a person leaving a note where an object belongs.

**Still open, and touching none of `004`'s files:**

1. **The librarian is reachable — settled 2026-09-20, and the fourth row of
   `failures.jsonl` records it.** `시뮬레이션 세션 4` confirmed it by **calling
   the server**, not by reading a tool list: a `kb_query` that refused as
   designed, logged with `claimed` filled. A session opened at
   `simulation_agent/` attaches.

   **There was one cause, not two, and this card said otherwise until now.**
   The user-level `~/.claude/settings.json` has carried
   `enabledMcpjsonServers: ["librarian"]` since 2026-09-19 and it applies
   regardless of directory. The only thing overriding it was a repo-local
   `disabledMcpjsonServers` in `.claude/settings.local.json`. Remove the deny
   and nothing further needs enabling — the repo side now reads `{}` and there
   is no per-agent file, and the tools attach anyway.

   **So the suspicion this card carried is closed, and it was never evidence.**
   It said the seven project entries in `~/.claude.json` are empty arrays so a
   second cause may exist. They are still empty and the tools attach, which
   means those arrays were not the mechanism at any point. Three rows of
   `failures.jsonl` reasoned from them. **Not visible from inside the
   repository is what made that reasonable and still wrong** — the deny lived
   in an untracked, globally ignored file that no seat could read.

2. **`read_envelope()` names the wrong field on one path.** A `limits` that is
   not a dict reports *carries no `smoke_budget`*, because the membership test
   runs first. The behaviour is right — it refuses — and the sentence sends the
   reader somewhere else, which is check 56's failure one level down. `005`
   records it.

**Done, so do not restart.** `001`. `003`. `005` (`c2f4bf5`) and the first runs
(`0a697f2`) — `runs/` holds `run-20260920-001` and `-002`, and `005` is marked
done with what was verified from HEAD. `002` is not separate work; it folded
into `004`.

**And read the inbox section of `CLAUDE.md` before you need it.** Rounds from
the bridge arrive in `simulation_agent/inbox/<thread>/`; an envelope sitting
there is the turn, and you never write into it. Taking a round is S2 and is
assigned by a task card the way an axis is — seeing one you have no card for,
report it up rather than starting it.

## The `budget.json` split — the section the table points at

**`plan.md` rules that there is no `safety.json` in this tree.** The file in
`simulation_agent/envelope/` is misnamed, and the reason is not tidiness:

> The grade of harm differs — get the laser ceiling wrong and you lose an eye,
> get the wall clock wrong and you lose a night. Putting the same lock on the
> same door was never decided.

So `envelope/budget.json`, and what goes away with the rename is **the
physical-confirmation requirement and Tier 3**, both meaningless about a disk
quota. **P0 rule 7 now binds `safety.*` only.** What a budget needs is that
somebody who knows that machine chose the number — not that anyone measured it.

**Done, by `manager-simulation`:** `contracts/schemas/envelope_budget.schema.json`.
`confirmation` is replaced by **`chosen_by`** — `by`, `on`, and an optional
`rationale` — and the schema refuses a `confirmation` or a `grade` pushed into a
limit, so the lower bar is expressed rather than merely permitted. Tested in
seven cases.

**What is left, and most of it is this seat's because `src/` is:**

1. **`src/axis_a5_budget.py`, `src/operator.py`, `src/plan_card.py`** — the
   paths and the artifact name. `operator.ENVELOPE` and `read_envelope()`'s
   three self-declaration checks both name `envelope_safety`.
2. **`envelope/budget.json` itself**, carrying what `safety.json` carries now
   with `confirmation` rewritten as `chosen_by`. The values do not change: 2 h,
   10 GB, 5 min / 500 MB, chosen by the person on 2026-09-19.
3. **Removing `safety.json`** — **ask before doing this one.** It is committed
   (`fa1d69f`, `human@seat.invalid`) and it is a `safety.*` file, so Tier 3
   still reads as binding until it is gone. Whether the rename is the person's
   act or this seat's is not settled anywhere, and it is cheaper to ask than to
   be the seat that deleted a P0 file on its own reading.

**Ordering ruled 2026-09-20, because `plan_card.py` writes the path into the
card.** Line 154 emits `"checked_against": ["…/envelope/safety.json"]`, so a
revision 2 generated before the rename is **born naming a path that will
vanish** — and **nothing catches that**: check 8 reads a `checked_against` only
for a bridge envelope's answerability, against `contracts/capabilities/`.
Nothing reads this one.

**So `plan_card.py` goes first, then `004`.** Not the other way, and not folded
into `004`. `004`'s one-commit argument is that **one pin blocks its four items
and one revision bump releases them** — a path string is neither pinned nor
revision-bumped, so attaching it widens a commit that is already four things
and hands the file to the seat that is not in it. The overlap is exactly one
file, so reversing the order costs nothing.

**And the same two lines are already stale in a second way.** The `note` beside
them says *"The file is absent, so there is no allowance to compare the
estimated cost against, and A5 abstained for the same reason."* The file has
existed since 10:33 and `check_budget` returns `inside`. Fix both while there.

**No fallback while the two files overlap.** `operator` reads `budget.json` and
nothing else; absent means `unavailable` and the run refuses, which is the state
this tree was in all morning and is safe. A fallback would make behaviour depend
on which files happen to be present, and if both exist and disagree it picks one
silently — P0 stops on ambiguity rather than choosing. **Land `budget.json` in
the same commit as the operator change** and there is no window to bridge.

**Then, and only then, `manager-simulation` tightens two things** — removing
`simulation_limits` from `envelope_safety.schema.json`, and narrowing
`ALLOWED_PATHS` from `envelope/[anything]` to the declared names per agent, so
§7's tree becomes binding rather than descriptive. **Both are held until the
swap lands**: doing either first refuses the file that is there now, and a gate
that refuses correct work is one somebody reaches around.

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
