# 013 — the approval writer, part of the person's guard

Written by `manager-console-office-20261017-1`. You read this; you do not edit it.

**Assigned to `console-office-20261017-1` (Console 1)**, after cards 015 and
014, which the person's "connect the mock system" moved first
(`aeea9d60`). If you are not that seat, take nothing from this card and report up.

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

## Where it writes: the person's approvals folder (revised 2026-10-26)

On 2026-10-24 this card wrote only into a test root (`d4ec508f`). The
reason was plan.md 15.1 item 4 (`0607b848`): until card 087 landed, the
operator would have accepted a console-written file on the console's checks
alone.

**Card 087 landed at `549867d2`, and 088 at `78574ee7`.** The operator now
does three things for a file that carries the console's mark:
- it checks the mark;
- it reads the person's own login from `envelope/console_login.json`,
  beside the folder the approval was read from;
- it compares the two byte for byte, and refuses when the file is missing
  or invalid.

That meets item 4's condition for the real folder. The writer is not built
yet, so it is built once, writing where the person said at `b4f340ee`: into
their approvals folder. Nothing that exists changes, so this needs no
further word from the person. Any change after it lands still does.

So:
- **The one target is `<tree>/microscope_runtime/approvals/`**, where
  `<tree>` is the root the console's real store reads.
  - There is no target setting and no fallback.
  - It never writes into the old `microscope_agent/approvals/`.
  - Against a scratch copy (card 063's form), it writes into that copy's
    folder and nowhere else.
- **Under the mock store it writes nothing**, as before.
- **Practice on the runtime's mock** (card 087 item 5):
  - The console, run against a scratch copy, writes into that copy's
    approvals folder.
  - A mock run started with
    `--approvals <copy>/microscope_runtime/approvals` reads it. Every
    backend but the mock refuses that option.
  - The runtime takes the login from
    `<copy>/microscope_runtime/envelope/console_login.json`.
  - Whoever sets up the copy places that file. The console never writes it.
- Every rule below holds.

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
   - `<tree>/microscope_runtime/approvals/` exists. Otherwise "your
     approvals folder is not there", and it creates nothing.
   - **The person's login file** is in place and agrees with the session:
     - `<tree>/microscope_runtime/envelope/console_login.json` exists;
     - it is valid against `contracts/schemas/console_login.schema.json`,
       read from the repository;
     - its `login` equals the session's login, byte for byte.

     Otherwise refuse, because the runtime would refuse the approval for
     the same reason. Say which: "your own login file, placed by hand
     beside the safety policy, is missing", "is not valid" or "names
     another login". The console reads that file and never writes it.
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
   - Written whole to a temporary name in that folder, then renamed. The
     temporary name does not end in `.json`, because the runtime reads
     every `*.json` there and must never read a half-written file. Never
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
   - refuses when the tree has no `microscope_runtime/approvals/`, and
     creates none;
   - refuses a missing login file, an invalid one, and one that names
     another login;
   - writes only into the test tree's `microscope_runtime/approvals/`:
     nothing lands in that tree's old `microscope_agent/approvals/`, and the
     repository's own `microscope_runtime/approvals/` is unchanged after the
     whole suite, compared by listing and by hashes;
   - the temporary file's name does not end in `.json`;
   - refuses an existing file of that name;
   - on success, exactly one file, valid against the schema, carrying the
     mark, with nothing written outside that folder;
   - no password anywhere in the file, the response or the audit log.

## What not to do

- Write nothing else into `microscope_runtime/` or any agent's folder.
  Never write the login file, and never commit an approval.
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
