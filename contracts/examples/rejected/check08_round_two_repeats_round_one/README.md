# check 8 — the plain repeat rule 5 was always about

Round 2 asks the same observable in the same direction as round 1 and claims
no supersession. Its source sits at the same revision, so nothing moved: this
is re-asking what was already asked, and rule 5's answer is a knowledge
reference in `status.json`, not another round.

**This fixture exists because the rule had none.** On 2026-09-21 a cleanup in
check 8 left a block that skipped the duplicate test for every round, and
`--expect-fail` still reported 31/31 cards and 16/16 groups -- the oldest half
of rule 5 was switched off and nothing anywhere noticed. A check with no
fixture is a check nobody has watched fail.
