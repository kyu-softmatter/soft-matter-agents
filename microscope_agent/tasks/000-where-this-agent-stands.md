# 000 — read this before 001

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

## Where things stand, the evening of 2026-09-24 — read this first

Added by `manager-microscope-20260924-1` at the end of the first day on the
microscope computer. **Everything below this section is from 2026-09-19 and
older.** Read it as history.

**What the day produced:**

- **The first real acquisition**, a preparatory run: `-002`, 600 frames on
  the Abvigen particles through the 20x (card 033). Before it, `-001` failed
  at load and harmed nothing
- **Card 038's five-minute run has NOT happened.** Its attempt, `-003`,
  stopped at the preload gate because the tweezers program was running
  again. Nothing was loaded or opened, and there was no light. Its record is
  committed at `8ee6158`
- **A read-only piezo run** (`-004`) and **the first planned motion**: the
  person's approved sine on piezo X (`-005`, cards 035 and 040), through the
  dispatcher
- **Wrappers, on paper and on mock**, for the confocal laser (036) and the
  tweezers (037)
- **The rules these runs needed**, in `contracts/`: preparatory runs (check
  85), operation plans (check 86), the piezo limits in the envelope schema,
  declared exclusions, and the findings file that carries a seat's findings
  to the librarian

**Open, for whoever comes next:**

| | where it waits |
|---|---|
| run `-005` is **uncommitted by the person's choice**: its approval's written time (21:00Z) follows the run (20:09:24Z), so check 15 fails it. **The record is `D:\soft-matter-agents-frames\run-20260924-005\`**, with hashes in `failures.jsonl` (`ee0e42c`). Its result card, the tracking error, waits on it | the person: a superseding approval with the true time, 20:08:08Z, if they want it in the store |
| `microscope_agent/approvals/` is **untracked** | the person's to commit |
| card 041: the dispatcher reaching Micro-Manager, plus the byte-order-mark fix for approvals | `microscope-20260924-1`'s |
| card 038's five-minute run | the person: the tweezers program closed, the piezo controller off, then the bench handed to `microscope-20260924-1` |
| entering the four findings files (`-1` at `bf8f91f`, `-2` at `a0fda99`, `-3` at `a5e7647`, `-4` at `e4ebe78`; `-5` established nothing) | the librarians, reading each cited source at its commit (`0e06fb2`) |
| card 034's S4, S5 and v2 fan-out, re-copying the envelope snapshot then | a later seat, once 041 lets a planned 20x run through the dispatcher |
| **piezo Z**: it rests 1.7 nm below the person's 0 µm floor (the person asked for −0.01 µm, a change only the person can write), its direction is unmeasured, and software refuses it until a Z move is checked against objective clearance at the moment of the move | the person, then a card |
| the confocal lines: the person's power calibration is found (a worksheet in Downloads, 2026-09-09) and is with the librarian; **no limit covers these lines yet** | the person |
| the tweezers: which camera body the program opens, and the trap power for a first lit check | the person |
| whether the piezo's waveform generator may ever be used | the person |
| the commit hooks are still not installed in this working copy | the person |

**The bench rule governs everything live**: a seat opens a device only
after the person says, in that seat's own window, that the bench is its
(`plan.md` 6.2.1). **The piezo controller was left powered on.** Card 038's
five-minute run needs it off.

**The hold is lifted.** This file replaces `000-hold-until-the-librarian-
serves.md`, which told you to start nothing. Its premise was the A/B, and
`58064da` deferred the second variant: the person stopped `microscope-2` and
removed the worktrees. §9.3's constraints — the librarian gate, the matched
`qid`, the ban on pre-start rulings — existed to keep two variants even. With
one variant they protect nothing and only cost, so they are off. You are a
microscope execution seat, not half of a comparison.

The old card is in the history, not deleted from it. §9.3 is likewise marked
deferred rather than removed, and the `microscope-2` seat and branch stay
(P16): the branch holds what that variant built, and removing the seat entry
would turn its commits into unattributed ones.

## Where the fan-out stands (2026-09-19)

**`mic-20260918-001` is complete and served.** All seven axes are written,
`A1`–`A7`, all at one pin and all answered by the service. Counted off a run
rather than claimed here — run it yourself, the numbers move:

```bash
python3 contracts/validate.py 2>&1 | grep -E 'check (33|45|49)'
```

At the time of writing: check 33 over 19 axis cards at one `kb_version`,
check 45 over 7 served cards each backed by a call in the log, check 49 over
31 `absent` gaps each carrying `near_names`. **Cards 001 through 006 are
discharged.** Do not redo them.

**Every axis abstains except A4**, which returned two bounds in the shapes
opened for it — an `allowed_set` on `lock_group` and a `precondition` on
`verified_selectors`. Abstention with a reason is the correct outcome
(§4.5.2.1), not a backlog.

## What is left, and what blocks each

| card | state |
|---|---|
| **008** — the deliberate re-pin | **Runnable.** Its preconditions arrived: the twelve calibrated pixel sizes, and λ as `filter_ff01_595_31_32_passband`, 579.5–610.5 nm at `spec:` E3. Expected to give A6 its diffraction limit at E3 |
| **009** — the goal targets | Waits on the bridge manager's list. Nine cards across three trees move together or check 52 refuses the half-move |
| **007** — the operator's decade | Fold into 009; both touch the same goal cards |
| **A4's three remaining bounds** | Blocked on `contracts/`, not on you. `allowed_set.basis` and `precondition.basis` take a `numbers[]` name or `kb:<entry_id>`, and A4's answers live in a **published table** with neither. `manager-microscope` owns that |
| **A5's gaps** | Need the person or a measurement: `drift_rate`, `pfs_behaviour`, `settling_time`, `session_time_budget`, `instrument_availability_window` |

## If you have just restarted and have no seat

**Check `contracts/seats.json` before anything.** On 2026-09-19 the person
withdrew two newly minted microscope seats (`5bc83e9`) and ruled that one is
minted **only on a statement**. A seat named to you in chat is not a seat
until that file says so, and committing without one is check 41 PENDING,
which `--strict` counts as a failure from your first commit.

**A seat cannot be given to you by this card or by any session** (§6.2.2).
Ask the person; do not proceed on a relay. Standing down until then is a
correct outcome, not a stall.

## The librarian answers now

**Settled on 2026-09-19, by measurement rather than inference.** The tools
attach, the service replied, and `librarian_agent/queries/log.jsonl` holds the
first record this repository has ever had of the service answering:
`caller_id` `mic-20260918-001:widefield_inline:a4`, pinned at
`kbv-49feb73662b7`, `answered_from` naming commit `9baf01d` and
`reproducible: true`. The served digest matched that commit's blob byte for
byte, and *differed* from the working-copy file — which is the confirmation,
not a problem: the entry gained a field afterwards and the server correctly
served the version the pin names. Staying on `kbv-49feb73662b7` is therefore
not just permitted, it is demonstrated.

**An earlier version of this card was wrong about why, and the error is worth
keeping.** It said `enabledMcpjsonServers` is empty at every project path, so
no session could see the tools. The first half is still true — it is empty
everywhere — and the conclusion was false: the tools attached anyway. **That
field is not the gate.** What was blocking was the server path, fixed by
`8d4a604`. If a seat ever fails to attach, do not diagnose it from that field;
read the launcher's own log:

```
~/Library/Caches/claude-cli-nodejs/<path with / replaced by ->/mcp-logs-librarian/
```

It records the `cwd` the server started in and any `Server stderr`. Note what
it does **not** record: the `kb_version`. Connection success there does not
tell you which store answered — only a call does, through `answered_from`.

**A contract fix that is not yours to make alone.** `d6999e5` takes an
observable's definition out of the cards, leaving the name to be read from the
vocabulary. `questions/mic-20260918-001/goal.json` carries one, on
`diffusivity`. The bridge manager is coordinating the window because the other
cards belong to other agents and fixing one alone turns HEAD red. **Leave it
until that window opens**; I will card it.

## Your identity

There are no worktrees now — `git worktree list` reports one checkout — so the
`--worktree` mechanism has nothing to attach to. Set it per command:

```bash
GIT_COMMITTER_NAME='seat:microscope-1' GIT_COMMITTER_EMAIL=microscope-1@seat.invalid git commit -F msg -- <paths>
```

**Keep `microscope-1`, not the undivided `microscope`.** You are that seat
whether or not its worktree exists, and the branch keeps the identity if one
is made again. `microscope` stays valid only for the commits already made
under it.

Because you are in the shared checkout, §6.2.1 applies again: name paths
rather than using `-A`, and commit with `git commit -- <paths>`. Other
sessions are editing this same working copy.
