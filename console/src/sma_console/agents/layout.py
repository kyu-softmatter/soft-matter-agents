"""Where the microscope's run-side folders are: one rule, in one place (console card 005).

plan.md 15 moves them out of `microscope_agent/` in two steps: `runs/` went to
`microscope_runtime/runs/` in card 080, and `approvals/` goes to `microscope_runtime/approvals/`
later, in the person's own commit. The shapes do not change, only the folders. So, for the
microscope seat, each of `runs` and `approvals` is read from `microscope_runtime/<folder>/` when
that folder exists, and otherwise from `microscope_agent/<folder>/`. Each folder is decided on its
own, so the time between the two steps reads correctly: runs moved, approvals not yet. The
simulation seat keeps `simulation_agent/` for both, and the questions, the inbox and the plan
cards stay in `<seat>_agent/`.

The old place is for a tree from before the move, such as a scratch copy made earlier or the
mock sample. It is a display-side branch: nothing here enforces anything, and no reader that
does is involved. Once the person's step 6 has landed, a later card removes it.

One folder is read, never both: two places are not merged, because a run listed from either one
would then look like the other's. A reader asks `run_side_folder` and nothing else; none keeps a
path of its own.
"""

from __future__ import annotations

from pathlib import Path

RUNTIME_FOLDER = "microscope_runtime"
RUN_SIDE_FOLDERS = ("runs", "approvals")


def run_side_folder(root: str | Path, agent: str, folder: str) -> Path | None:
    """The directory of `agent`'s `runs` or `approvals`, or None when it is not there.

    Microscope: `microscope_runtime/<folder>/` if that directory exists, else
    `microscope_agent/<folder>/` if that does. Anything else: `<agent>_agent/<folder>/`."""
    if folder not in RUN_SIDE_FOLDERS:
        raise ValueError(f"not a run-side folder: {folder!r}")
    base = Path(root)
    candidates = ([base / RUNTIME_FOLDER / folder, base / "microscope_agent" / folder]
                  if agent == "microscope" else [base / f"{agent}_agent" / folder])
    return next((c for c in candidates if c.is_dir()), None)
