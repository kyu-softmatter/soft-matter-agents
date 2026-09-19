# queries — who asked the store for what, and why

`log.jsonl`, one JSON object per line, appended by
`librarian_agent/src/query_log.py`. `src/mcp_server.py` writes a line for every
call it answers, and treats a logging failure as worse than no answer: if the
record cannot be written the call fails, because a silent hole in the trail is
the thing the trail exists to prevent.

**It records refusals too, since 2026-09-19.** A refused call is an ask, and
holding only answers meant the service's refusal rate was written nowhere —
"nine of ten queries came back empty" was countable because empty is an
answer, and refusals were not. It also left a card claiming `degraded`
indistinguishable from one that called and was turned away, which is the same
distinction `searched` draws between not-looked-for and not-there.

A refusal asserts nothing. Every argument as given goes under `claimed`, and
no field states a property the server just rejected — because a refusal may be
*of* a `caller_id` the launcher never issued, and writing that string into
`caller_id` would put an invented id into the audit trail. That is the reason
this seat declined to fabricate the log's first line, applied to its own
records.

## Why it is beside `kb/` and not inside it

§4.3.2 sorts material into three genres — knowledge, records, policy — and a
query log is a **record**, the same genre as `microscope_agent/runs/`. The
mechanical reason is sharper than the taxonomy: `kb_version` is a hash over the
entries, and a card cites the store as `kb:<entry_id>`. Everything inside `kb/`
is therefore either citable or noise in that hash, and a log is neither. Keeping
it out preserves the boundary `kb_version` exists to draw.

## What a line holds

An answered line: `asked_at`, `caller_id`, `kb_version`, `tool`, `purpose`,
`observable`, `condition_range`, `returned`, `gaps`, `coverage`,
`server_session`. A refused one: `asked_at`, `tool`, `outcome`, `reason`,
`claimed`, `server_session` — and nothing else, because a refusal may not
assert what the server rejected. The shape is fixed and an unknown field is
refused, because a log that accepts anything documents nothing.

Neither of the two questions is a new idea. `kb_query` already takes
`caller_id` and `purpose`; a `kb_gap` already keeps `asked_by`. So a question
that **failed** was already attributable while a question that **succeeded** was
not, and this closes that asymmetry rather than adding a concept.

**`caller_id` is carried here, not verified here.** It takes four forms —
`<qid>:v<N>:<config>:<axis>`, `<qid>:v<N>:s2`, `<qid>:v<N>:operator`, and
`bridge:<thread>:r<N>` — and the launcher issues it rather than the sub-agent
choosing it (§4.3.1), which is what makes the "who" worth writing down. What
this directory cannot do is check it: the server sees an argument, not an
identity, so a line says which id was passed and not which process passed it.
Anything verified against this field is corroborated by the log rather than
proved by it, and saying so is cheaper than a reader assuming the stronger
claim. It was written as one form until 2026-09-19, which is the same
abridgement that left a bridge caller unable to see why it had been refused.

`server_session` is the part the server does observe: which of its own runs
answered. It identifies no caller. What it gives is that lines sharing it came
from one process — the distinction that was missing on 2026-09-19, when three
lines one second apart carried three seats' ids and nothing could tell three
callers from one harness iterating over three names.

`purpose` and the `caller_id` pattern are read live out of `contracts/`, never
copied. A second copy of a registry is a registry that drifts.

## The one rule

**Global statistics never touch the answer** (§4.3.1). A store that notices what
its callers ask starts answering with what is popular, and that breaks two
things at once: determinism, and caller isolation — a sibling's query would
become visible in another sibling's answer.

The enforcement is structural, not a comment. `query_log.py` offers `record`
(write) and `verify` (offline audit) and **no function that reads the log by
caller, by observable or by count**. There is nothing here for answering code to
call.

## What it buys beyond the audit trail

§4.3.1 requires the same `(query, kb_version)` to give the same answer forever,
and nothing checked that. Recording the answer beside the query makes the
violation visible: two lines, one query, one version, different returns.

```bash
python3 librarian_agent/src/query_log.py --verify
python3 librarian_agent/src/query_log.py --self-test
```
