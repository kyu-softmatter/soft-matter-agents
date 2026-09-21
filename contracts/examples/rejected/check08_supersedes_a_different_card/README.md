# check 8 — a supersession carrying a different card

A superseding round carries a later revision of the **same** card. This one
names round 1 and its ledger pins a different `card_id` entirely, which is a
different question wearing a correction's clothes.

**Compared by `card_id`, not by path.** §7.1 rule 3 gives each revision its
own filename, so revision 2 of a plan is `v2_plan_….json` beside revision 1's
`plan_….json`. The first version of this check compared paths, which made a
supersession structurally impossible -- no agent revising by the rule could
pass it -- and the isolation test that "proved" the accepting path had kept
one path across two revisions, a shape the real tree cannot hold.
`manager-simulation` measured it. The path is still required to name the same
card once the prefix is stripped.
