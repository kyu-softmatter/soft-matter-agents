# bridge

The other three agents each answer a question. This one does not. It carries a
card from one of them to the other and keeps track of whose turn it is.

That sounds like plumbing and is mostly a discipline: **the bridge authors
nothing.** It does not add a number, round one off, improve a condition, write
a conclusion, answer for either side, or decide to start. A courier that edits
the parcel is not a courier, and every rule here is a way of making that
checkable rather than promised.

**It is the only agent that never touches a number.** The other three measure,
compute and estimate; this one carries what they produced without adding a
digit. The envelope holds no numbers, no assumptions and no knowledge
references of its own; it is tied to the card it carries by a hash; and
whether the other side can even produce the observable is **derived** from the
shared vocabulary and that side's capability table rather than judged here.
That the carrier does not judge is the whole reason it exists.

## What it is made of

A round lives in `threads/<thread>/` and is four files:

- an **envelope** wrapping the card being carried, unchanged
- the same round **for a person to read**
- a **ledger** of what was read and from where
- one **`status.json`** per thread, saying whose turn it is

A delivered round lands somewhere else: **`<agent>/inbox/<thread>/`**, in the
receiving agent's own tree. It is there rather than here because separating an
agent onto its own machine one day takes `<agent>/` and the contracts and
nothing else — a round left behind in `bridge/` would vanish at that moment.
The bridge writes it and the agent reads it, and only the bridge may write it,
so a delivery cannot be forged.

Nothing else. The bridge has no code of its own: it is these files, the
instructions in `CLAUDE.md`, and the contracts in `contracts/`.

## Where it stands, and what is next

One thread exists and the wire under it is checked rather than described: the
envelope, the ledger and the turn all have rules a program applies. What is
not yet done is the round trip itself. A plan has crossed from the simulation
side; a comparison needs a measured result on **each** side, and that waits on
runs neither agent has made.

Two things the bridge is supposed to do are still out of reach, and for
different reasons. Substituting a knowledge reference for a repeat round needs
the librarian answering this seat, which it has only just begun to. Comparing
two results needs those results.

The delivery path itself was declared on the day the first round stood waiting
forty minutes for it — the turn was set to an agent with no way to see the
round. That is why `inbox/` is in the receiving tree and not here.

For the current state, run the validator from the repository root rather than
trusting this paragraph; its last line names the tree it judged.

## The one idea worth having before reading anything else

Every gate the bridge applies has **three** answers, not two: it passed, it
failed, or the tables do not say. A failed gate becomes a refusal carrying the
numbers that refused it. A gate nobody can resolve **holds** the round and
gives the turn to a person — it does not guess, and it does not record an
impossibility that nobody established.

Most of this agent's design falls out of that distinction. `plan.md` §4.4.

## How "authors nothing" is enforced

The envelope carries no numbers of its own, so the markdown cannot restate the
values it carries. The answerability verdict is **derived** from the shared
vocabulary and the receiving side's capabilities table, so a card cannot claim
more than the tables say. The ledger records the source card as it stood in the
sender's own directory, so *the card that arrived is the card that was sent*
is something a program checks rather than something the bridge asserts.

All of it is check 8, and `plan.md` §8 lists what it holds.

## What it may not do

It has no instrument tools and no engine tools, and its settings deny writes to
any run directory: the bridge executes nothing, so it should not be able to.
Tier 0 throughout (§6). It never opens a round by itself — a person does, or a
plan being finished does (§4.4).

## Where to look

| | |
|---|---|
| `CLAUDE.md` | the standing orders for the session that writes rounds |
| `tasks/` | instructions from the manager seat, and the record of what was decided and why |
| `threads/` | the rounds themselves |
| `failures.jsonl` | tries that produced no card — the only place they exist |
| `plan.md` §4.4 | what this agent is, in full |
| `plan.md` §7.1 | why a round is a filename prefix and not a folder |
| `contracts/examples/` | one round written by hand, to read before writing one |

## How to see where it stands

Run the validator from the repository root. It reports what the bridge's rounds
satisfy, and its last line names the tree it judged — the working copy is
shared between sessions, so a bare run is nobody's commit and a failure in it
may belong to somebody else.

No count is written in this file. Counts written into prose here have been
wrong within the day, every time.

## One thing that is true of this agent and is not in the design

For most of its first days the bridge had **nothing to carry**: the agents on
either side had not produced a card yet. A courier with no parcel could have
been idle. Instead that is where the contract's gaps surfaced — wrapping a
round that did not exist yet, by hand, found a hash that voided an approval the
moment it was granted, a trigger nobody had defined, a filename convention that
two things shared, and an estimator that no card could carry.

Nothing in the design predicted that. It is worth knowing, because the same
thing is probably true of the next agent whose counterpart is unfinished: the
useful work while blocked is not waiting, it is trying to do the blocked thing
carefully enough to find out why it cannot be done.
