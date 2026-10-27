# 061 — each device row carries its Micro-Manager label, citing the entry that holds it

Written by `manager-librarian-20261007-1` on 2026-10-26. You read this; you do
not edit it.

**For a librarian execution seat** (librarian-20261007-1, or whichever
librarian seat the person opens next). It comes after 060 unless the person
moves it. If you are not a librarian seat, take nothing from this card and
report up.

## Why

Read **plan.md 15.1 item 9** (`fb1f828a`), and microscope card 091
(`159d4c71`), which waits on this one.

- The runtime's software-motion check asks Micro-Manager's allow-list about
  the devices a command reaches. That list is keyed by **Micro-Manager device
  labels**: `Kinetix_red`, `DiaLamp`, `Aura`, `Core`.
- A plan names the **store's names**: `camera_red`, `dia_lamp`,
  `widefield_source_a`.
- Nothing maps one to the other, so every drafted plan is refused as naming an
  unknown device, on mock as on the instrument.

A label is a fact about this instrument's configuration, so it is yours (P14).
The store already holds several labels, in entry `identifiers`:

| registry name | label | entry | grade |
|---|---|---|---|
| `camera_red` | `Kinetix_red` | `camera_red_mm_control_path` | E3 |
| `z_drive` | `ZDrive` | `mm_label_zdrive_is_the_focus_axis` | E3 |
| `nosepiece` | `Nosepiece` | `nosepiece_is_an_mmcore_state_device` | E3 |
| `dia_lamp` | `DiaLamp` | `dia_lamp_reports_state_and_intensity` | E1 |
| `csuw1_shutter` | `CSUW1-Shutter` | `csuw1_shutter_state_reads_a_label` | E1 |
| `pfs` | `PFS` | `pfs_reports_focus_maintenance_status_and_range_in_three_states` | E3 |
| Aura III 5-NII-WA (a designation, not a row) | `Aura` | `mm_label_aura_is_the_aura_iii` | E3 |
| Spectra III 8-NII-XS (a designation, not a row) | `LightEngine` | `mm_label_lightengine_is_the_spectra_iii` | E3 |

This table is the manager's reading of the store on 2026-10-26, not your
input. Re-derive it from `kb/entries/`, and if your reading differs, yours
stands and you say so in the report.

## The form

**One field on a registry row: `mm_label`, an object
`{"label": "<the exact Micro-Manager label>", "entry_ref": "<entry id>"}`.**

- The row gets it in `kb/staging/devices.v0.json` and reaches the runtime only
  through the snapshot's `devices` table. The runtime reads the field and
  nothing else, and holds no copy of the mapping.
- It goes on a channel row or an element row, wherever the plan-facing name
  is: `camera_red` is a channel, `dia_lamp` and `z_drive` are elements of
  `stand_ti2e`.
- **The cited entry must carry the same label, character for character, in
  its `identifiers`**, under `mm_label` or `mm_device`. The store has used
  both keys for one meaning, and you do not rename them in existing entries.
  Use `mm_label` in new entries.
- **The grade is the entry's, never the row's.** The field has no `grade` or
  `source` of its own, so the row cannot claim more than the entry does.
- **One label per row, and one row per label.** A label names one device.
  An entry whose identifier lists two labels in one string (the turret
  shutters' `Turret1Shutter, Turret2Shutter`) backs neither row.
- **A row with no entry holding its label gets no field.** That covers
  `camera_blue` today, and anything else without one. An absent field is
  what makes the runtime refuse with the missing label named, which is the
  right answer.
- **`widefield_source_a` and `widefield_source_b` get no label while
  `lapp_branch_assignment` is open.** Which channel is which engine is exactly
  that question, and a label on the channel would settle it in passing. Put
  `Aura` and `LightEngine` on the two designations under `light_engines`
  instead, the same way and in the same field, so the facts sit where the
  engines' other facts already are.

**The highest-grade entry wins.** For `camera_red`, the entry measured here,
`kinetix_red_label_opens_serial_a24m723015` (E1), states `Kinetix_red` in its
claim but not in its `identifiers`. Do not edit it. If you judge the run's
record is enough, enter a new entry citing the same run whose `identifiers`
carry `mm_label: Kinetix_red`, and cite that. Otherwise cite the E3 entry and
say why in the report.

## Added the same day: the configuration each label was read under

Read **plan.md 15.1 item 9** again at `344d115a`. The software-motion check
now uses a label only when two things hold. Its entry is E1, meaning a run on
this instrument read the device's report of itself under that label. And the
sha256 of the configuration file the label was read under equals the one the
runtime records at load. So the row has to say which configuration, in a form
code can compare:

- **`mm_label` gains a third key, `config_sha256`**: the 64-character
  lowercase sha256 of the configuration file the label was read under,
  exactly as the reading run's log records it.
- **The cited entry carries the same digest in its `identifiers`, as
  `mm_config_sha256`.** The row's digest is a copy of the entry's, the way
  the label is.
- **The digest comes only from a run log of this system**, an entry whose
  source is `measured:<run_id>`. Do not compute it from a file on disk: which
  file was loaded is the run's fact, not the file's. A configuration named
  only in prose ("with X loaded"), or only by its file name, gives no digest.
- **A row whose entry gives no digest keeps `mm_label` without
  `config_sha256`.** The label stays in the store as knowledge for planning
  and naming. The runtime refuses to command on it and names the missing
  digest, which is the ruling working.
- **Adding `mm_config_sha256` to an existing entry is allowed** when that
  entry's own cited run recorded the digest: it states what the run recorded
  and changes no claim. This also lets you add `mm_label: Kinetix_red` to
  `kinetix_red_label_opens_serial_a24m723015` instead of entering a new
  entry, which replaces the "do not edit it" above. Say which you did. Editing
  an entry moves `kb_version` exactly as adding one does, so do it between
  fan-outs.

The architecture seat read the files at `344d115a` and found that
`run-20260924-002` records `8184073e...` for
`single_cam_red_noDMD_nocom10.cfg`, and that the person approved
`DMD_dualcam_LUNF.cfg` (`80135a4e...`) on 2026-10-19. That reading is the
architecture seat's, not your input. So **the digests you can enter today
will not match the approved file, and nothing on the instrument will run on
them.** That is expected. The labels that will let something run are new
readings from a run under the approved file, which manager-microscope cards.
They reach you as findings in the ordinary way. This card only makes the row
able to carry them.

Two self-tests are added to step 4:
- every `mm_label.config_sha256` is 64 lowercase hex and equals its cited
  entry's `identifiers.mm_config_sha256`;
- every entry carrying `mm_config_sha256` has a `measured:` source.

## Not decided here, and not yours to decide

- **Whether the runtime may command a device on a label graded E3.** A label
  read on the prior project's configuration is still E3 here. The runtime
  holder decides how grade bears on commanding; the cited entry carries the
  grade so the runtime can see it.
- **Which configuration file is loaded.** Several entries say their label
  holds "with configuration X loaded", and their validity conditions say so.
  Matching that against the configuration actually loaded is the runtime's.
- **Whether a plan may name an engine by its designation.** That is a
  vocabulary entry, registered when a plan needs one.

## What to do

1. Add `mm_label` to each row and designation that an entry backs. For each,
   cite the entry, after you have read it yourself.
2. Rebuild the exports and the snapshot through `src/export_snapshot.py` as
   usual, and confirm the snapshot's `devices` table carries the field.
3. Write the `kb/wiki/` page changes `src/wiki.py` makes, if any.
4. **Self-tests**, each watched failing before it passes, in the same place
   as your other export self-tests:
   - every `mm_label.entry_ref` names an entry in `kb/entries/`;
   - that entry's `identifiers` carry the same label under `mm_label` or
     `mm_device`;
   - no label appears on two rows;
   - `widefield_source_a` and `widefield_source_b` carry no `mm_label`;
   - the snapshot's `devices` table text equals staging's, field included.
5. Run `python src/kb_index.py` and the validator.

## Report

Send manager-librarian-20261007-1:

- each row given a label, with its entry, grade and configuration digest (or that it has none);
- each row left without one, and why;
- any entry you made, with its source;
- the commit hash, and the self-tests you watched fail.

Also send the runtime seat, microscope-office-20261017-1, the field name and
the commit. Card 091 reads the field through one function, and that function
follows this form.

A validator check that the row's label matches its entry is the manager's,
and it lands with its fixtures, separately from this card.
