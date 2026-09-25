# CLAUDE.md — soft-matter-agents

Four agents for soft-matter research: a microscope agent and a simulation
agent that design and run experiments, a librarian that owns all knowledge,
and a bridge that carries cards between the two executing agents.

The design lives in **`plan.md`**, in English like everything else here. Read
it before changing anything structural. Principles **P0–P16** and decisions **D1–D12** there override
habit and convenience: if work would violate one, the work is wrong, not the
principle. Changing a principle means editing `plan.md` first, in the same
commit, with the reason.

## Status

**M0 landed. The four agents are built concurrently.** Milestone names M0–M5
name bodies of work, not an order. What actually blocks what is the column in
`plan.md` §9. §11-1 no longer blocks anything: on 2026-09-19 the person settled
that **the vocabulary is never finished** — entries are added when a question
needs one, so an unanticipated experiment is still takeable. An unregistered
name is not a refusal but an ordering: register it, then plan with it.

`contracts/` is the only shared code. `librarian_agent/kb/` is the store, and
**the read-only MCP server over it exists as of 2026-09-18** (`a9df017`, four
tools). So §9.1's completion condition — one pass with the librarian **on**,
`kb_refs` and `kb_gaps` filled and `degraded` empty — is reachable rather than
hypothetical. **The service answered for the first time on 2026-09-19**:
`queries/log.jsonl` holds seven calls under one issued caller_id, three of them
real gap detection — two `absent`, one `condition_mismatch`. That is §0.3's line
between reading the files and the service answering, crossed.

**§9.1's condition was first met on 2026-09-19** and is now met by **all seven
axes** under `microscope_agent/questions/mic-20260918-001/` — `_a1` through
`_a7`, each with `kb_refs` and `kb_gaps` filled, `degraded` empty, and a
caller_id the query log carries. Three of them (`_a2`, `_a3`, `_a6`) were the
first to stand together, at `b63dcc7`; the seventh joined at `ea58f3e` the same
morning. Count them off a run, not off this sentence: check 45 is what counts
them. Cards outside that count still read the files directly and belong on the
degraded path.

**This file said "three" for a day after it was seven, and said the `_a4` card
was in no commit when `e9d2f69` had committed it that same morning.** Both were
read off prose, and the second grew a paragraph of lesson about uncommitted
work out of a file that was already in the tree. The count has now been wrong
here in both directions, too few and too many, which is why the instruction
above is to read it off the run.

```bash
python3 contracts/validate.py                                    # the repository
python3 contracts/validate.py --strict                           # undecided and pending count as failures
python3 contracts/validate.py --expect-fail contracts/examples/rejected
python3 librarian_agent/src/kb_index.py                          # after editing kb entries
git config core.hooksPath contracts/hooks                        # once per working copy
```

**On the microscope computer (Windows, from 2026-09-24).** `python3` there is a Microsoft Store App Execution Alias that is not Python, so type `python` where the commands above say `python3`; everything in this repository that picks an interpreter now probes it by running it. **Since `9a796f8` the validator and the hooks run correctly there** -- paths print with `/`, `--expect-fail` prints both totals, and the validator no longer needs `PYTHONUTF8`. Agent code outside `contracts/` still reads text without naming an encoding in places, so set `PYTHONUTF8=1` when running an agent's scripts. **The hooks are fixed and not installed**: installing them is a manager's call, made while someone watches the first commits through them. **Pushing** needs the credential manager named, because git there has no helper configured: `git -c credential.helper=manager push origin main` uses the GitHub login saved in Windows, and a plain `git push` fails asking for a username. `sh` is not on the Windows PATH by default; `Git\bin` was added to the user PATH so the librarian's server starts. See §11-22.


The first must end `0 failed`. The last prints two totals, cards and groups,
and every one of both must still be rejected — a fixture that stops failing
means a check stopped working. **Read every count off the run, never off
prose**: three counts written into this file were wrong within a day.

**`--commit-range` freezes the data and not the checker.** It selects which
commits are judged and then judges them with **the `contracts/validate.py`
sitting in the shared working copy**, which never re-execs the committed one.
So a run over frozen history still changes verdict when another seat is
mid-edit in the validator, which is the opposite of what the flag looks like
it buys. On 2026-09-20 two seats reported `check 48` failing on
`contracts/seats.json`; clean archives of both HEADs passed, and the seat that
had run `--commit-range aeaa27b~1..aeaa27b` re-ran the identical range later
and got `PASS`. One variable moved between the two: `manager-bridge` had
uncommitted hunks in the validator's path classifier and reverted them. That
is a controlled comparison and not a proof -- the hunks were destroyed with
`git checkout` and cannot be re-read.

**And read the tree the run names with it.** Several sessions share one
working copy, so a bare run is **nobody's commit** — a failure in it may be
another session's work in progress. The validator says which tree it used on
its last line: a commit, that commit plus uncommitted paths, or the index as
it would be committed under `--staged`. Quoting a number without that line is
how two seats quoted each other stale numbers on 2026-09-19, one of them from
an honest `0 failed` that was true of HEAD and false of the working copy.

**And the line carries a digest of the dirty set, `[dirty XXXXXXXX]`, since
2026-09-23 -- before that it only counted.** It named the commit and the
number of uncommitted paths, so two runs minutes apart could print the same
`plus N uncommitted paths` and have judged different trees; `manager-simulation`
nearly read a `73 pending / 6 N/A` against `70 / 7` as the interpreter
changing the verdict when another seat's edit had moved between the runs.
**Two runs are comparable only when the digest matches** -- and the digest
reads file contents, so it also moves when only data on disk moved.

UNDECIDED and PENDING are not passes. UNDECIDED means a threshold nobody has
chosen (§11-2); PENDING means an artifact a later milestone produces.

The commit gate checks **the tree the commit would create**, not the working
copy — the index is unpacked to a scratch directory and the validator runs
there. With `git commit -- <paths>` git builds a temporary index first, so what
is judged is your paths on top of HEAD and another session's half-finished edit
neither enters your commit nor refuses it. A plain `git commit` has no such
index: whatever anyone staged is your commit, and is judged as yours. **`git commit --amend` is
the same hazard and worse, and this file did not say so until it happened
(2026-09-23).** An amend with no paths rebuilds the commit from **the index**,
so another seat's staged files become yours -- and because the probe form
`git commit -- <paths>` builds a *temporary* index and never updates the real
one, your own work may not be in that index at all: an amend after it can
**replace your commit's contents entirely with somebody else's**. That is
what `28761d4` is. It is worse than a plain commit in the way that matters
for noticing: a plain commit adds a line to `git log`, an amend changes the
content under an existing line, so **with the message unchanged nobody looks
at all**. The only visible trace was that the amended commit's predecessor
still said `probe`. `manager-microscope` made that point; I had called the
two the same shape.

**And the index is not the hazard's root, which I learned by repeating it
inside the hour.** The second time I checked `git diff --cached` first, found
it empty, and amended anyway -- and swallowed **26 files of another seat's
already-committed work**, because **`--amend` targets HEAD and HEAD moves.**
Another session's commit completed between the check and the amend, so the
commit I rewrote was not the one I had made. An empty index proves nothing
about whose commit you are about to replace. **So the rule is not "check the
index before amending" but simply: do not `--amend` in this working copy.**
A wrong message is cheap and a rewritten commit is not; correct it by adding
a commit that says what the badly-named one contains. That second incident
was undone -- `--amend` with an empty index keeps the tree, so the replaced
commit and its replacement had identical trees and `git update-ref` back to
the original restored it with nothing lost -- but it was undoable only
because nobody had committed on top in the ninety seconds it existed.

**A long commit message passed as `$(cat <<'EOF' ...)` has now failed
silently twice**, leaving the commit unmade while the command reported
nothing. Both times the recovery attempt was an amend, which is how one
failure became two. **Write the message to a file and use `git commit -F`.** **And do not filter
a commit's output down to FAIL lines**: when another seat holds
`.git/index.lock` the commit prints `fatal:` and is not made, and a filter for
FAIL shows nothing at all -- which read as success on 2026-09-23, with the
message already in a file. Read the last lines and confirm with `git log -1`. The gate
lists separately whatever differs from what is going in, because nothing checks
that. `--no-verify` bypasses it and leaves no trace, so say so in the
message.

**The working copy and the git index are shared between sessions.** Name paths
rather than using `-A`, and use `git commit -- <paths>` — but **naming a path
is not naming a change**. That form builds its index from the *worktree*
state of those paths, so another seat's in-progress edit to the same file
rides in under your identity, and your own partial staging of it is
discarded — **and a staged deletion is undone**, so that form cannot untrack
a file that stays on disk. Run **`git diff HEAD -- <paths>`** first and check
every hunk is yours -- **not `git diff -- <paths>`, which this file
prescribed until 2026-09-23 and which compares against the index.**
`git commit -- <paths>` builds its temporary index from **HEAD** plus the
worktree state of those paths, so HEAD is the base that matters. With a
stale index the plain form **invents** hunks that will not land; with
another seat's work staged it **hides** hunks that will -- and `git add -A`,
which this same paragraph warns against, is exactly what stages another
seat's work. **Two warnings sat in one paragraph and neither knew about the
other**: the command prescribed here is disabled by the command forbidden
two sentences earlier. `manager-microscope` proved it in a four-line scratch
repository and I reproduced it -- with a colleague's line staged,
`git diff --` shows only `+MINE` while the commit carries `+OTHER SEAT` too.
**The two directions are not symmetric**: a false positive costs one round
trip, and that seat spent one today stopping a colleague over 74 lines a
stale index had invented, while a false negative commits another seat's work
under your identity, which is what `28761d4` is. Checking does not close it either: the window is between the
check and the commit, and it measured three minutes once. No check catches
any of this. See §6.2.

**And `git checkout -- <path>` is the same hazard inverted, which this file
did not say.** The commit form *takes* another seat's uncommitted edits under
your identity; the checkout form *destroys* them. It restores that path from
HEAD and discards **every** seat's uncommitted work in it, not just yours, and
**there is no path-scoped way to undo only your own edits to a shared file** --
I confirmed both halves in a scratch repository rather than assuming them. The
trap is that a seat which has absorbed the warning above reaches for checkout
as the safe way out and does the worse thing; `manager-bridge` did exactly
that on 2026-09-20 and took 92 uncommitted lines of another seat's check with
it, having written half of the warning it was obeying. It had the worktree
diff saved outside the tree and restored inside the minute. **Before reverting
a shared path, save `git diff -- <path>` somewhere outside the tree** -- it is
the only copy of the other seat's work that will exist.

**A check and its fixtures land in the same commit.** `--expect-fail N/N`
reports that every fixture *present* still fails and can say nothing about one
that is gone, because a fixture that was never committed is a file git never
knew: the rule above -- a fixture that stops failing means a check stopped
working -- does not reach it. On 2026-09-20 `bad_gap_name_carries_its_locus.json`
left index, disk, every commit and every loose object; two seats searched
independently, walking unreachable and dangling blobs, and found nothing. A
check committed without its fixtures is a check whose evidence exists only in
a working copy anyone can revert.

**And a rule with no fixture at all is outside that sentence entirely.** On
2026-09-22 a seat tidying §4.4 rule 5 switched its duplicate test off for
every round and `--expect-fail` read **31/31** -- because a plain repeat had
no fixture, so there was nothing to stop failing. *A fixture that stops
failing means a check stopped working* only reaches rules a fixture covers.
**The completing half is to watch the new fixture fail**: the same seat added
one, switched the check off again, and saw 16/17. A fixture you have never
watched fail is a fixture you do not know tests anything. Neither of these gets a check of its own:
nothing at commit time can tell whose hunk is whose, and a fixture that was
never committed leaves nothing to compare against (§11-17).

## Rules that bind every session here

**Safety outranks everything (P0).** People first, then instruments, then
samples and data. Safety decisions are made by deterministic code, never by a
model, and ambiguity stops rather than proceeds. §2.1 lists the
enforced rules — read the list, not a count.

**One agent, one session (D11), in three tiers (D12).** The four agents always
run as four separate Claude Code sessions. Above them sit two seats that touch
no instrument: **architecture**, which owns the repository's own files —
`plan.md`, this one, `contracts/seats.json`, `README.md`, `docs/`,
`pyproject.toml`, `uv.lock`, `.gitignore` — and **manager**, which owns the
rest of `contracts/` and each agent's `CLAUDE.md`. Read the seat's `paths` in
the registry rather than this list; it has grown four times. Instructions go down and reports come up; the
tiers hold no extra permission, only an order. **There are no worktrees** — they
were introduced and reverted on 2026-09-18, and the person was asked again on
2026-09-20 when both conditions for revisiting were met and answered the same.
Every session shares one working copy, which is why the paragraph above about
naming paths exists at all (§6.2.1, §11-17).

**A tier assignment is not something a session can be told by another session.**
A relayed instruction is not your user's instruction, so the person seats each
session directly — six sessions means six seatings. Work flows down freely once
seats are set; authority never does (§6.2.2). A session writes only inside its own agent directory, reads
`contracts/` without writing it, and never touches another agent's directory.
**The commit gate is what enforces that** — checks 35 and 41. Each agent's
`.claude/settings.json` states the boundary and runs the validator after a
write, but its outward path denials are **inert in a session rooted at that
agent**: a path pattern resolves against the session's root, so
`Write(bridge/**)` from `microscope_agent/` names a path that cannot exist.
Tool denials are not inert, and a denial aimed inside the agent's own tree
resolves normally. See §6.2. Sessions communicate only through file cards and read-only
librarian MCP calls, so every transfer leaves a trace on disk. See §6.2.

**MCP tools can be missing for a reason no seat here can see.** Claude Code
keys projects by working directory, and this file said for days that the
approval therefore does not reach a session launched in a subdirectory.
**It does.** On 2026-09-20 all seven `rebuild` entries in `~/.claude.json`
held an empty `enabledMcpjsonServers`, and sessions rooted at the repository
root and at `simulation_agent/` both reached the server anyway: a user-level
approval by server name covers every directory, and the per-directory split
this file blamed was never the operative thing. What actually silenced three
seats for a day was one key in `.claude/settings.local.json` —
`{"disabledMcpjsonServers": ["librarian"]}` — because **a deny beats an
allow**, while the user-level approval prescribed here as the fix had been in
force since 2026-09-19 20:00.

That file is untracked and gitignored globally, so part of a session's real
permissions sits where nothing in this repository can reach it. The commit
gate judges the tree a commit would create and the file is never in that
tree. Check 53 reads settings files by globbing `settings.json` exactly, so
it walks past this one, and its own note about refusals it cannot see names
user-level and harness ones — not a repository file sitting beside the one it
read. Three seats recorded the symptom and none could state the cause from
inside its own boundary. **A commit refused for no stated reason is the same shape, and the file is
`.git/config.worktree` (2026-09-22).** It can hold `committer.name` and
`committer.email`, **`committer.*` beats `user.*`**, and this working copy
currently has it set to `bridge-4`. So a seat committing with
`git -c user.email=...` is silently overridden and check 41 refuses its paths
as another seat's -- which is what happened five times in a row to one seat
before it found the cause. **`GIT_COMMITTER_NAME` / `GIT_COMMITTER_EMAIL` as
environment variables beat both**, which is why the seats using that form were
unaffected; I confirmed the precedence with `git var` rather than assuming it.
**`conda` as a bare command is broken in every session here for the same kind
of reason** -- `__conda_exe:6: permission denied`, from a shell function in
`~/.claude/shell-snapshots/`, which this harness writes per session. The
absolute binary and `condabin/conda` both work. **Call conda by absolute
path**; one seat read the failure as a broken machine and lost half a day,
and its retraction is in §7. **And take a seat's email from `contracts/seats.json`, never from a
message**: a message delivered by session id -- the desktop's session-messaging
route -- arrives with `@` turned into a fullwidth `＠` (U+FF20), so an email
copied out of it matches no registry entry and check 41 refuses the commit.
microscope-20260923-6 caught it in its seat notice on 2026-09-23, and its reply
arrived with the same substitution. **Run `git var GIT_COMMITTER_IDENT` before trusting who you are** -- it costs
nothing and answers exactly, the way calling one tool answers whether the
tools are there. The file is in no tree, so the gate cannot see it, and the
hook made it worse by exiting 1 after `pre-commit: contracts` with no FAIL
line: the symptom did not name the cause and `sh -x` on the hook was what
found it. That silence is `contracts/hooks/` and so a manager's.

**When the tools are missing, read that file first,
by hand** — and read it again, because it moves: on 2026-09-20 it went from
that one key to `{}` to absent inside ten minutes while seats were quoting it
to each other, and nothing anywhere records that it did. Settings are read at
session start, so fixing it leaves a running session unchanged.

**That sentence is the third instance of one class and it took three to see
it.** A fix that lands in configuration reaches **only what starts after
it** -- a settings file reaches the next session, a `mcp_server.py` commit
reaches the next server, and on 2026-09-23 a SessionStart hook reporting the
pinned committer identity reached every seat except the ones already running,
which were exactly the seats it was written for. Each was written down on its
own and none as a kind, so the third arrived looking new. **The remedy that
works is to put the notice where the thing is used rather than where a
session starts**: `manager-simulation` moved the identity warning into the
commit hook, which runs at the moment an identity is actually spent and so
reaches a session that has been up since morning. Ask of any configuration
fix **who is already running**, and if the answer matters, find the use site.

**The librarian's server code has the same shape and it was not written
down.** Each session starts its own `mcp_server.py --serve`, four or five at
a time, so **a fix to the server reaches only sessions started after it**.
A seat that has been up since morning keeps calling the morning's server
with no signal that it is doing so. **This file said nothing anywhere records
which build replied, and that was wrong**: every logged call carries
`server_session: srv-<pid>-<epoch>`, and the epoch is the server's start time.
Decode two of them against `ps` and they match to the second. So the question
is countable from disk, for every past call and not just the processes alive
now, by comparing each call's server start against the last commit to touch
`mcp_server.py` at that moment. **The librarian counted it: 0 of 417 calls
across 69 server sessions were served by a stale build.** That count settles
less than this file first claimed of it. It asks whether a call's server
predated the last `mcp_server.py` commit at that call's moment, and **two
servers can each be current when they answer and still answer differently** if
a commit lands between them. That happened: on 2026-09-19, 37 minutes apart,
one `kb_version` was asked the same question twice under two builds and
returned `in_published_table` and then `absent`. §4.3.1 rule 2 failed and the
log keeps it, because the log is append-only. So the hazard has bitten once,
the 0-of-417 metric does not see it, and check 70 is the one that will. Treat a server fix the way a settings fix is treated --
it lands for whoever starts next and everyone else has to be told -- and
settle whether it bit by counting, not by checking what is running now.

**A manager seat cannot query the store, and that is the design working.**
The four issued `caller_id` forms are all a question's -- `<qid>:v<N>:<config>:<axis>`
and its siblings -- and a manager has no question, so there is no card for an
answer to land on. A query that leaves a log line and no `kb_refs` anywhere is
exactly what the card contract exists to prevent, so **no manager form should
be minted.** Two manager seats hit this refusal within minutes on 2026-09-20
and both read it as a gap; it is not. What a manager needs from the store it
gets **through an execution seat that holds a caller_id** — that route is
already seated, already leaves the trace, and needs no new mechanism. Running
the server directly with its log redirected would work and is the wrong
answer: it buys a manager the store's semantics while removing the one thing
the isolation is for.

**Testing the server's behaviour is a different act and is not refused.**
Asking the service for a fact and measuring how the code behaves are not the
same thing: the `caller_id` isolation exists so a fact taken from the store
lands on a card carrying `kb_refs`, and a measurement of what the code does
produces no fact about the world to land anywhere. So a manager verifying a
server fix, or mutation-testing a check against a synthetic tree, is doing
its own job and needs no issued id. **The line is what may be kept**: a test
may see store contents in passing and may carry none of it into a card or a
KB entry -- that path is a query and needs an id. §6.2 rule 3 still decides
*who*: running or reading code in `librarian_agent/src/` is that agent's
side, not every manager's. The librarian asked for this line on 2026-09-20
after being refused twice, having done the measuring kind and not the asking
kind.

**The two split by MEANS, not by intent, and the first version of this
paragraph did not say so.** Within the hour the seat that asked for the line
crossed it: verifying a colleague's measurement, it called `kb_query` with a
`caller_id` it invented to look issued and its log pointed elsewhere. In its
own head that was *verification*, an allowed category, so the means were never
examined -- the same shape as `manager-microscope` checking whether a method
was sound and not whether it was its to run, one asking *who* and this one
asking *what*. So the test is the entry point and not the purpose: **calling
`kb_query` is querying, whatever it was for; calling `Store.answers_to` and
`match` directly is measuring.** Redone the second way, the numbers were
identical -- the means changed and no conclusion did, which is what makes the
crossing pure loss. And an invented issued-looking id is the worst version,
because the server itself says the check is elsewhere: *"that an
issued-looking one really came from the launcher is enforced at the launcher,
not here."* Nothing there can refuse it. §4.3.1 rule 3 is honour at exactly
the point a seat is most tempted.

**The cheapest test of whether the tools are there is to call one.** A probe
costs nothing and dirties nothing: the server files a refusal with
`caller_id` null and what was claimed -- the `caller_id` and `kb_version` --
under `claimed`. **What else it records depends on which build answered**: a
server started before `9cf04d8` (2026-09-23 23:46) records only who claimed to
ask -- the recorder kept keyword arguments and the tools are called
positionally, so all 15 refusals before it carry just those two keys -- and a
server started after it also records what was asked, under
`claimed.arguments`. librarian-2 found and fixed it, and watched its new
self-test assertion fail on the old code first. Which build answered a given
line is countable, by comparing its `server_session` epoch with that commit's
time. Check 45 guards both
sides of that -- `if cid` before the log line is counted, `if not cid` before
a card is -- so an invented id can neither enter the log as a caller nor back
a card. simulation-3 put off a probe over that worry and then checked; this
seat then read the check expecting to find the guard missing, and found two.
Both of those were a mechanism that sounded right and did not survive being
run, which is what the rest of this file keeps saying.

A seat without the librarian's tools gets no error — it proceeds on the
degraded path, which is legitimate here, so a silent day looks like an
ordinary one. The cards are not silent, though: **`degraded`** carries the
librarian's name until the server answers and only then empties, so no card
ever claims the librarian answered when it did not. This file called that
field `evidence` until 2026-09-20; `evidence` is in `scope_approval.schema.json`
and in no card schema, while `degraded` is in `common.schema.json` and so in
every card. The mechanism was always real and enforced -- check 45 tests an
empty `degraded` against the query log -- and only the name here was wrong. That makes this a schedule problem
rather than an evidence one.

Launching everything from the root is not the fix. Beyond the root being a
top-tier seat, an agent's **inward** denials are relative paths —
`envelope/safety.json`, `approvals/**`, `inbox/**` — which resolve only
from that agent's directory. From the root they name nothing, so the
guards on the person's two folders and the bridge's one all drop at once.
See §6.2.

**Which session am I?** The working directory says it. If it is an agent
directory, read that agent's `CLAUDE.md` and stay inside it. If it is the
repository root, this is a top-tier seat: specify, do not implement. The
directory cannot tell architecture from manager — both sit at the root — so
that one comes from the person who seated you. `contracts/seats.json` then
**narrows** a seat inside the boundaries it owns; it cannot widen one. Which
paths a boundary holds is a table in the validator, so a path added to a seat's
`paths` that the validator classifies elsewhere grants nothing — **and the
reverse bites too**: a path the validator classifies into a boundary you own,
which no seat's `paths` covers, grants nothing either. Boundary and narrowing
are two gates and a path needs both (§11-11).

**Numbers carry four parts (P2).** `{value, unit, source, grade}`. The grade
E1–E6 is derived from the source, never self-reported. E6 — a value a model
made up — may not enter any card or the KB. See §5.3.

**JSON is authoritative, Markdown is generated (P3).** If a number appears in
both, the JSON wins. Hand-editing generated Markdown has no effect.

**Knowledge lives in one place (P14).** The librarian owns it. Execution
agents keep records and a hash-checked snapshot, never their own knowledge
store. New facts leave as result cards for the librarian to enter. See §4.3.2.

**What the librarian could not supply is recorded too.** `kb_refs` holds what
came back; `kb_gaps` holds what was asked for and did not, with where it was
looked for. An estimate made while the librarian was reachable has to name the
gap it stands on (check 39) — looked-for-and-absent and nobody-checked are not
the same number. See §4.3.1.

**Explore is the default (P15).** Most questions here examine a system that is
not yet understood, so targets and constraints are stated in decades and
differences under 10x are ties. A computed value inherits the worst precision
of its inputs; one estimate in the chain means the answer is an order of
magnitude. See §5.8.

## The prior repositories — three closed, one open under rules

**Do not consult** `Brownian-Dynamics-Agent`, `librarian-agent` or
`sim-exp-bridge`, nor any mirror, export or summary of them. This covers
filenames, not just contents: a filename carries vocabulary, and vocabulary
carries design.

**One narrow exception, 2026-09-24, the person's own and confirmed directly:** `librarian-agent` (at `C:\librarian-agent` on the microscope computer) was opened for **one search only** -- the confocal/illumination power calibration -- with every item found ruled under §10.2.1, nothing copied as-is, and no safety limit crossing. Nothing else in it may be consulted, and the other two stay closed. See §10.2.

**`agentic-microscope` was opened on 2026-09-17**, by the person, with the
condition that nothing is transplanted as-is and that anything over-claimed is
downgraded or dropped. That condition is §10.2.1: every item coming across is
ruled **transfer**, **downgrade** or **discard** before it is used, and a
transferred item **names the A1–A7 slot it went into and the §10.3 rule it
passed**. An item that cannot name its slot is discarded. Which rows of §10.2
are open is a separate question from whether the repository is — read the
table, not this paragraph.

Until 2026-09-16 a SessionStart hook injected `~/.claude/knowledge/`, a
read-only mirror of the first two, into every session on this machine, and its
filenames did leak terminology into this design. The hook entry is gone from
`~/.claude/settings.json` and the mirrored content is gone, but **the
machinery is not**: as of 2026-09-20 `~/.claude/knowledge/` still holds
`session-hook.sh` and `sync.sh`, both executable, so one command repopulates
it. Nothing today injects anything -- the one registered SessionStart hook
runs `agent-layer-check.sh`, which names none of the three. What else on this
machine carries the names is inert: shell history, `.claude.json` backups, a
saved plan, and one user-level skill that carries them **in order to forbid
them**, which a grep for leaks will flag and a reader must not.
If the mirror returns, this rule still applies.

They do hold useful material — hardware control paths, device specs, concrete
values such as NA, axis calculation logic, and a record of what went wrong.
`plan.md` §10.2 says when each may be opened, and §10.3 governs how numbers
cross over: through the librarian as graded KB entries, never pasted into code
or `envelope/`, capped at E3 because a measurement taken elsewhere is not a
measurement taken here, and never for safety limits.

When a design question seems to need them before their milestone: answer from
`plan.md` principles, or record it in §11 as an open question. Do not fill the
gap early.

## Talking to the person

**When the reader is the person, say what was found and what to do about
it -- not where the rule is written** (the person's instruction, 2026-09-23).
Chat replies, the daily report, a question put back to the person, and any
card or operator text written for a person carry **no internal codes**: no
section, principle, rule, decision or check numbers, no axis, stage, grade or
tier codes, and no seat names or commit hashes unless the person asked about
that seat or commit. The person is not reading `plan.md` beside the reply. Not
*"rule 2 says ambiguity stops and one of four places proceeds"* but *"a channel
named `*_blanking` is not recognised as a shutter, so it stays open while the
lamp runs -- declare each shutter's role explicitly."* Keep what the person
acts with -- a file to open, a command to run, a value with its unit -- and keep
**provenance in words**: whether a number was measured, computed or guessed,
because a guess shown to the person is still labelled as one. **Records keep
their references**: `plan.md`, this file, commit messages, fields code reads,
and messages between sessions. Where a field meant for the person must also
point at the record -- a held thread's `open_question` has to name
`plan.md 11-<n>` -- the plain question comes first and the pointer after it.

## Language

- Everything inside this repository is written in **English**: code, schemas,
  comments, filenames, commit messages, agent instructions.
- **There is no exception any more.** `plan.md` was Korean until 2026-09-20,
  then briefly a generated English rendering of `plan_ko.md`, and is now the
  record itself. The Korean text left version control and stays in history.
  What the two-file arrangement cost is why it ended: a hash bound the pair,
  no generator existed, so every edit to the record was two hand-edits plus a
  recomputed header, and two architecture seats could not hold it at once.

## Where to look in plan.md

| | |
|---|---|
| §0.1 | the fixed decisions D1–D12 |
| §2, §2.1 | principles P0–P16, and the safety rules |
| §4.1–4.4 | the four agents: what each does and does not do |
| §4.5 | the five-stage pipeline; S3–S5 are the "system designer" |
| §4.6 | the system operator, devices, optical paths, orchestrator, clocks |
| §5 | card contracts, evidence grades, units, precision modes |
| §6 | permission tiers, the two approval cards, session boundaries |
| §7 | repository layout and the dependency graph |
| §8 | the validator's checks, the failure record, and bias |
| §9–§12 | milestones, scope, open questions, facts awaiting a KB |
