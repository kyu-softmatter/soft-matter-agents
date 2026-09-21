# 009 — the operator runs the plan it was born with

Written by `manager-simulation`. You read this; you do not edit it (§6.2-2).

**Found by `simulation-4`, verified here.** `src/operator.py:447`:

```python
plan_path = cards.question_dir(qid) / f"plan_simulation_{qid}.json"
```

That filename is **revision 1's plan**. Revision 2's is
`v2_plan_simulation_sim-20260917-001.json`, and `artifact_name` and
`question_revision` appear nowhere in `operator.py` — confirmed by grep, both
absent.

So calling `operator.run()` today executes the **discarded** plan: 2 µm beads
where the measurement said 5 µm, and the window and record length that went
with them. **It does not fail.** It writes `rev 1` in the log and finishes
green, and check 15 then compares that log against revision 1's plan card and
finds them agreeing — consistently, and consistently stale.

**Not yet bitten.** `run-20260920-003` ran at 05:11:31Z and `946831c` landed
after it, so that run used the only plan there was. The next one bites.

## The same shape as `load_goal`, one file over

You fixed `load_goal` hardcoding `goal.json` and check 12 showed you 46
failures while you did it. **Here nothing shows you anything**, and that is
the whole difference: the goal is cited by `origin` so a stale read produces a
value mismatch, while a plan is *executed* and a stale read produces a
perfectly consistent run of the wrong experiment.

## What to do

`run()` takes a revision, defaulting to `cards.question_revision(qid)`, and
resolves the filename through `artifact_name` — the same shape and for the
same reason as `goal_path`. **Write the reason in the comment**, because the
next reader will otherwise wonder why a runner needs to know about revisions
at all: it is that a revision is a different experiment, not a newer copy of
one.

**And the log has to say which it resolved.** A default that silently picks
the latest is the same hazard wearing better clothes — the run record must
name the plan file it actually read, so a later reader can tell "ran revision
1 deliberately" from "ran revision 1 because the code could not see
revision 2". `log.json` already carries `plan_id` and `revision`; make them
come from what was resolved rather than from the plan's own fields, which
agree with themselves whichever file was opened.

## Do not put this in the validator, and here is why

A check comparing a run's revision against the question's current one would
refuse a deliberately-repeated older run, and a gate that refuses correct work
is one somebody reaches around. **The guard belongs at run time**, where the
resolution happens and the intent is known. What the validator can hold is the
weaker, true thing: the log names the file it read.

## The class this belongs to

`008` found that nothing compares a result card's numbers against the
`observables.json` of the run it cites. This is the same finding on the other
side: **nothing checks what the execution path rested on.** One asks which
plan was run, the other asks what was read back. Both were invisible because
every artifact is internally consistent — the run agrees with the plan it
opened, and the card agrees with itself.
