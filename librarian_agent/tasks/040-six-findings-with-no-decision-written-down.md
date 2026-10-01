# 040 — six microscope findings with no decision written down

status: **open** · issued 2026-09-28 by
manager-librarian-kyuhwan-macbook-20260928-3, under the person's standing
instruction of 2026-09-24 that the day's microscope findings be harvested into
the store (recorded in 037), and announced to the person in this seat's window
before it was filed · filed 2026-09-29, once this seat's row was in the
registry (`9c9a930`); the six were re-derived at `54e4885` first, after a
context reset in this seat's window, and the list stood · ~~for
librarian-kyuhwan-macbook-20260928-3~~ · **readdressed 2026-09-30 to
librarian-kyuhwan-macbook-20260930-1** by
manager-librarian-kyuhwan-macbook-20260930-1, on the person's "응" ("yes")
in the manager's window: the 2026-09-28 fleet was archived on 2026-09-29 with
040 untouched. 039 is done and published (`a16a650`), so "after 039" is met.
**041 goes first**, because two live questions wait on it; publish this one
on its own afterwards, or once together with 041 if 041 has not published yet

## GOAL

Six items in `microscope_agent/findings/`, each `for_store: true` and
delivered to `librarian_agent`, have no decision written down anywhere this
seat could find. Each gets the decision every 037 item got: entered, held,
excluded or discarded, with the reason.

- **Four were never taken in.** Three were added to microscope-20260924-3's
  file at `d8570f1` (19:08 on 2026-09-24), after 037's intake had read it at
  `a5e7647`. The fourth is in microscope-20260924-6's file for 2026-09-25,
  which no librarian session has opened.
- **Two were read and their fate is not recorded.** They are in
  microscope-20260924-2's file, which 037 took in. `a14ec7a` accounts for -2's
  other person statements and other unmeasured items one by one in its
  message. These two are named there by neither id nor content, and appear in
  no entry, gap or `failures.jsonl` line. They may well have been excluded
  with the three that 037's state line calls "policy or session state", but
  nothing says so. Write down what happened to them, or decide it now.

This seat found all six while verifying 036 and 037. It matched every item
id against the store, `failures.jsonl`, the tasks and the librarian commit
messages, then read the messages for what the id match could not see.
**Re-derive the list before you trust it.** A match on ids finds an id, not
a claim. -2's forty self-reports look absent to it, and they are not absent:
`a14ec7a` entered them as ten entries by claim.

## TASK

Read under `plan.md` §7's `findings/` line: the findings file, and exactly
the paths an item cites, with `git show <commit>:<path>`. Nothing else of
`microscope_agent/`. The items name paths and no commit, so read at **the
findings file's last commit**. Every path they cite is already committed
there; this was checked at filing.

| item | file, read at | kind | cites |
|---|---|---|---|
| `mm_load_hung_after_nis_force_kill` | `microscope-20260924-3-20260924.json` at `0ecf94b` | document_fact | `runs/run-20260924-009/log.json`; its `fact` and `how` also rest on the logs of `run-20260924-010` (committed at `08de0a7`) and `run-20260924-008` |
| `blanking_lines_free_right_after_nis_kill` | same | document_fact | `runs/run-20260924-009/log.json` |
| `csuw1_reports_no_disk_speed_here` | same | self_report | `run-20260924-008`, event 4 (events 4 to 10 carry the seven devices) |
| `optical_tweezers_work_with_40x_60x_100x` | `microscope-20260924-6-20260925.json` at `921537b` | person_statement | the message of `dee04b3`, the commit that adds the item, which quotes the person |
| `person_piezo_axis_channels` | `microscope-20260924-2-20260924.json` at `a0fda99` | person_statement | `microscope_agent/tasks/035-piezo-then-confocal-laser-then-tweezers.md` at `be5a848`, "What the person stated" |
| `unmeasured_piezo_position_tolerance` | same | unmeasured | `microscope_agent/src/piezo_live_checklist.md`, step 3b |

The last row cites a file in `src/`. §7's line allows it only because an item
cites it, and only at the named commit. Read that one path at that commit and
nothing next to it.

## CONTRACT

- **Two of the four new ones meet what the store already holds from the
  prior project**, and the items say so themselves.
  - `csuw1_reports_no_disk_speed_here` is
    `csuw1_disk_speed_is_not_exposed_in_micromanager` observed on this
    computer.
  - `blanking_lines_free_right_after_nis_kill` confirms here that the kill
    frees the port. The store holds that only by implication, in
    `lunf_blanking_port_is_held_by_one_program` (held while the program runs)
    and `lunf_fiber_shutter_survives_a_controller_kill` (after a kill, a line
    driven from other software still emitted).

  Where it is the same claim observed here, the new entry is the one that can
  be E1 and points back with `supersedes` (`plan.md` §10.3 rule 1). Where the
  conditions differ (another configuration, another computer), it is its own
  entry and names the other in its text. Edit no old entry. Neither
  observation tests `lunf_killed_writer_may_leave_a_line_open`, because the
  writes were not read back.
- **`mm_load_hung_after_nis_force_kill` says the prior project reported the
  opposite**: a configuration of the same shape loaded after a force-kill on
  2026-09-07. No entry holds that report (checked at filing), so there is
  nothing to name in `conflict_with`. The note is the microscope seat's word
  about the prior project. If the prior report is wanted, it comes in through
  §10.2.1 like any other prior item, and not from the note.
- **A device's report of itself may enter at E1**, citing the run log as
  `measured:<run_id>` with the event, as 037's did (§11-21 as narrowed at
  `20a688b`, check 85). A registered observable's value may not.
- **Claim no more than the item does.** The blanking writes were not read back
  and no light was produced, so what the lines did is not established. An entry
  says the same. Nothing here is a safety statement or a limit.
- **The person's words are the person's, and only those.** Enter what
  `dee04b3` quotes. The item's own note says what the person did not state: why
  the other objectives do not trap, and which 40x objective is meant. Leave both
  open. Do not fill them from what trapping needs. That reason is general
  knowledge and not the person's statement. For the piezo channels, the
  controller's own axis labels are already entered at E1 from `run-20260924-004`.
  Say whether the person's statement agrees with them. Do not resolve a
  disagreement.
- **An absent tolerance is not knowledge.** Whether a position tolerance
  should exist is the person's, because it is policy. What the store could hold
  is only that none has been set. If that is worth a gap, file it as one. If it
  is not, exclude it and say so. **Either way, the checklist already names
  it:** step 3b at `a0fda99` says *no entry — gap `piezo_position_tolerance`*.
  No gap by that name, or by any name holding `position_tolerance`, exists
  anywhere in `librarian_agent/` at `54e4885` (checked at filing). So filing
  it under that name gives the checklist's reference something to point at.
  Excluding it leaves the checklist naming a gap that will not exist, and the
  report says so, so that the microscope seat can hear it through its
  manager.

## CONSTRAINTS

- **After 039.** These move `kb_version`. If 039 has not published yet,
  publish once for both; otherwise publish this on its own. Either way, check
  the query log for in-flight pins first and confirm with the simulation and
  microscope execution sessions that nothing is in flight.
- Name files, never `librarian_agent/`. Run `git var GIT_COMMITTER_IDENT`
  first and commit with the environment-variable form under your own seat.
  Write the message to a file and use `git commit -F`.
- Dead ends go in `librarian_agent/failures.jsonl` naming `task: 040`.

## REPORT

Per item: entered (entry id and grade, and what it supersedes or names),
held, excluded or discarded, with the reason. The commit, the publish, and the
one sentence: what is not yet on disk.
