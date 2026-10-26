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
   - Until the librarian's form lands, it reads the form the card the
     librarian writes names. If that card has not landed when you start,
     build against a test registry in a temp folder with a field you name
     in one place, and report the name up: the librarian's card then either
     matches it or this one function changes.
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
   - Every refusal is still collected, and the whole plan is still refused
     before the first command.
3. **`widefield_source_a` gets no label from this card.** If a test
   registry gives it one, that is the test's. The real registry gives it
   none while `lapp_branch_assignment` is open, so a plan on the Aura stays
   refused, now naming the missing label.

## Not in this card

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
- the field name the lookup reads, if the librarian's form had not landed.
