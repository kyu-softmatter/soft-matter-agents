# 036 — catalogue the lab's manual archive, and a safety guide per device

status: **open** · issued 2026-09-24 by manager-librarian, on the person's
instruction of the same day

## GOAL

The person pointed at `C:/Users/Takatori lab/Desktop/Maintanance/Setup/` and
asked for two things: *"save this properly and make a safety guide for each
device."* Saving properly here means every vendor document is a source record
the store can cite. The safety guide is a person-facing page per device that
says what that device's manufacturer warns about, with a page reference for
every line, and says plainly where no manual exists.

## The person's ruling, to be recorded before anything is read

**Asked 2026-09-24:** two editions of each Tweez 300 safety manual are on this
computer: `C:/Program Files/Aresis/Tweez300/Manuals/` (2022-11-02) and the
Setup archive (2021-11). Which does the safety guide follow?
**Answer: the installed 2022-11 edition.**

That settles `safety_manual_versions_differ` in `src_aresis_tweez300_manuals`,
which says nothing may be entered from either safety manual until the person
decides. Record it as its own `person_ruling` source. Do not add it to
`src_person_ruling_20260924`, which is about pixel size: one ruling per record,
so each can be cited and superseded on its own. Keep the 2021 files catalogued
as the superseded edition and enter nothing from them.

## TASK

### 1. One source record per device document set, referenced in place

Follow `src_aresis_tweez300_manuals`: `vendor_spec`, referenced by path and
sha256, **not copied into the repository** (vendor copyright, and the folder
is 2.2 GB, almost all of it installers). Its `not_yet_catalogued` list already
names the ten PDFs with hashes; re-hash them rather than trusting that list,
because the list was written by another session.

| device (`devices.v0.json` id) | what the archive holds |
|---|---|
| `optical_tweezers` | four Tweez 300 manuals, already recorded |
| `piezo_stage` | Nanobench 6000 software manual, NanoFlash manual, NPC-D interface library manual, three release notes. **Software only**: no hardware manual for the stage or controller |
| `stand_ti2e` | Ti2 Control software manual, English and Japanese. **No Ti2-E hardware manual.** The Japanese copy is a translation: catalogue it, enter from the English one |
| `dmd` | a two-page Micro-Manager setup note and a Readme. No hardware or safety manual |
| `camera_red`, `camera_blue` | **installers only, no manual.** The evaluation tool is named `PmPrimeCamEval` while the store holds a Kinetix 22 datasheet. Record that; do not resolve it by guessing |
| `laser_combiner`, `confocal_csuw1`, `widefield_source_a/b` | **nothing in the archive** |

Skip the licence folders, the LabVIEW runtime and the installers. They are not
knowledge.

### 2. Safety statements as entries, one claim per file

For each manual that has safety content, enter each distinct warning as a
`claim` entry: E3, `vendor_spec`, with printed and PDF page in
`validity_conditions` the way `trap_laser_emission_is_switchable_over_tcp`
does it. Numbers the manufacturer prints (laser class, wavelength, maximum
output, travel range) go in `numbers` with units. Paraphrase; **no manual
prose is reproduced** (the source record's `license_note`).

Term counts from the text layer, to size the job and not to replace reading
it: Laser Safety Manual 13 pp, General Hardware and Safety 14 pp, Installation
Guide 33 pp, User Manual 107 pp (all dense with laser and interlock warnings);
Nanobench manual 18 warnings and one danger notice; NPC-D library and NanoFlash
2-3 cautions each; Ti2 Control 10 cautions; the DMD note has none.

Every entry ends like the existing one: **knowledge, not policy.** What any
session may do is the person's, and lives in the envelope.

### 3. Where there is no manual, a gap and not a guess

Each device in the lower rows of the table gets a `kb_gaps`-shaped record:
kind `absent`, `searched` naming the archive path and the installed-software
folders you looked in. **Do not fill a missing manual from general knowledge
of the model.** A laser class remembered by a model is a model-produced value,
and it may not enter. The four with nothing include the laser combiner, the
second laser on this bench. That gap is the most important line in this task
and should read as such.

### 4. The guides: generated, one per device

A script in `librarian_agent/src/` renders
`librarian_agent/kb/guides/safety_<device_id>.md` from the entries and gaps.
Markdown is generated and never hand-edited, so a correction goes into an
entry and the guide is regenerated. Each guide has:

1. **What the manufacturer warns about**, in plain words, each line with its
   document and page.
2. **The manufacturer's figures**, value and unit, labelled as the
   manufacturer's rather than measured here.
3. **What is missing**: manuals the archive does not hold, sections not yet
   read. This part must be as visible as part 1.
4. A closing line saying that **this page is not the lab's safety limits**.
   Those are written by the person after confirming them on the instrument.

A device with nothing in the archive still gets a guide. Its guide is short:
it says so, and names the document to obtain.

**The reader is the person.** The guides carry no internal codes: no section,
principle, check, grade or seat names, no entry ids in the body. The source is
a manual title and a page. Put a single line at the bottom giving the
`kb_version` it was generated from.

## CONSTRAINTS

- The store moves when entries land. Publish **once at the end**, not per
  device, and not while a fan-out is pinned mid-flight. Check the query log
  for in-flight pins first.
- Name files when committing, not `librarian_agent/`. Another librarian
  session has uncommitted pixel-size work in the same tree.
- Nothing crosses into any envelope. If a guide exposes a limit the
  envelope lacks, **report it up**, and the person decides.

## REPORT

The commit(s); the list of guides with, per device, how many manufacturer
statements it carries and what is missing; the gaps filed; anything the entry
schema could not express (raise it; `kb_entry.schema.json` is this seat's).
Then the one sentence: what is not yet on disk.
