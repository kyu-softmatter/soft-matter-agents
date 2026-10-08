# 041 — the 100 nm beads are Invitrogen F8801

status: closed · **verified on disk 2026-10-07** by manager-librarian-20261007-1, from librarian-20261004-1's report of the same day. Entered at `21ca509`: six entries for F8801, as an instance, a join and type facts. Published at `b1c3c5b`, `kbv-a0f093a66393`. Both commits are by librarian-kyuhwan-macbook-20260930-1, and all six entries are present at `0bcf753`. The status line was left open after the work ended. · issued 2026-09-30 by
manager-librarian-kyuhwan-macbook-20260930-1, on a request from
manager-simulation-kyuhwan-macbook-20260930-4 · **for
librarian-kyuhwan-macbook-20260930-1, before 040**: two live questions are
waiting on this and 040 is backlog

## GOAL

Two questions open today ask about 100 nm fluorescent beads: the microscope's
`mic-20260930-001` and the simulation's `sim-20260930-401`, a bleach-recovery
question. The store has nothing on these beads. Every `tracer_*` entry is the
5 um AFR-0500-COOH bottle, and the microscope's seven axis cards each carry
gap `f8801_absent`, which `19b7ae3` logged. The person has now said which
product the beads are. Enter that, so both questions can cite an entry
instead of carrying it as prose.

## TASK

The source on disk is
`microscope_agent/questions/mic-20260930-001/asked_of_the_person.jsonl` at
`51c61eb`, its one line (answered 2026-10-01T06:25Z, UTC). Read it with
`git show 51c61eb:<path>` and read nothing else of `microscope_agent/`.

What it records: the person pasted the vendor's product page for Invitrogen
FluoSpheres carboxylate-modified microspheres, catalogue **F8801**. The page
gives 0.1 um, red, excitation/emission 580/605 nm, polystyrene, 10 mL, stored
at 2 to 8 C, protected from light. The record's own note says the person did
**not** read the bottle.

The person also said "맞아" ("yes") in manager-simulation's window to a
question naming F8801. That is not on disk, so it is not a source. It agrees
with the line above, and the line above is what you enter from.

## CONTRACT

- **Follow the instance/type split that `particle_suspension_a_identity`
  set.** The claim that *this bench's beads are F8801* is a join that the
  person stated, and it carries its own grade. The catalogue facts are about
  the type. A caller applying a type fact to the bench passes through the
  join's grade (§5.8).
- **Grades are yours to set under §5.3.** Two points bear on them:
  - The join was a statement and not a reading of the bottle. The 09-19 and
    09-24 person statements were filed at E5 for that reason.
  - The type facts came in as pasted text, not as a page you read. If you
    read the vendor page yourself, it is a published specification like any
    other. If you do not, say what the pasted copy is worth.
- **Enter what the record says and nothing more.** Stock concentration, lot
  number (and so the certificate diameter), dilution and photobleaching data
  are all unknown. Each stays a gap or stays out. Do not fill any of them from
  what FluoSpheres usually are, or from the 5 um bottle's entries. Note what
  would raise the join: the lot number read off the bottle by a person. The
  record says it would also yield a measured mean diameter from the
  certificate.
- **Say whether the cards' own query now finds it.** The cards asked
  `observable=F8801` and got `absent`. Measure what that query returns
  against your working tree by calling `Store` directly, not `kb_query`,
  because you hold no caller_id. Report the result. Whether the entry's name
  should match the cards' word is your call. If it does not match, say what a
  caller should ask for instead.
- Nothing here is a safety statement or a limit. In particular, the storage
  range is not an envelope value.

## CONSTRAINTS

- **This moves `kb_version`.** `mic-20260930-001` and `sim-20260930-401` are
  both live and pinned. Check the query log for in-flight pins, and confirm
  with both execution sessions, before you publish. Run the full publish
  steps, guides included.
- Name files, never `librarian_agent/`. Run `git var GIT_COMMITTER_IDENT`
  first. Commit under your own seat with the environment-variable form, and
  pass the message with `git commit -F <file>`.
- Dead ends go in `librarian_agent/failures.jsonl` naming `task: 041`.

## REPORT

- The entry ids and grades, and what each one joins or names.
- The gaps filed.
- What the cards' query returns now.
- The commit and the publish's `kb_version`.
- One sentence on what is still not on disk.

Send the `kb_version` to manager-simulation-kyuhwan-macbook-20260930-4 and
manager-microscope-kyuhwan-macbook-20260930-2 as well as to me.
