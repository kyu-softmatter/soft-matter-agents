# plan plan-mic-20260920-001-r2

*Generated from plan-mic-20260920-001-r2.json. Editing this file changes nothing (P3, 5.6).*

- question: `mic-20260920-001`  ·  thread `solo-mic-20260920-001`  ·  revision 2  ·  status **VALIDATED**
- observable: `tracer_brightness`  ·  intent: explore
- configuration: `widefield_inline`

## Purpose

characterize

## Numbers

| name | value | unit | grade | source |
|---|---|---|---|---|
| `exposure_time` | 0.1 | s | E5 | `assumed:a_operating_point` |
| `illumination_line_intensity_permille` | 100 | 1 | E5 | `assumed:a_operating_point` |
| `nosepiece_position` | 5 | count | E5 | `assumed:a_operating_point` |
| `intermediate_magnification` | 1 | 1 | E5 | `assumed:a_operating_point` |
| `record_length` | 60 | s | E5 | `assumed:a_operating_point` |
| `brightness_window` | 6 | s | E5 | `assumed:a_brightness_window` |
| `bleach_window` | 60 | s | E5 | `assumed:a_bleach_window` |
| `frame_count` | 600 | 1 | E5 | `computed:record_length_over_exposure_time` |

## Conditions

- `exposure_time` = `numbers[exposure_time]`
- `illumination_line_intensity_permille` = `numbers[illumination_line_intensity_permille]`
- `nosepiece_position` = `numbers[nosepiece_position]` on `nosepiece`
- `intermediate_magnification` = `numbers[intermediate_magnification]` on `intermediate_magnification`
- `record_length` = `numbers[record_length]`
- `brightness_window` = `numbers[brightness_window]`
- `bleach_window` = `numbers[bleach_window]`

## Actions

- **act_release_pfs** `disable` on `pfs` (tier 1, **irreversible**)
- **act_retract_objective** `retract` on `z_drive` (tier 1, reversible)
- **act_set_nosepiece_position** `set_nosepiece_position` on `nosepiece` (tier 1, reversible)
- **act_set_intermediate_magnification** `set_intermediate_magnification` on `intermediate_magnification` (tier 1, reversible)
- **act_reacquire_pfs** `enable` on `pfs` (tier 1, **irreversible**)
- **act_acquire** `acquire_series` on `camera_red` (tier 1, reversible)

## Stop criteria

- **sc_frame_count**: the acquisition stops at 600 frames, which is the planned end and not a guard. It counts FRAMES and not seconds on purpose: an elapsed time accumulated a step at a time lands a hair off the boundary and reports a finished run as unfinished, and the direction of the error moves with the exposure. A frame count is an integer and compares exactly. No tolerance is added -- the limit came from the person and an operator that widens it is changing an approved number (`frames_acquired` >= `numbers[frame_count]`)

## Success criteria

- **ok_tracer_brightness**: tracer_brightness is placed within 1 decade (`tracer_brightness_decades_resolved` >= `targets[tracer_brightness]`, a decision and not a graded value)
- **ok_bleaching_rate**: bleaching_rate is placed within 1 decade (`bleaching_rate_decades_resolved` >= `targets[bleaching_rate]`, a decision and not a graded value)

## Open risks

- THE RETRACT CARRIES NO TARGET HEIGHT. act_retract_objective sends the verb and no distance, because the store's claim about this axis is a DIRECTION at E3 -- smaller Z is retracted -- and nothing says how far. The one number that would bear on it, the working height above the coverslip, is an open debt on the person's list. So the device's own escape position answers the question and this plan cannot state what clearance that leaves: `objective_clearance` is not on this card, which is why the operator's comparison against objective_clearance_min records `compared: null` rather than a pass. What stands in for the number is the READ-BACK -- stand_ti2e answers, so the interlock requires the retract verified and not merely issued, and the rotation does not proceed on an assumption. Inventing a height instead would put a model-made number in a safety path, which P2 admits nowhere.
- RE-ACQUIRING PFS IS NOT RESTORING THE LOCK IT DROPPED. act_reacquire_pfs takes a new lock wherever focus is after the rotation and the retract, which is why both PFS actions are `reversible: false`. No offset is commanded: pfs_offset_sign_unmeasured is open and the store calls it the one remaining direction on a collision device that has never been measured, adding that a direction written into a configuration without being measured reads as verified. Release and re-acquire need no sign; an offset does, and it waits for the bench.
- The detector is camera_red, selected by setting csuw1_port to 'empty'. That is the person's DECISION and not a bound any axis returned -- the store's chain to this arm ends at an E5 recall carrying the word `probably`, and the store declines to promote it. THIS RUN ADJUDICATES IT: if no particles appear on this arm, the recalled emission-wheel-to-camera mapping is inverted, and that is a RESULT rather than a failure -- the result card carries the correction to the librarian. It costs nothing to find out this way, because bare particles are not the mount and the one mount is not spent. The reading that would have settled it beforehand is one visit to the emission wheel, which also closes light_path_port and filter_turret_1; it is on card 018 and comes before the measurement this run unblocks, not before this run.

