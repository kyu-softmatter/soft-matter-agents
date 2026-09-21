# check 8 — a repeat wearing supersession

Both rounds pin the same card at the same revision, so nothing moved under
round 1. A repeat re-asks what was answered; this one re-asks and calls
itself a correction. Rule 5's answer to a repeat is a knowledge reference in
`status.json`, not another round.

This is the branch that makes `supersedes` a gate rather than a word: the
claim is recomputed from the two ledgers, and a writer cannot open a round
by asserting one.
