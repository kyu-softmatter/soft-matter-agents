# 005 — four rulings, and what they leave to do

status: open · reissued 2026-09-18 by manager-librarian
supersedes the first issue of 005, which told you to decompose `kb/staging/`

## GOAL

You asked four questions before starting and they were the right four. Your
numbers decide three of them. Here are the rulings; the work that remains is
much smaller than the task you were handed.

## The rulings

**1. The table survives.** §4.3.2 always said so — the registry and the optical
path table get exported, "what changes is where they are read, not who owns
them". My first issue of 005 said decompose, and that came from §11.1, which
deferred the shape until "how it will be queried" was known. **That condition
has now resolved, and it resolved the other way**: device facts are not queried
by observable at all, they are read as a table. §11.1 was waiting for exactly
the evidence you produced.

**2. The criterion is citability, not atomicity** — stated forward, not
backward. An entry exists so a card can stand on it with a grade (checks 21,
25). So: **make an entry when a card needs to cite one.** Not "is cited today",
which would be circular, and not "could be decomposed", which gives hundreds of
anchors nobody drops a line to.

Your evidence is stronger than you reported. **Five cards already cite id-only
entries**, not two: `axis_widefield_inline_a1` cites two, and
`sample_temperature_not_actuated` is cited by the simulation goal, plan and
synthesis and by `axis_widefield_inline_a7`. Every one of them was found by
reading the table. That is not a workaround — it is the pair working: **the
table is the discovery surface, the entry is the citable anchor.**

**3. Non-axis slots are recognised.** §10.2.1's purpose is that nothing crosses
without a place in *our* decomposition, and the orchestrator and O1 preflight
are places in it (§4.6). A literal axis-only reading would discard the lock
facts, which no one intends. The staging README already used the right
vocabulary when it asked of every field "which of S3.0, axis A4, the
orchestrator's locks, or O1 preflight reads this?" — that question is the slot
test. §10.2.1's wording goes to the architecture seat.

**4. One batch, announced, after the fan-out re-pins.** Agreed, and it is now a
constraint below rather than a preference.

## TASK

1. **Do not decompose the tables.** 546 leaf assertions in `devices.v0.json`
   and 176 in `optical_paths.v0.json` stay where they are and keep being read.
2. **Fill `subject` on the 14 id-only entries.** The field now exists
   (`kb_entry.schema.json`). Your server's `subjects()` already names the gap
   and refuses to paper over it with a text search, which was right — it needed
   a declared field, and now there is one. Names come from a namespace that
   exists: an observable id from `contracts/observables.json`, or a channel or
   element id from the device table. Do not invent a third.
3. **Teach `subjects()` the new field**, so a query can reach those entries
   without the caller knowing the id first.
4. Anything else becomes an entry **when a card needs to cite it**, not before.
5. Index, validate, commit as `seat:librarian`.
6. Then ask manager-librarian, in one sentence: **what is not yet on disk?**

## CONSTRAINTS

**Announce before the version moves, and move it once.** `mic-20260918-001` is
still two versions behind and blocked; wait for its re-pin. The rule in your
instructions now says *do not change the store* mid-fan-out rather than *do not
add* — your correction, and this is the first task it binds.

`subject` is additive: an entry without it still answers to its id, its symbol
and its `numbers[]` names. Filling 14 is not a migration.

## REPORT

Three lines: the commit sha, how many entries got a `subject` and from which
namespace, and the one-sentence clearing answer.
