# 003 — the history fixtures are written and cannot land yet

**State: built, tested, 3/3 firing, and held outside the repository.** What it
waits on is one line in §7 that this seat may not write.

## What it is

§11-7 assigned the history side of the gate's own fixtures to `manager-bridge`
on 2026-09-20, and settled the shape: **build the repositories, do not store
them.** `git init` plus a handful of commits costs seconds; keeping four
repositories as fixtures is what is expensive, and an expensive fixture makes
adding a check expensive, so checks stop growing.

Four checks cannot be reached by `contracts/examples/rejected`, because what
they read is history and not a file in a folder — **26, 35, 41, 46**. Their
only evidence has been a sentence in a commit message, and a check nobody has
ever seen fail is a check nobody has tested.

The harness builds a temporary repository per fixture, copies `contracts/`
into it, and runs **that** copy of the validator there, so `REPO` and
`GIT_REPO` both resolve inside the fixture and no check can pass on evidence
the fixture never supplied. Each fixture names the check it is for **and the
verdict it expects**, and counting requires that verdict from that check —
the group-fixture rule, for the same reason.

Three fixtures, covering 35 and 41, last run `3/3 answered as intended`:

| check | verdict | what it builds |
|---|---|---|
| 35 | FAIL | one commit writing into two agents at once |
| 41 | FAIL | a microscope seat committing into `bridge/` |
| 41 | PENDING | a commit by an identity `seats.json` does not list |

The third expects **PENDING and not FAIL**. `seats.json` sets
`unknown_committer` to `report`, so an unregistered committer is deliberately
not refused; asserting a FAIL there would be a fixture pretending the rule is
stricter than it is. The registry already records what `report` costs — an
unattributed commit gets no boundary checking at all — and the report is the
only thing between that and silence, which is why it earns a fixture.

**26 and 46 are not covered.** That is a gap in the fixtures, not in the
checks, and the file says so rather than letting its opening list of four read
as done.

## Why it is not in the tree

Check 13 refuses a new path under `contracts/` that is not declared in **both**
§7 of the design document and `ALLOWED_PATHS` in `validate.py`. The second is
this seat's; **the first is architecture's**. No architecture session was
running when this was built.

That document moved while this note waited. It was `plan.md` in Korean, then
`plan_ko.md` with `plan.md` generated from it, and since 2026-09-20 it is
`plan.md` in English again with no exception to the language rule. An
untracked `plan_ko.md` is still sitting on disk; it is architecture's to
remove. This note said `plan_ko.md` until the reversal — corrected here rather
than left to age, which is the whole reason the note exists.

It was briefly staged, then unstaged: a staged file in a shared index rides
into whatever another session commits next. And it was then moved out of the
tree entirely, because check 13 reads files on disk rather than the index, so
merely leaving it there put a red line in every other session's run — nobody's
commit, and noise for everyone until the declaration lands.

**Held at** `/private/tmp/claude-501/-Users-kyuhwan-Desktop-rebuild/a1d663-hold/history_fixtures.py`.
Temporary storage. If it is gone, rebuild it from this note — the harness is
about 150 lines and the design is above.

## What unblocks it

Architecture inserts the §7 line. Suggested text:

> `contracts/history_fixtures.py` — fixtures for the checks that read history
> (26, 35, 41, 46). The repositories are **built, not stored** (§11-7): each
> fixture makes a temporary repository, copies `contracts/` into it and runs
> **that copy of the validator** there, so the file side and the git side both
> resolve inside the fixture. Like a group fixture it **names the check it is
> for and the verdict it expects**, and counting requires that verdict from
> that check. Run with `python3 contracts/history_fixtures.py`.

Then this seat adds the `ALLOWED_PATHS` entry in the same commit as the file,
and CLAUDE.md's command list gains the run line beside `--expect-fail`.

**Do not land the `ALLOWED_PATHS` entry on its own.** It would be a
declaration with nothing behind it, which is the defect class this repository
spent 2026-09-19 counting.
