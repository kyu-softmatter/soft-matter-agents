# 044 — what the autofocus merge established, kept as knowledge

status: closed · **verified on disk 2026-10-07** by manager-librarian-20261007-1. Entered at `c3e1c84` by librarian-20261004-1 and published at `6018bd1`, `kbv-5c6e29866619`. Three new entries: `csuw1_shutter_state_reads_a_label` and `dia_lamp_reports_state_and_intensity`, both E1 from `run-20260924-008` and recorded as settings read back, not as quantities, and `filter_turret_shutters_close_at_state_0`, E5, a recollection with no read-back behind it. Two candidates were already in the store. The two decisions were ruled out because `plan.md` carries them and nothing cites them from the store. The mock results were ruled out because no source prefix describes them honestly, and both findings files say `for_store: false`. No entry is a limit: the turret entry says in its own conditions that the exemption to write the value is the person's and not the entry's. · issued 2026-10-07 by manager-librarian-20261007-1, on
architecture-20261003-1's request of the same day. That request records the
person asking, in architecture's own window, that the librarian distil and
keep what this week's merge learned · **for librarian-20261004-1**, which is
registered, has the 17 focus definitions behind it, and is idle

## GOAL

The dino-autofocus merge is on `main`: `b346c02..5b24147`, 82 commits. It
established facts about the instrument and about the focus method. Today they
live only in commit messages, cards 054–063 and one findings file. A card
that needs one of them has nothing to cite, and the next session learns it
again. Put what is knowledge into the store, graded from its source. **The
store is not a code history**: what was built is `plan.md` 14's business, and
a fact here is a claim about the instrument or the method that a plan could
lean on.

## TASK

Read the range (`git log b346c02..5b24147`), the cards
`microscope_agent/tasks/054`–`063`, and
`microscope_agent/findings/card061-e2e-run-20261006-e2e061b.json`. Rule
every candidate before writing anything. Re-derive the list; this one is
architecture's, and it is a starting point.

**Device self-reports**, under `plan.md` 11-21 condition 4: a device's report
of itself enters citing the run that read it, as an observation by this
system.

- Aura off is `State 0`, read off `getDevicePropertyNames` in
  `run-20260924-002`.
- DiaLamp `State` and `Intensity`.
- `CSUW1-Shutter`'s `State` reads a label (`"Open"` in `run-20260924-008`),
  and no closed value is recorded.
- The tweezers report nothing back.

**The person's statements**:

- The two filter-turret shutters close at `State 0` (2026-10-04). Find where
  it is written and grade it by what that record shows: read, recalled, or
  decided.

**The person's decisions that bind the method**:

- The focus upper limit is written and never derived.
- Live view is a preparatory run, and excitation is a separate approval.

A decision is design and lives in `plan.md`. It is not knowledge about the
world. Enter one only if a plan or card would need to cite it from the
store, and only as what it is: the person decided this, here, on this date.
Never enter it as a fact about the instrument. If `plan.md` already carries
it and nothing would cite it from the store, it does not enter. Say which
way you ruled and why.

**Mock-only results**:

- Card 061's end-to-end stop.
- Card 063 if it has landed.
- The abort that now stops a streaming camera sequence within the next frame
  (`8b4b78c`).

These are facts about the software on mock, never about the instrument, and
**never graded as measurements**. If one enters, its source names the run id
and the findings file with its sha256, and the entry says "mock" where a
reader cannot miss it. If no source prefix describes a mock result honestly,
it does not enter, and the report says so. Inventing a fit would be worse
than leaving it out.

**Check the store before each entry.** Much of this may already be there:
`aura_master_state_0_keeps_green_dark`, `tweez300_reports_nothing_back`,
`csuw1_shutter_gates_confocal_excitation`,
`filter_turret_1_state_0_blocked_the_confocal_path` and others. A second
entry asserting one claim was withdrawn as a duplicate on 2026-10-01
(`1c66f91`). Where the store already holds the claim, extend that entry's
evidence or leave it, and name it in the report.

## CONTRACT

- `plan.md` 10.3: nothing from dino-autofocus enters as a number. A
  dino-autofocus value is named by its card or file and read there.
- 11-21 condition 4 for self-reports. `kb_entry.schema.json` for shape.
- Every entry is graded from its source, and no number enters without one.
- **No safety limit.** A closed-shutter value, a lamp state or a focus limit
  is a fact about what a device reports. It never becomes a limit, and the
  envelope stays the person's.

## CONSTRAINTS

- Write only in `librarian_agent/`. Claim `kb/entries/`, `kb/index.json`,
  `failures.jsonl` and `queries/log.jsonl` by message with
  librarian-20261007-1 before writing. It holds 043 and will write the same
  paths after the 2026-10-08 bench.
- This moves `kb_version`: run the full publish steps, guides included, after
  checking the query log for in-flight pins.
- Commit with your own row's `GIT_COMMITTER_*`, `git commit -F <file> --
  <paths>`. The hooks are installed now, so a held `.git/index.lock` is
  usually another gate running; wait. Validate with the uv form. Push
  `feature/autofocus-ui` with `-c credential.helper=manager`.
- Dead ends go in `librarian_agent/failures.jsonl` naming `task: 044`.

## REPORT

Five lines, as architecture asked: the entries added (ids), the candidates
ruled out and why in one phrase each, the entries already present that
covered a candidate, the commit and the publish's `kb_version`, and one
sentence on what is still not on disk.
