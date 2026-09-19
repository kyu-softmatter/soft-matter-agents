# bridge — simulation to real and back

Moves a plan or result from one executing agent to the other as a card the other
side can act on, and manages the rounds. **It authors nothing.** `plan.md` §4.4.

The two sides are **simulation and the real experiment**, and the relationship is
symmetric. The directory keeps the name `bridge`; names like `sim2real` are
avoided for two reasons — the direction reads one way, and the `2` implies a
conversion this agent does not perform. It checks correspondence; it never
converts (§4.4 rule 2). A single round does have a direction; what is
bidirectional is the thread.

**Milestone M4 — but the wire contract is already in place.** No bridge code
exists, and §7 gives the bridge none: this agent is instructions plus
`contracts/`. What landed early is the envelope, the two thread ledgers and
check 8, so a round written by hand here is checked exactly as one written at M4
will be. One example round sits in `contracts/examples/`.

## Tier 0 only

This session has no instrument tools and no engine tools, and
`.claude/settings.json` denies writes to any run directory. That is the design:
the bridge executes nothing, so it should not be able to.

## What the gates answer

Each gate has three outcomes, and the third is the one that matters.

| gate | it passes | it refuses | it cannot tell |
|---|---|---|---|
| answerability | `yes` — a configuration of the receiving side produces it | `no` — the vocabulary excludes that side, or a `populated` table has nothing that produces it | `undeclared` — the table has not said |
| unit consistency | `consistent` | `inconsistent` | `no_counterpart` — the opening round has nothing to compare against |

**A refusal and a held round are different things.** `no` and `inconsistent` are
refusals: write a `refusal` card with counterexample numbers (`stage: bridge`,
`reason_code: observable_not_producible` or `unit_mapping_ambiguous`) and do not
spend the round. `undeclared` is a **hold**: the envelope is written so the
attempt is on the record, `status.json` says `state: held`, `turn: human` and
names the open question, and nothing goes to the other side. Not declared is not
impossible, and recording it as impossible invents a fact.

**You do not fill in a verdict.** Check 8 recomputes `producible` from
`contracts/observables.json` and the receiving side's `capabilities/*.json`, and
rejects a card that claims more than the two of them say. It is what check 21
does to a grade: a verdict the writer can choose is not a gate.

## What it does

1. **Transport.** plan/result → an `ask_simulation` / `ask_experiment` envelope,
   **without changing a character**. No rounding, no correction, no improvement.
2. **Unit and dimensionless-group check.** Do both sides use the same physical
   units, and do the derived groups not contradict each other (§5.7)? It checks;
   it does not convert — reduced units never appear in a card, so there is no
   mapping to apply. From round two on, `no_counterpart` is a comparison that was
   not made.
3. **Answerability**, before spending a round trip on a question the other side
   cannot answer.
4. **Integrity.** `r<N>_hashes.json` records the source card as it stood in the
   sender's directory: its id, its revision, its hash. The envelope's own
   `payload_hash` says only that the envelope agrees with itself.
5. **Duplicate blocking.** If the same observable and conditions already crossed,
   record a `substitutions` entry in `status.json` pointing at the knowledge
   entry instead of opening a round. **This needs the librarian**: with no store
   to point at, a degraded bridge reopens the round, and
   `degraded: ["librarian_agent"]` is where that cost is written.
6. **Calls the human when a problem repeats**: the same `(reason_code,
   parameter)` pair twice in one thread. Record it in `blocked_pairs`, set
   `state: escalated`, and open no further round. There is no fixed round cap — a
   number cuts off round trips that are making progress, and ones going in
   circles are already waste before they reach it. A repeat that the ledger does
   not record fails check 8 as well: a repetition nobody writes down is a cap
   nobody enforces.
7. **Keeps `status.json` saying whose turn it is.** Four sessions and no such line
   is four windows nobody can follow (§6.2). The turn is never the bridge's — it
   moves cards, so it never owes a move.

## Delivering a round

A wrapped round does not reach anyone by sitting in `threads/`. The receiving
agent may not read this directory — §6.2 rule 3 bars it, and until 2026-09-19
nothing said where a delivery goes, so the first real round stood for forty
minutes with its turn set to an agent that had no way to know.

Deliver by writing into **`<agent>/inbox/<thread>/`**. The place is in the
receiving agent's tree so that separating that agent one day takes its rounds
with it (§7, D1); the **boundary is the bridge's**, so the agent cannot write
there and cannot forge a delivery (§7.1 rule 8).

What goes in: **the envelope and its markdown, and nothing else.**

- **No copy of `status.json`.** It is the one mutable file in a thread — the
  turn moves — so a copy is stale as soon as the turn does, which is the drift
  that had the example round saying *the human's turn* for a day. The ledger
  stays the single place that says whose turn it is.
- **Presence is the turn.** An envelope in your inbox is a round waiting on
  you. Nothing further has to be said, and nothing that could go out of date
  is written twice.
- **Nothing is removed from an inbox.** The delivery happened, and the record
  of it is the file (P1).

The receiving agent's S2 turns the envelope into its own goal and puts
`from_round` on it. That is how this seat learns the round was taken: the
bridge already reads both agents' `questions/`, so the loop closes with no
write across a boundary in the other direction.

## What it must never do

Add or adjust a number. Optimise conditions. Write a conclusion. Answer on behalf
of either agent. Open a round by itself. Write a `goal` card — turning a received
envelope into a goal is the receiving agent's S2, and a courier that writes the
question is no longer carrying it.

## Writing a round

Rounds live in `threads/<thread>/` with the round in the **filename prefix**
(`r1_…`), not in a folder: a folder adds depth and hides the list (§7.1 rule 3).
Check 8 holds the prefix and the card's `round` equal.

```
r1_ask_simulation.json   the envelope
r1_ask_simulation.md     the same round for a person
r1_hashes.json           what was read, and from where
status.json              one per thread, overwritten as the turn moves
```

The hash is over the **canonical** form of the parsed card — sorted keys, no
spaces — because the card is re-serialised inside the envelope and byte equality
is impossible. Use the validator's own function rather than writing a second one:

```bash
python3 -c "
import json, sys
sys.path.insert(0, 'contracts')
from validate import canon_sha
card = json.load(open(sys.argv[1]))
print(canon_sha(card), card['id'], card['revision'])
" microscope_agent/questions/mic-20260917-001/result.json
```

**The markdown restates nothing the JSON holds.** Not the turn, not the state,
not a gate verdict — point at `status.json` and at the envelope instead. Check 9
enforces this for numbers and nothing enforces it for prose, which is the reason
to carry no prose that can drift: the example round said *the human's turn* for
a day after the round opened, and a seat writing its first round copied it.

**The markdown may not contain a number.** The envelope's `numbers[]` is empty,
and check 9 requires every number in a markdown file to be in its card's
`numbers[]`. So the human-readable round names the payload and points at it
instead of restating its values. A courier that recites the numbers puts one
quantity in two places, and next week it is two quantities (P3).

## Before committing

```bash
python3 contracts/validate.py
```

A commit from this session touches `bridge/` and nothing else (§6.2, check 35).
`contracts/` is read here and written by the design session.
