# 067 — publish the store version that holds task 066's entries

Written by `manager-librarian-scope-20261105-1` on 2026-11-09. You read this;
you do not edit it.

**For `librarian-scope-20261105-1`**, or whichever librarian seat the person
opens next. If you are not a librarian seat, take nothing from this card and
report up.

## GOAL

The microscope manager declared `trapped_particle_drag_offset` at `618f9e50`,
citing `piezo_x_ramp_is_a_staircase_of_position_targets_read_back`, which
task 066 entered at `38af895b`. The microscope agent plans `mic-20261109-001`
from its envelope, and the envelope copies only a published export. Neither
066 entry is in one yet.

## TASK

1. Publish: `export_snapshot.py`, then `safety_guides.py` and `wiki.py` in the
   same sitting. Commit the guides and pages with the publish, never after it.
2. Check that both 066 entries and the six gaps written in `devices.v0.json`
   are in `kb/exports/snapshot_microscope_agent.json`.
3. Run lint at the `publish` trigger only if task 065's tools exist by then.
   If they do not, say so and do not imitate them.

## CONTRACT

Publish only what is committed. Do not change any entry in this sitting: an
edit moves `kb_version` exactly as an addition does.

## CONSTRAINTS

Your `CLAUDE.md`. Dead ends go in `failures.jsonl` with `task: 067`.

## REPORT

Send to `manager-librarian-scope-20261105-1`, 4 lines at most:

- the publish commit and the `kb_version` it published;
- whether both 066 entries and the six gaps are in the microscope export;
- the guide and page counts the `--check` runs read afterwards;
- one sentence: what is not yet on disk.
