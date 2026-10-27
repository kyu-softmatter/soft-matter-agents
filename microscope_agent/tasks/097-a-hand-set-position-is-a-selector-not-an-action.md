# 097 — a hand-set position is a selector, not an action

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-office-20261015-1`, the microscope execution seat**,
for the planning side in `microscope_agent/src/`. It can run alongside card
095, which is the runtime's side of the same rule. If you are not that seat,
take nothing from this card and report up.

## Why

Read **plan.md 15.1 item 10** (`efbd679a`), the bullets under "A selector is
a setting or a required state". Read off `plan_card.py` at `c4c2f869` and
plan `mic-20260920-001`:

- a condition whose element the registry names becomes an action
  `set_<parameter>` (around lines 640–652). So `nosepiece_position` and
  `intermediate_magnification` go out as `act_set_nosepiece_position` and
  `act_set_intermediate_magnification`, on devices software may not command;
- a rotation brings three bracketing actions, `act_release_pfs`,
  `act_retract_objective` and `act_reacquire_pfs` (around lines 590–655).
  Item 10 says the focus release and retract are the person's at the bench;
- the four selectors in `system_configuration.selectors` already carry the
  hand-set path elements as selectors. The nosepiece and magnification are
  the two that do not.

Once the runtime refuses any action on a device software may not command,
which it does today, this plan cannot run at all for those six actions.

## What to build

In `microscope_agent/src/plan_card.py`:

1. **A condition on an element software may not command becomes a selector
   in `system_configuration.selectors`, not an action.** Read which devices
   software may command from the snapshot or the runtime's published list
   the planner already reads. Do not copy the list into this file. If the
   planner reads no such list today, stop and report to this seat. The
   selector's `value` is a string in the device's own keying. For the
   nosepiece, that is the position read from the snapshot's turret row, as
   `selector_numbers()` already reads it. Its `selects` stays empty unless
   the store holds one quantity per setting.
2. **The number stays in `numbers[]`.** `nosepiece_position` is what the
   runtime keys the focus floor by, so the condition and the number remain,
   and only the action goes. The selector and the number must name the same
   position. A test holds them equal.
3. **The rotation's three bracketing actions are not emitted when the
   nosepiece is a selector.** The turret change, with the focus released
   and the objective retracted around it, is the person's at the bench
   before the run. The plan states that as a precondition the person meets
   at the bench, in the plan's existing fields. If no existing field can
   hold a bench step the person performs, stop and report the field to this
   seat. Do not put it in prose only.
4. **An element software may command keeps its action**, unchanged.
5. **Re-derive `mic-20260920-001`'s plan** with the change and commit the
   new revision as its own card, as the planner revises any plan. The old
   revision stays.

## Tests, each watched failing first

1. A goal naming `nosepiece_position` gives a plan with a `nosepiece`
   selector whose value equals the number's position as a string, and no
   `set_nosepiece_position` action.
2. The same for `intermediate_magnification`.
3. With the nosepiece a selector, no `pfs` or retract action is emitted, and
   the bench precondition is present.
4. An element on the allow-list still gets its `set_<parameter>` action.
5. The re-derived `mic-20260920-001` revision passes the validator with
   `0 failed`, on the tree the run names.
6. The existing suite is unchanged, apart from tests that asserted the six
   actions. Name each one you change and why.

## Boundaries

- Write `microscope_agent/src/`, its tests, and the new plan revision under
  `microscope_agent/questions/mic-20260920-001/` only. No `contracts/`, no
  `envelope/`, no `approvals/`, nothing in `microscope_runtime/`.
- If a schema field is needed, stop and report it to this seat. The schema
  is mine to change.
- Commit through `contracts/tools/seat_commit.py`, naming each path. Never
  `--no-verify`, `--amend` or force.

## What comes back

To this seat, 4 lines at most: the commit or commits; each test, watched
failing, then passing; the suite's counts; and any existing test you
changed, by name.
