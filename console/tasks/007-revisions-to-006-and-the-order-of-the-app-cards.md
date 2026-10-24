# 007 — revisions to 006, and the order of the app cards

Written by `manager-console-office-20261017-1`. You read this; you do not edit it.

**This card assigns no work.** It revises card 006, which said it holds until a
later card revises it, and it fixes the order of the app cards. **Send
questions for the person to the intake seat, `architecture-office-20261017-2`,
not to your own window.**

## Why

The person answered the last open questions after 006 landed, and then said
to finish the console: "콘솔 완성해두ㅗ", read as "get the console finished"
(I-20261024-office-01, `7c33b8c3`). The intake seat's reading, which this
card follows:
- The app cards start now.
- The whole redesign goes through its stages (screens on example data, then
  the mock backend, then the real instruments) with no further start signal
  between stages.
- Every limit already set still stops the work for the person's word where
  it applies.

**Canvas**: https://claude.ai/artifact/Wfw2ybEMyLpfU6UYyQCeVo, now **version
58** (version id `1792807301-4968`), page "Pared down - 2026-10-23". Where
this card and the canvas differ, this card holds.

## What changes in 006

**Self-improvement can be decided from the admin screen**
(Q-20261022-office-14, `659c2214`; Q-20261023-office-04, `881f5119`). This
replaces 006's "the console does not sign it".
- A proposal that loosens a rule, retires one, or changes a core rule gets a
  decision step: Yes or No.
- The step has the same conditions as signing a plan:
  - the person's own login only;
  - the password typed again every time;
  - bound to the proposal's fingerprint as read at a named commit.
- A tightening or a reshape needs no permission. It is listed, with how it
  would be undone.
- The record follows HP-016 (`ffef9a67`), these fields and no others, in
  `microscope_runtime/approvals/harness/<HP-nnn>-<first 12 hex of the
  sha256>.json`:
  `{artifact: "harness_permission", schema_version, proposal,
  proposal_commit, proposal_sha256, decision, screen_words, signed_at,
  signed_through: {via: "console", login}}`.
  `proposal_sha256` is the hash of the proposal file's bytes at
  `proposal_commit`, never the working copy. The person commits the record.
- **Built only after four things exist**:
  - plan.md 8.3's new form;
  - the folder;
  - the gate's refusal;
  - check 89's reading.
  Core changes also wait for HP-018 to land.
- **Under HP-017 the console signs nothing** while
  `microscope_runtime/envelope/console_login.json` is not committed in the
  tree it reads. Today the Office computer has no such file.

**The sample map and the sample screens come back** (Q-20261022-office-15,
`33526c26`), as sub-tabs of Experiments: Runs, Sample, Sample map. Both only
show.
- **Sample map**
  - The frames were taken while the person moved the stage by hand, placed
    by the stage's read-back, and come from a run that saves its frames,
    such as a live-view run. A focus search never.
  - The scale is not measured until the 4x pixel size is in the store.
  - The hole fit comes from a run's results. None is built, and the console
    never fits.
  - Classical candidates may show. A model's guesses are recorded only and
    are never drawn as candidates.
  - Flags and candidate confirmations are "not recordable yet": nothing
    writes them, and when something does it will be at the microscope.
- **Sample**
  - The record names the individual, "said to be <product>", with whether
    its label was read.
  - The loading check is read from a run's hand-step sheet.
  - Where the sample's record lives is not decided (architecture-20261007-1,
    4.6, after Q-04). Invent no path.

**How a question reaches an agent** (Q-20261022-office-04, `5444c688`):
- A new inbox of the agent's, designed on its own and approved by the person
  before it opens.
- The console writes the question request into its own folder, as 006 says.
- **Nothing reaches an agent from the console until that inbox opens.**

**Every other line of 006 stands.**

## The order of the app cards

Each card is assigned to the console seat on its own, after the one before
it lands. Each keeps the canvas's look, works on example data first, and
watches each new test fail before it passes.

1. **008: the shell.** The left sidebar, the footer with STOP and the login
   corner, the seven retired areas and their notice removed, and new places
   for Instruments, Experiments and Library.
2. **Login and accounts.** Plain login ids, never an email. The first-start
   administrator. The password advice. Accounts switched off, never deleted.
3. **Questions.**
   - The field, with autocomplete from strings on disk only.
   - The question request written into the console's own folder. Its schema
     and its validator line come first, from this seat, in `contracts/`.
   - The cards and their progress.
4. **One question and the sign dialog**, on example data.
   - The approval writer is **part of the person's guard** (plan.md 6.1): its
     own module, and built only on the person's word, asked through the
     intake seat when this card is reached.
   - It writes only into `microscope_runtime/approvals/`, with no fallback.
5. **Instruments**: status from the idle status file, optics and control,
   cameras through the frame tap, tweezers, confocal, piezo. Show, draft and
   stop only.
6. **Experiments**: runs, sample, sample map. Drafts waiting for a
   signature. Hand steps shown, never confirmed.
7. **Simulation and Results**, pared to one screen each.
8. **Library**: the three requests. Their schemas are manager-librarian's,
   once the inbox route exists. Until then the screen draws them and sends
   nothing.
9. **Admin**:
   - accounts;
   - console-side roles;
   - agents' permissions read-only;
   - services, from architecture-20261007-1's registry file once it lands;
   - self-improvement, built only when its four pieces exist.
10. **The mock backend.**
    - The console server's mock store serves the files the screens read:
      cards, runs, and copies of the runtime's status file.
    - Live pieces come only from what the runtime has built: frames,
      positions, check now, the approval reader's checks.
    - **A runtime piece that is not built shows "not built", and the console
      builds no stand-in for it.** A console-side fake of a runtime piece is
      the second engine plan.md 15 retired. The pieces still missing are
      listed in plan.md 15.1 under "Who takes what", as manager-microscope's
      cards for the runtime seat. So this stage is finished only as those
      land.
11. **The real instruments.** Reading the real tree, and attaching to a
    running approved run through the run interface only. This is the
    person's act at the bench.

**What stops for the person's word**:
- the approval writer, and any change to it;
- the agents' new inbox, which opens only after the person approves its
  design;
- hands-on control, decided after the reduction;
- any new package install.

The console never commands an instrument, never holds a payment detail or a
key, and never confirms a step done by hand.
