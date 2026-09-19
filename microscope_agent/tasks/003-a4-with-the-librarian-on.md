# 003 — A4, and the first pass with the librarian on

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

## Why this is its own card

Task 001 commissions A2 through A6 and still stands. This card covers only the
first of them, because the first one is a different kind of thing: **it is the
first axis in this repository to be answered by the service instead of by
reading the files.**

§9.1's completion condition has never been met — one pass with the librarian
**on**, `kb_refs` and `kb_gaps` filled, `degraded` empty. Until 2026-09-19 it
could not be: `queries/log.jsonl` did not exist, so every card so far belongs
to the degraded path, whatever it says. Reading the files is not the service
answering (§0.3). A4 is the pass that can finally satisfy it, and the card
exists so that it is satisfied honestly rather than merely claimed.

001's ordering already puts A4 first, for a reason that still holds: the
device registry is the one table with real content, so A4 is the axis most
likely to return an interval rather than abstain.

## What is different from every card before it

**`degraded` must be empty, and empty must be true.** It is now checkable
against `queries/log.jsonl` (§0.3-4) — that is the whole point of the log.
So: if any question you needed answered went to the files instead of the
service, `degraded` names the librarian and says which question. An empty
`degraded` on a card whose questions are not in the log is the lie that field
was invented to prevent, and it is now a lie that can be caught.

**A gap is now a service answer, not a directory listing.** `kb_gaps` records
what you asked for and did not get. Before today `searched` named directories,
because that was all there was. Now it names the call: the tool, the
`observable`, and the `caller_id` that asked. Asked-and-absent and
nobody-checked are different claims (§4.3.1), and only one of them is now
available to you.

**Every `kb_ref` carries what the service returned** — the entry's own grade,
read from the entry rather than restated, and the `kb_version` that answered.
A grade you assert rather than receive is a different claim from one the store
gave you.

## The pin does not move

Ask at **`kbv-49feb73662b7`**. The store is at `kbv-67f9ad766d92` and that is
fine: the server returns the store as of the version you pin (`4033b4d`) and
stamps every answer with `answered_from`. This was verified today, not assumed
— the served bytes matched the pinned commit and differed from the working
copy, which is exactly right.

Do not re-pin to chase the store. A1 and A7 sit at `kbv-49feb73662b7`, check
33 wants siblings to agree, and this fan-out has already paid for one re-pin
whose target went stale in four minutes.

If some question genuinely cannot be answered at the pinned version, that is a
finding to send up — not a licence to re-pin.

## What A4 owns

Configuration suitability for `widefield_inline`: channels, read-back,
automatability, path exclusivity. Two consequences 001 already named, and they
still hold:

`optical_tweezers` and `laser_combiner` are `read_back: false`, and §4.6.6
rule 5 makes them manual, which makes an individual approval mandatory (§6.1).
**That consequence belongs in the card**, not only in your reasoning.

`automatable: full` on the DMD is true only on a core pinned to device
interface 71 — the registry carries `automatable_condition: core_requirement`
and says so. A plan screened on the bare field passes while the preflight that
opens the device fails. If A4 screens on `automatable`, it reads the condition
too.

## What holds

Every inequality the axis owns gets an entry: an interval, or an abstention
with `kind` and `reason`, and `missing` named when `kind` is `no_input`.
Silence is refused (§4.5.2.1); an interval with neither bound is that same
silence. An abstention with a reason is a correct outcome, not a failure —
A1 and A7 both abstained and both were right to.

An axis states a range and does not choose inside it. It does not read another
axis's output, and it does not read lessons (P16).

## The log is not yours to commit

The server writes `librarian_agent/queries/log.jsonl`. That path is the
librarian's boundary — check 41 refuses your commit if you touch it. **Commit
only `microscope_agent/`.** Say in your report that the log has new records,
and the librarian seat commits them.

## Done when

The A4 card is committed and `VALIDATED`, `python3 contracts/validate.py` ends
`0 failed`, dead ends are appended to `questions/<qid>/failures.jsonl`, and
`kb_refs`, `kb_gaps` and `degraded` each say something true about how the
answer was actually obtained.

Then one sentence up: whether `degraded` is empty, and whether that is the
first time it has honestly been so.

## Not this task

A2, A3, A5, A6 — they are 001's, they come after, and they will be easier once
this one has shown what a served card looks like.

**The `definition` in `goal.json`.** `d6999e5` moves an observable's
definition out of cards into the vocabulary; the bridge manager is
coordinating the window because the other affected cards belong to other
agents. Leave it; I will card it.
