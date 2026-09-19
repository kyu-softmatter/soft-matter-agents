# 002 — re-pin the fan-out to the store that exists

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

**Revised 2026-09-18.** The first version of this card named
`kbv-ec984bc852e7` as the target and was wrong by four minutes: `9baf01d`
moved the store again before the card was committed, and I did not re-read the
index between writing and committing. The target below is checked, and the
last instruction in the task exists so the same gap does not catch you.

## Where this picks up

This fan-out is two axes of seven in, pinned to `kbv-9bc3910f1886`. The store
has moved **twice** since, and is now at **`kbv-49feb73662b7`**:

- `51c0e93` re-filed `tau_d` — `dimensionless_group` to `derived_quantity`,
  gaining `unit: "s"`.
- `9baf01d` re-sourced `water_viscosity_293k` — `spec:src_water_properties`
  to `literature:src_water_properties`, because `literature:` now exists and a
  textbook is not a vendor specification. **The grade does not move: E3 both
  sides.**

Going back is not available. Neither old version is on disk, and the MCP
server refuses a stale pin by design
(`librarian_agent/src/mcp_server.py:276`), so the remaining five axes could
only run degraded — and §9.1's completion condition is one pass with the
librarian **on**. **The pin moves forward.** That is my decision; the reason is
written here rather than carried in a message, so you can check it.

## Why moving is cheap, and the two places it is not

I checked both hops rather than taking either on report. `entry_count` is 25 at
all three versions: **no entry was added and none was removed across the whole
move.** So every `kb_gap` in this fan-out survives it — a gap claims *absent at
this version*, and nothing became present.

The refs need more care than the first version of this card claimed. This
fan-out cites five entries: `csuw1_disk_position_states` and
`csuw1_disk_speed_exposure_constraint` (a1), `water_viscosity_293k`,
`lab_ambient_temperature` and `sample_temperature_not_actuated` (a7). **One of
the five did change** — `water_viscosity_293k`, in the second hop.

It still carries across, for a reason you should verify rather than accept. A
`kb_ref` in these cards records `entry_id`, `grade`, `kb_version` and `claim`.
What changed in the entry is its `source` prefix, which is none of those: the
value, the validity window and the grade are untouched, so the `claim` a7
quotes and the `E3` it records are both still what the entry says. **Open the
entry and confirm that before you move its pin.** If the grade or the claim has
moved, stop and say so — that is not a re-pin.

The other place is one line. `goal.json` `kb_gaps[0].nearest[0]` names `tau_d`
— the entry that changed in the first hop — as the near-miss for
`tracer_radius`, at `overlap: "unconstrained"`. That judgement was made against
an entry filed as a dimensionless group with no unit. It is now a
`derived_quantity` in seconds over `bead_diameter**2/diffusivity`, and
`bead_diameter` is a length. **Re-read the near-miss against the current entry
and record what the re-read says**, rather than carrying the old verdict
across. If the answer moves, move it: a near-miss that reads differently once
the entry is correct is a finding, not a failure of this task.

## The task

1. Move every `kb_version` under
   `microscope_agent/questions/mic-20260918-001/` from `kbv-9bc3910f1886` to
   `kbv-49feb73662b7` — `a1`, `a7`, `configs.json`, and the gap in `goal.json`.
2. Confirm `water_viscosity_293k`'s grade and claim against the current entry
   before moving a7's ref, as above.
3. Re-read the `tau_d` near-miss as above, and leave it correct.
4. While you are on that field, its value word becomes `no_overlap`. The
   architecture seat settled the rename in `b8f7f15` and `408a973` widened the
   enum so both words are accepted — so this is not urgent by itself and is
   here only because it is the same line of the same file. `goal.json` is the
   last holder of the old word, named as the holder in
   `contracts/schemas/common.schema.json`.
5. **Re-read `librarian_agent/kb/index.json` immediately before you commit.**
   If `kb_version` is no longer `kbv-49feb73662b7`, the store moved under you
   as it moved under this card: do not silently re-target. Stop, and say which
   version it is now and what the new delta is.

Nothing else moves. No interval, no abstention, no `kb_ref` added or dropped.

## What holds

**A re-pin is a claim.** After this commit those cards say they were answered
against `kbv-49feb73662b7`. That is true of the gaps by the count above, true
of four refs because their entries are untouched, and true of the fifth and of
the near-miss only if you do the two readings. Do not move those pins without
them.

**Nothing outside this directory.** The simulation fan-out is stale too and its
cards do cite `tau_d` directly. Another seat's card, another seat's judgement.

## Done when

Every pin in the directory reads `kbv-49feb73662b7`, `python3
contracts/validate.py` ends `0 failed` with the five check-25 PENDING lines for
this directory gone, and one commit as `seat:microscope`.

Then one sentence up: re-pinned, and whether either reading changed anything.

## Not this task

**The KB snapshot.** `9baf01d` published
`librarian_agent/kb/exports/snapshot_microscope_agent.json` at this same
version, and this agent's `envelope/` is empty — it has never held one. Copying
it in is required before preflight (P0 rule 2, §4.3.2) and it is the next card,
not this one.

**A2 to A6** — task 001, still open. The five should be written against a store
the librarian will actually serve, which is why this card comes first.

**Removing `unconstrained` from the enum.** That is in `contracts/`, it is a
manager seat's, and it comes after your commit.
