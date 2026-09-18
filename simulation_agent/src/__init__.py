"""This agent's deterministic code (plan.md 7.2).

**Why this file exists.** Section 7 names one of these modules `operator.py`,
and Python puts a script's own directory at the front of `sys.path`. A flat
`src/` therefore shadows the standard library's `operator` module, and because
`collections` imports it, every stdlib import in the process breaks -- not the
module that asked for it, all of them. The failure is a circular-import error
naming our file, which reads like our bug and is not.

Making `src/` a package fixes it without renaming anything: the modules are
run as `python3 -m src.<module>` from the agent directory, so `sys.path[0]` is
the agent directory rather than `src/`, `operator` resolves to the standard
library, and the siblings resolve as `src.operator` and friends.

So, from `simulation_agent/`:

    python3 -m src.axis_a1_stability      # one axis, one card
    python3 -m src.synthesis              # S4
    python3 -m src.plan_card              # S5, json and its generated md
    python3 -m src.operator               # S6, refuses without an approval

The dependency direction is 7.2's five lines and is checked (check 16):
`axis_*` and `synthesis` know nothing of backends, `operator` sees backend
modules only, and `cards` sits under all of them reading `contracts/` as data.
"""
