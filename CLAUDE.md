# CLAUDE.md — soft-matter-agents

Four agents for soft-matter research: a microscope agent and a simulation
agent that design and run experiments, a librarian that owns all knowledge,
and a bridge that carries cards between the two executing agents.

The design lives in **`plan.md`** (Korean). Read it before changing anything
structural. Principles **P0–P16** and decisions **D1–D11** there override
habit and convenience: if work would violate one, the work is wrong, not the
principle. Changing a principle means editing `plan.md` first, in the same
commit, with the reason.

## Status

**M0 landed; M1 (the microscope agent) is next.** Implementation order is
microscope, simulation, librarian, bridge (`plan.md` §9) — so the first two
agents run without a librarian, with every card marked
`degraded: ["librarian_agent"]`. That is deliberate: independence bolted on
later is usually not independence.

`contracts/` exists and is the only shared code. Nothing else does: the four
agent directories are still empty.

```bash
python3 contracts/validate.py                                    # the repository
python3 contracts/validate.py --strict                           # undecided and pending count as failures
python3 contracts/validate.py --expect-fail contracts/examples/rejected
```

The first must end `0 failed`. The second must end `8/8 cards rejected as
intended` — a card that stops failing means a check stopped working.

Two checks report UNDECIDED rather than passing, and that is the point: the
per-plan E5 cap is unchosen (§11-3, deferred until the librarian exists) and the
envelope comparison needs `envelope/safety.json` from M1. A threshold nobody has
chosen is not a threshold that is satisfied.

## Rules that bind every session here

**Safety outranks everything (P0).** People first, then instruments, then
samples and data. Safety decisions are made by deterministic code, never by a
model, and ambiguity stops rather than proceeds. `plan.md` §2.1 lists the
seven enforced rules.

**One agent, one session (D11).** The four agents always run as four separate
Claude Code sessions. A session writes only inside its own agent directory,
reads `contracts/` without writing it, and never touches another agent's
directory. Sessions communicate only through file cards and read-only
librarian MCP calls, so every transfer leaves a trace on disk. See §6.2.

**Numbers carry four parts (P2).** `{value, unit, source, grade}`. The grade
E1–E6 is derived from the source, never self-reported. E6 — a value a model
made up — may not enter any card or the KB. See §5.3.

**JSON is authoritative, Markdown is generated (P3).** If a number appears in
both, the JSON wins. Hand-editing generated Markdown has no effect.

**Knowledge lives in one place (P14).** The librarian owns it. Execution
agents keep records and a hash-checked snapshot, never their own knowledge
store. New facts leave as result cards for the librarian to enter. See §4.3.2.

**Explore is the default (P15).** Most questions here examine a system that is
not yet understood, so targets and constraints are stated in decades and
differences under 10x are ties. A computed value inherits the worst precision
of its inputs; one estimate in the chain means the answer is an order of
magnitude. See §5.8.

## The prior repositories are out of scope — for now

**Do not consult** `agentic-microscope`, `Brownian-Dynamics-Agent`,
`librarian-agent` or `sim-exp-bridge`, nor any mirror, export or summary of
them. This covers filenames, not just contents: a filename carries vocabulary,
and vocabulary carries design.

Until 2026-09-16 a SessionStart hook injected `~/.claude/knowledge/`, a
read-only mirror of the first two, into every session on this machine, and its
filenames did leak terminology into this design. The mirror and the hook entry
have since been removed. If either returns, this rule still applies.

They do hold useful material — hardware control paths, device specs, concrete
values such as NA, axis calculation logic, and a record of what went wrong.
`plan.md` §10.2 says when each may be opened, and §10.3 governs how numbers
cross over: through the librarian as graded KB entries, never pasted into code
or `envelope/`, capped at E3 because a measurement taken elsewhere is not a
measurement taken here, and never for safety limits.

When a design question seems to need them before their milestone: answer from
`plan.md` principles, or record it in §11 as an open question. Do not fill the
gap early.

## Language

- Everything inside this repository is written in **English**: code, schemas,
  comments, filenames, commit messages, agent instructions.
- `plan.md` is the one exception and stays in **Korean**.

## Where to look in plan.md

| | |
|---|---|
| §0.1 | the eleven fixed decisions D1–D11 |
| §2, §2.1 | principles P0–P16, and the safety rules |
| §4.1–4.4 | the four agents: what each does and does not do |
| §4.5 | the five-stage pipeline; S3–S5 are the "system designer" |
| §4.6 | the system operator, devices, optical paths, orchestrator, clocks |
| §5 | card contracts, evidence grades, units, precision modes |
| §6 | permission tiers, the two approval cards, session boundaries |
| §7 | repository layout and the dependency graph |
| §8 | the validator's checks, the failure record, and bias |
| §9–§12 | milestones, scope, open questions, facts awaiting a KB |
