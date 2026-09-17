# CLAUDE.md — soft-matter-agents

The design lives in `plan.md`. Read it before changing anything structural:
principles P1–P13 and decisions D1–D8 there override habit and convenience.
If work would violate one of them, the work is wrong, not the principle —
changing a principle means editing `plan.md` first, in the same commit, with
the reason.

## The prior repositories are out of scope

**Do not consult the four prior repositories** — `agentic-microscope`,
`Brownian-Dynamics-Agent`, `librarian-agent`, `sim-exp-bridge` — nor any
mirror, export or summary of them. This covers filenames, not just contents:
a filename carries vocabulary, and vocabulary carries design.

Until 2026-09-16 a SessionStart hook injected `~/.claude/knowledge/`, a
read-only mirror of the first two, into every session on this machine, and its
filenames did leak terminology into this design. The mirror and the hook entry
have since been removed. If either returns, this rule still applies.

The point of this rebuild is to re-derive the role boundaries, the permission
model and the vocabulary from scratch. Borrowing the earlier projects' terms
smuggles in their accumulated scope, which is exactly what the rebuild exists
to shed. `plan.md` §10.2 fixes the milestone at which each prior repository
may be consulted; nothing earlier is allowed, however convenient.

When a design question appears to need them: answer it from `plan.md`
principles, or record it in `plan.md` §11 as an open question for the user.
Do not fill the gap from the mirror.

## Language

- Everything inside this repository is written in **English**: code, schemas,
  comments, filenames, commit messages, agent instructions.
- `plan.md` is the one exception and stays in **Korean**.
- Numbers in prose are not numbers (P2). A quantity needs a unit and a source,
  and the JSON is authoritative over the Markdown (P3).

## Status

Pre-M0. Only `plan.md` and this file exist; `contracts/` comes first (see
`plan.md` §9). This file grows as the contracts land — it is not yet a
description of working code.
