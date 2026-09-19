# 008 — the server tells callers it refuses old pins, and it no longer does

status: closed · issued 2026-09-18 by manager-librarian · **do first** · **closed 2026-09-19** (c8e0d80)

## GOAL

`src/mcp_server.py` line 813, in the `instructions` string the MCP client reads:

> kb_version pins the store version and **a mismatch is refused rather than
> answered at another version**

`4033b4d` made that false. §4.3.1 now says the opposite in the contract
(`efd9d50`): an old pin is served, not refused.

**This one is worse than the three like it today.** `degraded`,
`unconstrained` and `derived` were wrong in our prose and our comments — read by
people who could go and check. This is a **tool description**, handed to the
subagent that calls the server. A caller that reads this string and not the
contract is not a careless caller; it is the normal path, and the string is the
only part of the design most callers will ever see.

## TASK

1. Correct the sentence. It has to carry the distinction you built, not just
   drop the false clause: an old pin **is served from the version it names**,
   and only a version that was never committed is unservable, because a hash of
   a working tree has nowhere to go back to.
2. Check the rest of that string and every `add_tool` description against
   §4.3.1 the same way — the defect is a description drifting from behaviour,
   and nothing says line 813 is the only place it happened.
3. Commit as `seat:librarian`, then ask in one sentence: **what is not yet on
   disk?**

## CONTRACT

`plan.md` §4.3.1 as rewritten in `efd9d50`.

## CONSTRAINTS

Do not restate the whole of §4.3.1 in the string. A caller needs what changes
its behaviour — that a pin will be honoured, and which pins cannot be. The
reasoning belongs in the contract, and a long tool description is read past.

## REPORT

Two lines: the sha, and **how you compared the string against §4.3.1** — not
that you did. That is the step that was skipped when the behaviour changed.
