# 005 — four rulings, and what they leave to do

status: closed · reissued 2026-09-18 by manager-librarian · **closed 2026-09-19** (closing commit not recorded here)
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
2. **Fill `subject` on the 14 id-only entries.** The field exists and its
   shape changed after your second message: each subject **names its registry**,
   `{"kind": ..., "id": ...}`, not a bare string. A free list would let two
   entries call one thing by different words and make matching a coincidence —
   your point, and you caught it before anything was filled.

   Four kinds. `device` resolves against the device table's channel ids,
   element ids **and retired row ids** — a fact about hardware that was taken
   out is exactly the fact someone comes looking for later, which is your
   `temperature_stage` case. `configuration` against the optical path table.
   `observable` against `contracts/observables.json`. **`quantity` against the
   names actually used in `numbers[]`** — that is your option (ii), chosen
   because it needs no new artefact and a typo still fails, and it is labelled
   in the schema as the weakest of the four so nobody reads it as a declared
   namespace.
3. **Teach `subjects()` the new field**, so a query can reach those entries
   without the caller knowing the id first.
4. Anything else becomes an entry **when a card needs to cite it**, not before.
5. Index, validate, commit as `seat:librarian`.
6. Then ask manager-librarian, in one sentence: **what is not yet on disk?**

## CONSTRAINTS

**Announce before the version moves, and move it once. Wait for the fan-out to
CLOSE, not to re-pin.** I wrote "after the re-pin" and you read it by purpose
instead: `mic-20260918-001` has re-pinned, and it is still open at 2 axes of 7
with no plan and no synthesis, so moving now would make that seat do the same
repair twice within the hour. You were right, and the wording is corrected here
rather than left for the next person to re-derive — the same reading you applied
to *add* versus *change* this morning. The rule in your
instructions now says *do not change the store* mid-fan-out rather than *do not
add* — your correction, and this is the first task it binds.

`subject` is additive and **cannot be required yet** — expand, migrate,
contract, the same shape as `no_overlap`. An entry without it still answers to
its id, its symbol and its `numbers[]` names.

**The field is worth little until a check resolves every subject**, and that
check is not written. It is a check, so it needs the architecture seat to
declare it in §8 before this seat implements it, and several §8 items are
already queued there. Said plainly rather than implied: filling `subject` now
is useful and unverified, and the verification is the next thing, not a thing
already done.

**And the two decisions are one decision.** The registry a `device` subject
resolves against **is the staging table**. Ruling 1 keeps the table, so this
works; a later decision to dissolve it would silently remove what `subject`
checks against. Whoever revisits ruling 1 has to revisit this in the same
breath.

**Not now: `identifiers` values as query handles.** It would find `Kinetix 22`
and `MRD70040`, which is what a person actually asks, but it also makes
`fitted_slot: "1"` findable by `"1"`, which is noise rather than a handle. The
rule that separates them — `part_number`, `model`, `product`, `lot` are names;
`position`, `slot` are indices — is `identifiers` semantics and therefore mine.
Wait for it; no consumer is querying yet.

## REPORT

Three lines: the commit sha, how many entries got a `subject` and from which
namespace, and the one-sentence clearing answer.
