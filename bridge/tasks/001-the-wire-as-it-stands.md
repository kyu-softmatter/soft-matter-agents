# The wire, as it stands on 2026-09-19

Written by manager-bridge. This is the standing record; a message may point at
it but may not replace it (§6.2-2). If something here is wrong, send it up
rather than editing the file — `bridge/tasks/` is the manager's to write.

## What check 8 holds a round to

Read this before writing a round, and treat a refusal as a report worth
sending up rather than a puzzle to work around.

- The envelope is the bridge's and carries nothing of its own: `author: bridge`,
  and `numbers`, `assumptions`, `kb_refs` all empty.
- `direction`, the card kind and the payload's author agree, three ways.
- `qid` is the payload's. A `thr-` thread, never a `solo-` one. Round ≥ 1.
- `payload_hash` is the canonical hash of the payload exactly as carried.
- The answerability verdict is **derived** from `contracts/observables.json`
  and the receiving side's capabilities table. Claiming more than the tables
  say is refused. `no` belongs in a refusal card, never an envelope;
  `undeclared` holds the round and gives the turn to a person.
- `unit_consistency: no_counterpart` is the opening round only.
- One `(direction, observable)` per thread. A repeat is a substitution in
  `status.json`, not a second round.
- A delivered envelope (`VALIDATED`) needs `r<N>_hashes.json`, and the ledger's
  `source` has to match the payload by id, revision and status.
- `blocked_pairs` with one pair in two rounds means `escalated`, turn `human`,
  and no further round. A repeat visible in the thread's refusals but missing
  from the ledger fails too.
- The envelope carries the payload's `degraded`. A plan made without the
  librarian must not read as normal on the other side.
- Under `bridge/threads/<name>/`, the directory name is the thread.
- The markdown may not contain a number: the envelope's `numbers[]` is empty
  and check 9 requires every number in a markdown file to be in its card.

## Four things settled on 2026-09-19

**The ledger does not hash `status`.** It hashes the card with status removed
and records the status separately. Approving a carried plan used to change its
digest and make a correctly transported round report tampering — which would
have refused the approving commit and every commit after it.

**`plan_completion` is the plan, not the run.** §4.4 grants one automatic
trigger and that is it, so a finished run does not open a round: a person does,
under `human`. A plan crossing is not a comparison — M4 wants two results for
one observable, and carrying a plan is how the second side learns which run to
do.

**Rounds are `r<N>_`, revisions are `v<N>_`** (§7.1 rule 3). Check 13 reads each
against its own field.

**A result says which estimator it ran**, by naming the vocabulary version it
followed rather than copying the estimator text. Check 46 refuses a pin that
stood at no commit.

## Calling the librarian

The bridge's `caller_id` is `bridge:<thread>:r<N>` — for example
`bridge:thr-tracer-diffusivity-001:r1`. Declared in §4.3.1 and, as of
2026-09-19, accepted by `common.schema.json`, where `axis.schema.json` and
`screening.schema.json` now both point rather than each carrying a copy.

**Accepted by the schema is not the same as accepted by the server.** The
bridge seat called `kb_query` with that id on 2026-09-19 and was refused:
`caller_id '…' is not <qid>:<config>:<axis>` — the pattern as it stood before
the bridge form was added. Two causes were found and both are real:

- The server held its own copy of the pattern. The librarian side changed it to
  derive one (`query_log.caller_id_pattern()`), which closes the class rather
  than the instance. They also found that consolidating the pattern into
  `common.schema.json` had taken the server down at import time, because two
  files read the schema by bare subscript — so the count of copies was four,
  and one failure mode was a server that did not start rather than one that
  degraded.
- **An MCP server process holds the code it started with.** A session whose
  server began before the fix goes on being refused while a sibling session
  works, and the launcher reports the connection healthy throughout. Connected
  is not working.

So if a call is refused with that message: **get a fresh process and retest**
before reporting a contract defect. A fresh process that still refuses is the
contract and goes to the librarian side; one that succeeds means the session
was older than the fix.

**Re-read before you cite.** This paragraph said something else for an hour:
that no contract described the librarian service, and that an absent contract
should be reported. It was false. `plan.md` §4.3.1 carries all four tools with
their arguments and says outright that the table is canonical — and it also
records that a duplicate `contracts/librarian_tools.json` was proposed on the
same reasoning a day earlier, accepted, and reverted, because the table
already gives the signatures and a second copy is the split §11-11 counts. The
rebuttal was pre-written in the document said to contain nothing.

Two seats reached that conclusion the same day, one from a `grep` for a
filename that did not exist, one from a checkout read two minutes before the
revert. Neither is carelessness of a kind a rule prevents: eight sessions
share this working copy, and a file quoted as it stood when you last looked is
a different file. **A missing file is not a missing contract**, and a search
for the filename somebody proposed will not find the contract that already
exists under another name.

**Do not hand-spawn the librarian's server, even though the command is the one
`.mcp.json` registers.** The argument that running a file means reading it does
not hold — spawning puts none of the producer's source into this seat's
context, which is what §6.2 rule 3 protects. The reason is narrower and it is
P4: the registered invocation is fixed and reviewed, and a hand-spawn is
whatever arguments the caller picks. Read-only would stop being a property of
the contract and become a property of this seat's restraint, and P4 is the rule
that refuses exactly that substitution. A stale server is fixed by a new
window, from the person.

The microscope execution seat reads this differently and used the route,
recording the disagreement rather than letting it look settled — which is the
right handling. The general question is with the architecture seat; this
paragraph binds this seat until it answers.

"Reconnect" is not the way to get one. The reconnect tool re-dials connectors
whose status is `failed`, and a stale server reports `connected` with its four
tools present — it is serving correctly, from old code. For a project-scoped
stdio server the only fresh process is **a new window, which the person
opens.** A seat cannot clear this from inside itself.

So the rungs are three, not two: **visible is not callable, and
schema-accepted is not server-accepted.** Item 5 still cannot be performed.

The unit is a thread and a round rather than a question, because one thread
crosses two qids, one per side. The `bridge:` prefix is there so a parser
splits the id without knowing the namespace.

Until 2026-09-19 no id existed that this seat could legally use, so item 5 of
`bridge/CLAUDE.md` — duplicate blocking against the store, which is the whole
reason a round can be substituted rather than spent — could not be performed at
all. That is now open. What it means in practice:

- A round may only claim `degraded: []` when a query under its own `caller_id`
  is in `queries/log.jsonl`. **That is a requirement on the writer, not a
  check.** `caller_id` is an argument: the server sees no identity behind it
  and cannot tell that the process calling is the seat the id names, so the
  log **corroborates** a claim and does not verify it. On 2026-09-19 three
  lines one second apart carried three different seats' ids, which is one
  process iterating over id forms and not three seats — and nothing in the log
  can say so. A round could point at a line it did not produce and nothing
  downstream would notice. Reading the store's files is also not the service
  answering (§0.3), and a refused call leaves no line at all, so an empty log
  is indistinguishable from never having asked.

  The rule this seat already applies one layer in is the same one: a verdict
  the writer can choose is not a gate (check 8, check 21). Here the honest move
  is the verb rather than a new mechanism — say corroborates, and do not read a
  green completion condition as verified.
- `degraded: ["librarian_agent"]` is the right entry in three states, and they
  are not the same state. **Absent**: the tools are not in the session — how
  the window was launched, fixed by relaunching it. **Present and refusing on
  the contract**: the server rejects a form the contract declares, which no
  seat fixes from inside and goes to the librarian side. **Present and serving
  old code**: the tools answer, correctly, from a process that started before
  the contract moved. The third is the one that looks like nothing is wrong.
  Say which in the round's note, or the next reader restarts a window that was
  never the problem — or worse, does not restart the one that was.

- **A round may not rest `degraded: []` on a log line it cannot claim as its
  own.** The log is keyed by `caller_id`, and a round's id is
  `bridge:<thread>:r<N>` — so a line written by anyone holding that string,
  including a service verifying its own fix, is indistinguishable from the
  round's own query. On 2026-09-19 exactly that happened: a query answered at
  08:01:01Z under `bridge:thr-tracer-diffusivity-001:r1`, made by the librarian
  side to test a fix, while this seat's two calls were both refused. A round
  pointing at it would claim a service answered it when the service never did.
  Raised: the grammar has no form for a verification call, and the refusal path
  already solves the same problem by keeping an un-issued id out of the
  `caller_id` field entirely.

Do not invent an id to see what the server accepts. A fabricated `caller_id` in
the query log is the impersonation §4.3.1 rule 3 exists to prevent.

**What the next seat does about it.** With a librarian process no older than
the contract, make the item-5 duplicate check for `thr-tracer-diffusivity-001`:
`kb_query`, `caller_id: bridge:thr-tracer-diffusivity-001:r1`, observable
`tracer_diffusivity`. Expect zero entries and a gap — three seats have said
independently that the store holds no measurement of it, and the microscope's
own A4 query is the closest thing to a precedent.

The answer is not the point, and this is the least obvious thing in the day's
record. **The only bridge-prefixed line in `queries/log.jsonl` is one no bridge
seat wrote** — the librarian side's 08:01:01Z call testing its own fix, made
under this round's id before `selftest:` existed to hold it. Both of this
seat's own calls were refused and a refused call leaves no line. So the log as
it stands corroborates nothing for this round, while looking exactly as though
it does. A correct answer reached by three routes still leaves the log wrong,
and the only thing that fixes it is making the call.

What it buys is narrow and worth naming: a later round can claim
`degraded: []` on a line of its own rather than on one it merely matches.
`selftest:` now exists, so a fresh stray line under a round's id would be a
contract violation rather than an ambiguity — but it does not retroactively
clean the one already there.

Before concluding anything from a failure, say which of the three states above
it is. The window this instruction outlived was replaced for the third one:
tools present, answering, from a process older than the fix.

## Recorded

**2026-09-19, the first bridge session read `librarian_agent/src/mcp_server.py`
and `librarian_agent/queries/README.md`** while diagnosing the caller_id
rejection, and reported it. §6.2 rule 3 bars reading another agent's directory,
not only writing to it; the bridge's exception covers the two executing agents'
`questions/` and nothing else. Nothing was written and check 35 reads commits,
so nothing caught it — the seat did.

The verdict stands and the lesson is narrower than it first read. The route
was always **up and over** — ask the librarian side — rather than open their
source, and the second bridge window reached the same conclusion from §4.3.1
alone. But "the server file added nothing" was wrong: the server carries its
own copy of the pattern, and **that fact is not discoverable from
`contracts/`**. It is what made 2026-09-19's fix incomplete. Not licensing the
crossing; correcting why it was not needed.

A dead end that produces no card belongs in `bridge/failures.jsonl` (§7, §8.1);
a seat without `questions/` writes only there. The validator did not know that
path until 2026-09-19 and now does.

## One bridge session, and a handover that is now recorded

A second execution session was opened on 2026-09-19 and the first has since
closed its window, released `bridge@seat.invalid` and handed
`thr-tracer-diffusivity-001` over. **That handover is recorded here**, which is
what this file is for: the rule below says a thread moves only when it is
handed over in this file, the first handover happened in messages instead, and
the incoming session read the rule and correctly held off the thread. The rule
worked on its first day against the case that motivated it. Both of those
message contexts are now gone; this paragraph is what is left.

- `thr-tracer-diffusivity-001` belongs to the session holding
  `bridge-2@seat.invalid`. r1 is committed, the turn is the microscope's, and
  both hashes re-derive from disk.
- A thread belongs to the session that opened it. It moves only when the move
  is written here. A new thread takes a name no other thread has.

`status.json` is the collision point when two sessions do run at once, because
it is overwritten as the turn moves rather than appended. Check 8 holds the
directory name and the `thread` field equal, so a thread cannot quietly become
another one, but nothing stops two writers from losing a turn between them.

Seat identities: `seats.json` lists `bridge`, `bridge-2` and `manager-bridge`.
The `bridge` entry stays although no session holds it — deleting it would turn
`1a6e879`, committed under it, into an unknown committer. One identity per
session; do not take one that has come free.

## A dead end with no card goes in bridge/failures.jsonl

The file exists as of `1fc3a4f` and holds two rows — a `refusal` and a
`deviation`, both from the librarian reachability task of 2026-09-19. Check 29
passes over it: `21 failure records in 4 files are well formed`. **It checks
form, not completeness**, so a short file is not evidence of a quiet day and
**its silence should not be read later as no dead ends having happened.**
Nothing requires this seat to write a row; only this paragraph does. Section 7
gives a seat without `questions/` that file and nothing else, and a try that
was folded without producing a card is recorded nowhere else (§8.1).

This paragraph said the file did not exist until 2026-09-19, hours after it
did. The sweep that caught it came from the simulation manager: pull every
commit sha and path out of a document and ask git and the filesystem whether
they resolve. It is a one-minute run with a poor yield — fourteen of their
fifteen hits and both of mine were artefacts of the script, a date that looks
like hex and a file correctly described in the past tense. The one that is
left is worth the minute, and it is not the kind a checker finds: **the defect
is prose in the present tense about something that is not there**, and what a
path test detects is a path that does not resolve. Those are not the same
thing, which is why this stays a habit rather than becoming a check.
