# 063 — the light-path order, from the person's 16 October description

Written by `manager-librarian-scope-20261019-4` on 2026-10-27. You read this;
you do not edit it.

**For `librarian-scope-20261019-1`, the librarian execution seat on the
microscope computer** (seated at `720cc889`). If you are not that seat, take
nothing from this card and report up.

## Why

The person decided in the microscope computer's intake window, read 13:54
-0700 on 2026-10-27 and committed at `c46095ec` (`docs/ideas/20261027.md`,
Q-20261027-scope-09), verbatim:

> 현미경 실시간 값까지 보여 줘야 한다. 10월 16일 설명을 지금 '설명에서 온 것'으로 순서로 기록해라. 추정 부분은 빈칸.

("It must show the microscope's live values too. Record my 16 October
description now as the order, graded 'from a description'. The guessed parts
stay blank.")

The console is to draw the live light path before anyone has walked the stand.
It can only draw an order the store holds. This card enters that order from
the person's description. Microscope card 101 (`6024414f`) later records the
order seen at the stand, by eye. That observation supersedes this entry, and
wherever the two differ the observed order wins. plan.md 15.1 item 11 carries
the rule, as the design seat amends it from `c46095ec`. Read it as amended; if
the amendment has not landed when you start, the verbatim line above and the
rest of `c46095ec` are the rule.

## The source, and what enters from it

- **The record of the description is the exported page**:
  `C:\Users\Takatori lab\Downloads\Light path console-html\Main.dc.html`,
  sha256 `5cdcbc49ba6d27f23cd3ec566fc1d40bdfd1f1525359c54092601a5a07f44254`
  (verified by this seat on 2026-10-27). It is the export of the design page
  "Microscope Light Path", <https://claude.ai/artifact/2huLpZuNgkvok2rASAdJN2>.
  Verify the hash before you read it. If it differs, stop and report up: the
  page has moved since the decision, and the decision named this copy.
- The file sits outside the tree, so nobody else can re-read it. Record it as a
  source the way the store records an operator source, with the path, the hash
  and the URL. Copy it under `librarian_agent/kb/sources/` if the store's
  source rules allow it, so the record can be re-read. The console manager is
  separately copying the same file into `console/`. That copy is the design's,
  and yours is the store's.
- The person's 16 October words in the Office computer's intake window are not
  on this computer. The page carries them as per-fact labels, which is why the
  decision names the page as the record.
- **Only what the person stated or recalled enters.** The page labels every
  fact with its origin. Labels found in the export on 2026-10-27: *stated*,
  *recalled*, *inferred*, *earlier setup*, and *drawn this way as an
  assumption*. A fact labelled *inferred*, *assumption*, *earlier setup* or
  *spec sheet* is the page's, not the person's, and it is left blank: not
  entered, not guessed, not filled from the store. A *recalled* fact enters as
  a recollection, if your grading allows one; say which grade it took.
- **The grade is the one the source derives, not one this card assigns.** You
  have said it is E5, operator recall and not a measurement. Every row says it
  comes from a description and was not checked on this microscope.

## What to enter

1. **First, the name the order needs.** You said that the order of elements
   along a beam needs a registered vocabulary name, and that the entry waits
   for it. Say which name is missing, and where:
   - An element id or a beam id that belongs in the device table or the
     optical path table (`kb/staging/`) is yours to add. Add it there first,
     with the same provenance as the order.
   - A name that belongs in `contracts/` (`quantities.json` or
     `observables.json`), or a field `contracts/schemas/kb_entry.schema.json`
     lacks, is not yours to write. Report it up to this seat, naming the file
     and what the name must mean. Stop that part until it lands. Enter
     whatever does not stand on it.
   - The existing form may already carry an order: a `claim` entry whose
     subject is the configuration (`widefield_inline`, `widefield_side`,
     `confocal`, `transmitted`, `trapping`) and whose `identifiers` hold one
     key per position. If you judge that it can, say so and use it, and no
     new name is needed. If you judge that it cannot, say why.
2. **Each beam, source to sample, and each path back to a detector, in the
   order light meets the elements**, as far as the person stated it. The page
   has five beams: the transmitted lamp, the Aura III, the Spectra III through
   the DMD, the laser combiner through the spinning disk, and the Tweez 300.
   It also has the paths back to each camera, the eyepieces and the side
   camera.
   - **A partial order stays partial.** It is recorded as far as it goes.
   - **An element the person named without stating its place** is listed
     against its beam as *place not recorded*. It is never put in a position.
   - A blank is not an empty slot. Write it so a reader cannot take a blank
     for "nothing there".
3. **The check against the store is part of the entry, not a separate step.**
   - **Per-line laser power is not order.** The page says each laser line's
     power is individually controllable. The store says per-line power is not
     transmitted. That fact does not enter as order, and this card does not
     enter it at all.
   - **Any other stated fact the store contradicts is not entered as order.**
     List each one in your report with both sides and the entry id on the
     store's side. Do not resolve it; the stand check does.
4. **Supersession.** The entry has to make plain that the observation from
   card 101 replaces it. When that observation is entered, it carries this
   entry in `supersedes`. Do not wait for card 101 to enter this one.

## What this card does not do

- It changes no limit, no device module and no plan, and it commands nothing.
  It takes no number from the page into code or `envelope/`.
- It does not draw anything. The live drawing is the console manager's card,
  built from what you enter.
- It does not enter what the page marks inferred or assumed, even where you
  could confirm it from the store. A confirmation from the store is a store
  fact, not the person's description.

## Done when

- The order is in the store, with its source recorded and hash-checked, and
  its grade derived. Blanks are left blank, and partial orders are shown as
  partial. `kb_index.py` has been rerun, and the validator ends `0 failed` on
  a tree you name.
- Your report back to this seat lists:
  - what entered, beam by beam;
  - what was left blank, and under which label;
  - each stated fact the store contradicted;
  - the vocabulary name: registered, already existing, or waiting on a
    manager, and which.

Dead ends go in `failures.jsonl` with `task: 063`.
