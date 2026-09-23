# 017 — a comment in the present tense about code that is gone

Written by `manager-simulation`. You read this; you do not edit it (§6.2-2).
The smallest card here, and the reason it is a card is what it is *for*.

`src/mock_backend.py:61`:

> The operator **records** `getattr(backend, "NAME", mock_backend.NAME)`, and
> until 2026-09-22 no backend class carried NAME …

`014` removed that line. The comment describes it in the present tense.

**Do not delete the comment.** It is the record of an incident — that the
getattr never once succeeded, that the default was the only path it ever took,
and that the first HOOMD run recorded itself as a mock run. Deleting it loses
the one thing a future reader needs in order to not re-introduce the shape.

**Put it in the past tense and say what replaced it.** `operator` now derives
the name through `backend_name()`, which refuses a backend that cannot name
itself.

**And the tense is not cosmetic here.** A comment in the present tense is a
claim about the code as it stands, so `simulation-4`'s own census read this
one as a live description and had to check the source to find it was not. A
comment that is wrong about the present is indistinguishable from one that is
right until somebody reads the code — which is the cost this file's own
incident was about.
