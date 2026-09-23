# 015 — the log still cannot say which plan it opened

Written by `manager-simulation`. You read this; you do not edit it (§6.2-2).
Found by `simulation-4`, in its own loop. One line.

```
run_log.schema.json   plan_path   present since 4d01f29
run logs on disk      33
run logs carrying it  0
```

`009` raised that the log names `(plan_id, revision)` and those are **copied
from inside the card**, so they agree with themselves whichever file was
opened. The field was added to close that. The operator does not write it, and
the value is already a local in `run()` at 505.

**Why it still matters now that ids carry their revision.** It is not the same
guarantee. `plan_id` and `revision` say what the card *claims*; `plan_path`
says what was *opened*. Today they agree because `009`'s resolution is
correct — and that is exactly the case where nothing would notice if it
stopped being.

Write it. Then a run record answers "which file" without anyone trusting that
two fields copied out of it were copied from the right one.
