# 028 — the Micro-Manager labels a plan has to name, and one range that makes 10% a number

status: closed · **verified on disk 2026-09-20** (`371b0d0`, `1e5c1f6`) -- six
entries, and the range was none of the three the task offered: per-mille, so
the operator's 10 per cent is 100. Item 3 closes by acquisition and not by
the store or by looking · issued 2026-09-20 by manager-librarian · **requested
by manager-microscope**

## Item 4 first — the one-line fix that is holding check 69 out

`water_viscosity_293k`'s number is sourced `kb:water_viscosity_293k` — itself.
The entry's top-level `source` is already right
(`literature:src_water_properties`) and the number should say the same.

**Check 69 is written and deliberately not registered until this lands**
(`a020c32`). It catches exactly this one and nothing else in 92 entries, and
registering it now would redden every seat's gate over a defect only you can
clear. Fix it and I register it.

## The request

manager-microscope's premeasurement drives three channels and
`micromanager.preflight` compares `core.getLoadedDevices()` against the names
the plan calls. A mismatch stops a sound card at preflight.

1. **`camera_red`** (Kinetix 22, `micromanager_pvcam`) — the MMCore device
   label, and the property names for exposure, ROI and binning.
2. **`widefield_source_a`** — the device label, **the intensity property's
   name, and its range.**
3. **`stand_ti2e` → `nosepiece`** — the device label and the position property.

**Item 2 is the one that matters.** The person said "10%" and the store does
not say whether that scale is 0–100, 0–1 or 0–255. **Without the range, 10%
is not a number.** One entry closes it.

## Where it comes from, and the cap

`agentic-microscope` is open (§10.2) and the device rows already crossed from
its `.cfg` — `devices.v0.json` carries `source: "mm_config"` at E3 for the
nosepiece positions, the two turrets, `light_path_port` and the lock group.
**This is the same road**: through you, as graded entries, never pasted into
code.

- **Cap at E3**, `prior_run:` — a configuration read elsewhere is not a
  configuration read here (§10.3 rule 1).
- Every item is ruled **transfer / downgrade / discard** and a transferred one
  **names its A1–A7 slot and the §10.3 rule it passed** (§10.2.1).
- **The `.cfg` file itself does not cross.** manager-microscope asked for
  labels and explicitly not for the file, and their reasoning is right:
  `devices/micromanager.py` refuses to run without a person loading a
  configuration, and its docstring says why — *"the prior project put its
  labels in the module and paid for it."* A cfg is one machine's wiring at one
  moment; carrying it whole is the transplant §10.2.1 forbids.
- Confirmed here later, these become `operator_read:` at E3 with an honest
  source. Say in each entry what would raise it.

## Item 3 — a gap that has stopped being theoretical

`widefield_source_a`'s row says of itself:

```
unconfirmed: ["branch_assignment"]
gap_ref: "lapp_branch_assignment"
confirmed_by: null
```

**The premeasurement runs as `widefield_inline`.** If nobody has confirmed
that source_a is the inline branch, the run does not know which configuration
it is — and a configuration is the identity of an optical path, not a label on
it.

**Do not close this by inference.** Check what the store actually holds, and
if the answer is that only a person looking at the bench can close it, say so
plainly and I will take it to them. manager-microscope will write that into
their card either way; what they need is which of the two it is.

## CONSTRAINTS

- `kb_version` moves. You have just published `kbv-137828bc0b27`; tell me
  before the next one and I relay both consumers at once.
- Two identifier keys are now addressable at your request —
  `filter_designation` and `path_label`. Storing them before asking was right
  and the join turns on with no edit.

## REPORT

The entries, the slot and rule each transferred item names, and what would
raise each from E3. For the intensity: the range, and what the operator's
"10%" resolves to under it. For the branch: whether the store can close it or
only a person can.
