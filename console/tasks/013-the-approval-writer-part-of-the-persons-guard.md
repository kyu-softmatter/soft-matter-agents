# 013 — the approval writer, part of the person's guard

Written by `manager-console-office-20261017-1`. You read this; you do not edit it.

**Assigned to `console-office-20261017-1` (Console 1)**, after card 012
lands. If you are not that seat, take nothing from this card and report up.

**Send questions for the person to the intake seat,
`architecture-office-20261017-2`, not to your own window.**

## Why

The person's word, committed at `b4f340ee` (Q-20261024-office-01, read
15:49 -0700 on 2026-10-24):

> (가) 예, 지금 만든다. 서명한 승인을 내 승인 폴더에 쓰는 부분을 콘솔 작업 세션이 지금 만들어도 된다. 나중에 그 부분을 바꿀 때는 같은 방식으로 다시 내 허락을 받는다.

("(a) Yes, build it now. The part that writes a signed approval into my
approvals folder may be built by the console's working session now. When
that part is changed later, my permission is asked again the same way.")

plan.md 6.1 makes this code part of the person's guard: it writes only after
the password check passes, and only the approval the screen showed. 15.1 is
the runtime's half: one folder and one reader, the login checked against the
person's own file, and no fallback. The mark's shape landed at `e2f5b08b`.
Card 011's dialog is the screen this writer serves.

## What to do

1. **One small module of its own**, for example
   `src/sma_console/signing/approval_writer.py`.
   - Its docstring says it is part of the person's guard and that any
     change to it needs the person's word, asked through the intake seat,
     citing `b4f340ee`.
   - Nothing else in the console writes into `microscope_runtime/`.
2. **It writes only when every one of these holds, checked in this order,
   in the same request.** Otherwise it refuses with a reason in words and
   writes nothing.
   - The session's login is `person_login` from the console's settings, a
     plain id. This decides the screen and the console's own refusal. The
     runtime still decides from the person's file, never from these
     settings.
   - The store is the real tree, not the mock. A practice or test login
     writes nothing real; under the mock it may show as signed, as 011 does.
   - The password was typed again and checked in this request, through the
     login's throttle.
   - The plan's fingerprint, recomputed from the plan card on disk by
     `card_sha`'s rule, equals the fingerprint the screen showed and sent.
     Otherwise "the plan changed; review it again".
   - `microscope_runtime/approvals/` exists in the tree the console reads.
     There is no other place and no fallback.
   - No approval file of that name is there yet. Otherwise "already
     approved".
3. **What it writes**: one plan approval.
   - Named `appr-<qid>-r<plan_revision>.json`, as the folder's files are
     named today.
   - Built to `contracts/schemas/plan_approval.schema.json` and validated
     against it, read from the repository, before writing.
   - `approved_by` is the login, and `approved_at` is UTC now. Add
     `signed_through: {"via": "console", "login": <login>}`. Nothing else
     beyond the schema's own fields.
   - Written whole to a temporary name in that folder, then renamed. Never
     rewritten, and nothing else in the folder is touched.
4. **After writing**, the screen says: written; the runtime reads it from
   disk now; commit it yourself when you choose. No seat may commit a file
   under `approvals/` (check 41). The audit log gets `approval_written`:
   the login, the question, the plan, the revision, the fingerprint and the
   file name. Never the password or a hash of it.
5. **Tests, each watched failing first.** Each refusal writes nothing,
   checked by listing the folder before and after:
   - refuses another login, a login with no `person_login` set, and a login
     that is not a plain id;
   - refuses under the mock store, and a practice or test login;
   - refuses a wrong password, throttled;
   - refuses a changed plan, by fingerprint;
   - refuses a missing `microscope_runtime/approvals/`, including when the
     old `microscope_agent/approvals/` exists;
   - refuses an existing file of that name;
   - on success, exactly one file, valid against the schema, carrying the
     mark, with nothing written outside that folder;
   - no password anywhere in the file, the response or the audit log.

## What not to do

- Write nothing else into `microscope_runtime/` or any agent's folder, and
  never commit an approval.
- Change nothing in the runtime. Its reader is card 087's, in the runtime
  seat's hands.
- No change to this module after it lands without the person's word, asked
  the same way.
- Install nothing.

## Done when

- `npm run typecheck`, `npm test` and `npm run build` pass from `web/`.
- `uv run pytest` passes.
- The validator ends `0 failed`.
- One commit through `contracts/tools/seat_commit.py`. Report the hash to
  this seat, and say which test covers each refusal.
