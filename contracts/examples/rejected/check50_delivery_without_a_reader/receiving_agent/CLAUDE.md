# FIXTURE — not standing orders for anything

This file exists to be read by check 50 and found wanting. It is deliberately
a plausible set of standing orders that never says where a round arrives: it
describes the agent's questions, its axes and its approvals, and stops. Nothing
here instructs a seat to look anywhere for a delivered envelope.

That was the real state of `microscope_agent/CLAUDE.md` on 2026-09-19 when the
first round was delivered into its tree. The delivery was correct and the
envelope was valid; the seat read it only because another session said so in
chat. Do not add the word to this file to make a run go green — the group is
supposed to fail.

## What this agent writes

`questions/<qid>/` holds its own cards. `approvals/` is the person's.

## Before committing

Run the validator. Zero failures.
