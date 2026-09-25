# 041 — the dispatcher reaches Micro-Manager

Written by `manager-microscope-20260924-1`. You read this; you do not edit it
(§6.2-2).

**REASSIGNED on 2026-09-25 to `microscope-20260924-6`, as phase 1 item 1 of
card 049.** That seat needs it for the double-well measurement and will be
the only seat in these files. `microscope-20260924-1` is not open, and had
not started it. If you are `-1` and read this, **do not start 041.**

Originally assigned to `microscope-20260924-1`, after cards 038 and 039,
and after `microscope-20260924-2` had landed card 040. That card edits the same two
files, `src/orchestrator.py` and `src/operator.py`. Start from its commit,
not before it. Ask that seat when it is in, and check `git status`.

## Why

`plan.md` at `66e3d83`: **a planned run goes through the dispatcher.** The
person has chosen that the photostability measurement bound for the store is
the next repeat under card 034's 20x plan, with runs `-002` and the
five-minute run cited as its inputs. That is a planned run, so the two gaps
card 033 §3b worked around have to close first. **If they cannot close, the
question goes back to architecture rather than being routed around again.**

## The gaps

1. **The registry carries no Micro-Manager labels**, so `Aura` and
   `Kinetix_red` raise `GapError` at preflight. The registry is the
   librarian's (`librarian_agent/kb/staging/devices.v0.json`), so **ask the
   librarian for the labels as fields**, with the evidence for each label:
   the load in run `-002` read them. **Do not map `Aura` to
   `widefield_source_a`.** That mapping is the unconfirmed Lapp branch. A
   label is a field of the channel it names, never a guess at a different
   one. Your side is the resolver that reads them
2. **`derive_commands` never produces `params.settings`**, so
   `micromanager.apply()` would verify nothing. Derive the settings
   mechanically from the plan's fields, so that each property written is
   read back and compared

3. **Approvals written from Windows PowerShell are refused as unreadable,
   and should not be.** Found by `microscope-20260924-2` on run
   `-005`: PowerShell 5.1's `Set-Content -Encoding utf8` writes a byte-order
   mark, and `approvals_on_disk()` in `operator.py` then fails to parse the
   file. **Refusing was fail-closed and correct.** The fix is to read
   approvals as `utf-8-sig`, which accepts the mark and changes nothing
   else. It will bite every approval the person writes from PowerShell. A
   test: an approval file with a byte-order mark is read, and a genuinely
   malformed one is still refused

**Card 033's allow-list and `GuardedCore` stay exactly as they are.** A
planned run is checked by them too; this card makes the dispatcher reach
them, not step around them.

Each gap gets a test in `microscope_agent/tests/`, watched failing.

## Constraints

- no hardware: this is code and tests only. The bench stays the person's
- commit with `git commit -- <paths>` after `git diff HEAD -- <paths>`.
  Hooks are not installed; say so. Run
  `PYTHONUTF8=1 python contracts/validate.py` and read the tree line

**Re-read this card immediately before committing.**
