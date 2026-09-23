"""One revision of a card stops destroying the one before it (P9, 4.5.5).

A card that sits on one path loses every revision to the next one, and other
artifacts NAME the revision they read: a run log names the plan it carried
out, and a plan pins the goal it was built against. Three run logs already
name plan revisions that exist in no tree, which check 66 reports as `LOST`
-- not PENDING, because it existed and a run executed it and it was replaced.

This module is the convention, in one place, because it is needed from two
and they are not alike. `plan_card.py` calls it on its own write path. The
GOAL card has no generator -- a person and a seat edit it by hand -- so the
convention has to be runnable by hand too, or it becomes a step that depends
on whoever remembers it, which is the class of failure this repository keeps
finding: the DRAFT-to-VALIDATED promotion and the Markdown regeneration are
both already in it.

    python3 src/card_revision.py questions/<qid>/goal.json

Nothing here decides WHETHER to revise. It moves aside what a revision is
about to destroy, and it refuses when it cannot do that honestly.
"""

from __future__ import annotations

import os
import sys

# THE SHADOW SCRUB, AND EVERY SCRIPT IN src/ CARRIES IT. `python3
# src/card_revision.py` puts src/ at the head of sys.path, and argparse's own
# import chain reaches `operator` -- which lands on this directory's
# operator.py, mid-way through its body.
#
# The rule rather than a count, because I wrote a count here and it was
# wrong: this said FOUR modules, and four is what operator.py's comment
# names. I read a comment and reported it as a measurement, on the day after
# being told not to count off prose -- a comment IS prose. Count it instead:
#
#   grep -l 'sys\.path\[:\] = \[p for p in sys\.path' src/*.py
#
# The rule that run gives: every module in src/ with a `__main__` carries
# this, and the only one without it is orchestrator.py, which is never run as
# a script. So the workaround is not a handful of special cases -- it is the
# condition of being executable in this directory at all, which is a stronger
# argument for renaming operator.py than any number was. plan.md 7 fixes that
# filename and it is the design seat's.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]

import argparse                                                  # noqa: E402
import json                                                      # noqa: E402
from pathlib import Path                                         # noqa: E402


class DisplaceError(RuntimeError):
    """The displaced copy cannot be written honestly, so nothing is written."""

def displace(live: Path) -> list[str]:
    """Move the revision about to be overwritten aside, under a `v<N>_` prefix.

    A plan card sat on ONE path, so every revision destroyed the one before
    it -- and a run log names the plan it carried out, so three run logs now
    name revisions that exist in no tree. Check 66 reads that as `LOST`: not
    PENDING, because it existed and a run executed it and it was replaced.

    THE PREFIX GOES ON THE DISPLACED COPY AND NOT ON THE LIVE ONE, which is
    what makes this cost nothing: `plan_microscope_<qid>.json` keeps its
    name, so the bridge and `--plan` read exactly what they read today and
    the convention only ADDS files. Both this seat and manager-microscope
    priced it as a contract change and sent it upward; architecture saw that
    displacing rather than renaming makes it one-sided.

    It is the axis cards' convention, which already keeps `v2_axis_*` beside
    the live seven for the same reason (4.5.5, P9).

    NOTHING IS OVERWRITTEN HERE EITHER. A displaced copy that already exists
    is left alone and the write refuses rather than replacing it -- two
    different bodies under one `v<N>_` name would recreate the defect one
    directory along, and the second one would be the lie.
    """
    if not live.exists():
        return []
    previous = json.loads(live.read_text())
    revision = previous.get("revision")
    if not isinstance(revision, int):
        raise DisplaceError(f"{live.name} carries revision {revision!r}, so the copy it would be "
                        "displaced into cannot be named. A card with no revision is one no run "
                        "log can name either")
    said = []
    for path, body in ((live, live.read_text()),
                       (live.with_suffix(".md"),
                        live.with_suffix(".md").read_text() if live.with_suffix(".md").exists()
                        else None)):
        if body is None:
            continue
        kept = path.with_name(f"v{revision}_{path.name}")
        if kept.exists():
            if kept.read_text() != body:
                raise DisplaceError(
                    f"{kept.name} already exists and differs from the revision {revision} about "
                    "to be displaced. Overwriting it would put two bodies under one name, which "
                    "is the defect this convention exists to remove, one directory along")
            said.append(f"  {kept.name} already holds revision {revision}, unchanged")
            continue
        kept.write_text(body)
        said.append(f"  displaced revision {revision} to {kept.name}")
    return said


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("card", nargs="+", help="the live card path, e.g. questions/<qid>/goal.json")
    args = ap.parse_args(argv)
    for name in args.card:
        live = Path(name)
        if not live.exists():
            print(f"  {name}: not on disk, nothing to displace", file=sys.stderr)
            continue
        said = displace(live)
        print("\n".join(said) if said else f"  {live.name}: nothing displaced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
