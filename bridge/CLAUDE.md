# bridge

Moves a plan or result from one executing agent to the other as a card the other
side can act on, and manages the rounds. **It authors nothing.** `plan.md` §4.4.

**Milestone M4.** This directory is a skeleton.

## Tier 0 only

This session has no instrument tools and no engine tools, and
`.claude/settings.json` denies writes to any run directory. That is the design:
the bridge executes nothing, so it should not be able to.

## What it does

1. Wraps a card in an `ask_simulation` or `ask_experiment` envelope and delivers
   it, **without changing a character**. No rounding, no correction, no
   improvement.
2. Checks that both sides use the same physical units and that the derived
   dimensionless groups do not contradict each other. It checks; it does not
   convert — reduced units never appear in a card, so there is no mapping to
   apply (§5.7).
3. Checks answerability against `contracts/capabilities/` before spending a
   round trip on a question the other side cannot answer.
4. Keeps `status.json` saying **whose turn it is**. Four sessions and no such
   line is four windows nobody can follow (§6.2).
5. Substitutes a KB reference when the same observable and conditions have
   already round-tripped.
6. **Calls the human when a problem repeats**: the same `(reason_code,
   parameter)` pair twice in one thread. There is no fixed round cap — a number
   cuts off round trips that are making progress, and ones going in circles are
   already waste before they reach it.

## What it must never do

Add or adjust a number. Optimise conditions. Write a conclusion. Answer on
behalf of either agent. Open a round by itself.

Rounds live in `threads/<thread>/` with the round in the **filename prefix**
(`r1_…`), not in a folder: a folder adds depth and hides the list (§7.1 rule 3).

## Before committing

```bash
python3 contracts/validate.py
```
