# 091 — the software-motion check finds each name's label in the snapshot

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-office-20261017-1`, the runtime seat.** It comes
after the cards already queued (086's remaining parts with 084 and 085,
089, 090), unless the runtime holder, architecture-office-20261017-1, moves
it. If you are not that seat, take nothing from this card and report up.

## Why

Read **plan.md 15.1 item 9** (`fb1f828a`). Your run of card 086 at
`f42fa1e8` found it:

- `check_software_motion` asks `micromanager.refusal()` with the names a
  command reaches, and the allow-list is keyed by Micro-Manager device
  labels (`Aura`, `Kinetix_red`, `DiaLamp`, `Core`);
- a plan names the registry's channels and elements (`camera_red`,
  `dia_lamp`, `widefield_source_a`), which are the store's own names and
  never labels.

So every plan outside the piezo, trap-step and focus-search exemptions is
refused as naming an unknown device, on mock as on the instrument.

**The label is the librarian's.** manager-librarian cards how a registry row
carries it, as a field or through the entry the row cites. That form is not
settled yet, so this card reads it through one function whose body follows
the librarian's form once it lands.

## What to build

In `microscope_runtime/src/orchestrator.py`:

1. **One lookup, from the registry the orchestrator already loaded.** A
   function that returns a registry name's Micro-Manager label, or None when
   the registry does not carry one.
   - It reads only what `load_registry` read: the snapshot first, then the
     export, then staging, as `REGISTRY_LOOKUP` orders them.
   - No second copy of the mapping: no table in `src/`, nothing beside
     `LIGHT_SOURCES`, and no label taken from a plan.
   - **The form is fixed** (librarian card 061, `2621655c`): a registry row
     carries `"mm_label": {"label": "<exact Micro-Manager label>",
     "entry_ref": "<entry id>"}`. The grade is the cited entry's, read from
     the same snapshot. Each label sits on at most one row. A row with no
     `mm_label` has no label. The field is not in the snapshot yet, so build
     against a test registry in a temp folder that carries it, and read the
     field name in one place.
   - **`orchestrator.CAMERA_DEVICES` goes.** It was added at `00c00824`
     (card 084) as a stopgap, because the registry carried no labels. It is
     the second copy this card forbids. The camera tap and the operator's
     camera lookup both read through the new function. A camera with no
     label taps nothing and says why. Test 6 finds it if it stays.
   - **The lookup returns the label with its `entry_ref`, the entry's grade
     and the configuration digest the entry carries.** It decides nothing
     from them; the check in item 2 does. The digest field is manager-librarian's
     to add to card 061's form (plan.md 15.1 item 9 at `344d115a`). Read it in
     one place, and build against a test registry that carries it.
2. **The check resolves before it asks.** For each name a command reaches
   (the channel, the element if named, and each device under
   `params.settings`), `check_software_motion` asks `refusal()`:
   - **with the name as written, as today**, so a plan that writes `ZDrive`
     still fails as a plan commanding the focus drive;
   - **and with the label the lookup gives**, when the name is a registry
     name;
   - a name is allowed only when neither ask refuses it and it reaches a
     label `SOFTWARE_MAY_COMMAND` holds. A registry name the lookup gives
     no label for is refused, and **the refusal names the missing label**:
     "`<name>` has no Micro-Manager label in the registry (`<source>`)".
     That is today's refusal, with its reason.
   - **A label lets software command its device only when this system read
     it here, under the configuration that is loaded** (plan.md 15.1 item 9
     at `344d115a`). A label the lookup gives is used only when both hold;
     otherwise the name is refused and the refusal says which failed:
     - **the cited entry is E1.** E3 (the prior project's configuration, or
       a person's reading off the property browser) commands nothing. One
       grade for every allow-listed device, with no split by moving or
       emitting;
     - **the entry's configuration digest equals the sha256 of the approved
       original** that `mm_config_gate.check` returns for this run (card
       069), not the derived copy that is loaded. File names are never
       compared. An entry with no digest refuses, as "names its
       configuration only in prose".
     - **On mock**, no file is loaded, so the test gives the mock the digest
       it stands for, the way a test gives a selector its position. With
       none given, every label-resolved name refuses. Put that digest
       wherever a test sets a selector's position, and nowhere a plan can
       reach.
   - `entry_ref`, grade and digest for each name resolved go in the
     `software_motion_checked` or `software_motion_refused` event, along
     with the loaded original's sha256 they were compared against.
   - Every refusal is still collected, and the whole plan is still refused
     before the first command.
3. **The registry's source is written with forward slashes.** The refusal in
   item 2 names the registry file, and the run log's `registry_source`
   names the same file. Today, on Windows, it reads
   `microscope_agent\envelope\snapshot.json` (you flagged this at
   `f977c927`). Write both repo-relative with `as_posix()`, the way
   `plan_path` is written. Records already written keep what they say.
4. **`widefield_source_a` gets no label from this card.** If a test
   registry gives it one, that is the test's. The real registry gives it
   none while `lapp_branch_assignment` is open, so a plan on the Aura stays
   refused, now naming the missing label.

## Not in this card

- **The run that makes any label pass on the instrument** is card 092.
  Today the store's E1 labels were read under
  `single_cam_red_noDMD_nocom10.cfg`, and the approved file is
  `DMD_dualcam_LUNF.cfg`, so on the instrument this card refuses every
  label-resolved name. That refusal is correct.

- **The settings derivation** (15.1 item 9's second gap). Once a label
  resolves, the check judges the right device, but `derive_commands` still
  produces no `params.settings`, so a planned run can pass and verify
  nothing. A test here that runs a plan on mock shows the check passing and
  the apply happening. It does not claim a verified apply. That is the next
  card, and it returns to design if it needs one.
- **The nosepiece on mock.** It reports no position until a test sets one,
  and the objective interlock refusing on that is correct (15.1 item 9). A
  test that needs it to pass sets a position with `set_element_by_hand`.

## Tests, each watched failing first

1. With a test registry giving `camera_red` the label `Kinetix_red` and
   `dia_lamp` the label `DiaLamp`, a mock plan on those two passes the check
   and dispatches. Without the lookup, the same plan is refused.
2. A registry name with no label is refused before any command, and the
   refusal names the missing label and the registry file it read.
3. A plan writing `ZDrive`, or any refused label directly, is refused as
   today, with the same text.
4. A registry name whose label is a refused device (a test registry mapping
   some name to `ZDrive`, or to a `NAMED_REFUSALS` device) is refused with
   that device's refusal. The lookup opens nothing the allow-list closes.
5. With the real registry, a plan on `widefield_source_a` is refused,
   naming the missing label.
6. Nothing under `src/` holds a label string for a registry name. A test
   greps `src/` for each `SOFTWARE_MAY_COMMAND` key outside `micromanager.py`
   and the existing `LIGHT_SOURCES` abort pairing, and finds none.
7. The existing suite is unchanged.
8. A run log's `registry_source`, and the source a missing-label refusal
   names, carry no backslash on Windows.
9. With `CAMERA_DEVICES` gone, card 084's per-camera tap tests still pass
   against a test registry whose two camera rows carry `mm_label`. With
   the label removed from one row, that camera's tap answers with no frame
   and names the missing label.
10. Every resolved name's `entry_ref`, grade and digest appear in the run's
    events, with the sha256 they were compared against.
11. A test registry row whose entry is E3 refuses its name, the refusal
    naming the grade. The same row cited to an E1 entry passes.
12. An E1 entry whose digest differs from the given one refuses, naming
    both digests. An E1 entry with no digest refuses, naming the missing
    digest. A mock given no digest refuses every label-resolved name.
13. Two configurations with the same file name and different bytes are
    two digests: the label read under one refuses under the other.

## Boundaries

- Write `microscope_runtime/src/` and `tests/` only. No `contracts/`, no
  `envelope/`, no `approvals/`, nothing in `librarian_agent/`.
- The check holds the policy; the lookup holds none. A label found says
  which device a name is, never whether it may move.
- Commit and push through `contracts/tools/seat_commit.py`, naming each
  path. Never `--no-verify`, `--amend` or force.

## What comes back

To this seat, 4 lines at most:

- the commit;
- each test, watched failing, then passing;
- the suite's counts;
- every place card 061's form did not fit, with the field.
