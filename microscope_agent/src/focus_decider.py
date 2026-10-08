"""The focus search's decider when `decided_by` is `metric_maximum` (card 063 Part A).

It picks a BRANCH and nothing else: the gate (orchestrator.run_focus_search,
card 055) derives every move from the plan, the last encoder read and that
branch. This file holds no Z, no limit and no default.

At each step it takes one frame where Z now is, scores it with the copied
`focus_classical.frame_stats`, and asks the copied `focus_verdict.from_sweep`
for a verdict over every frame the walk has taken so far, at their encoder
reads. The verdict is the branch. Every argument comes from the plan:

- `metric.name`, `metric_arguments.bin_px` and `blocks_per_side`;
- `camera_ceiling`, resolved through `numbers[]`: an entry in ADU whose
  source is `kb:`. A ceiling that names a gap REFUSES -- nothing is
  substituted for the camera's full-scale count;
- the five thresholds `from_sweep` requires, from `verdict_thresholds`.
  THAT FIELD NAME IS PROVISIONAL: plan.schema.json has no field for them yet
  (reported 2026-10-07), so a plan without it refuses here.

Until the walk has `min_frames` frames the verdict is `unsure` by its own
rule, and an unsure verdict ends a search. So while the walk is shorter
than that, the decider asks for `step_up`: the search starts at the
retracted end (range_um.min) and walks toward the coverslip, which is what
`approach_from: retract` says. This is the one choice made here rather than
by the core, and it is recorded on every such decision.

The verdict's `grade` fields are origin kinds (measured, computed), not
evidence grades. They are kept as the core wrote them, under `verdict`, and
nothing here turns them into an E-grade.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)                             # type: ignore[union-attr]
    return module


#: The five keyword arguments focus_verdict.from_sweep requires, every one the caller's.
THRESHOLD_KEYS = ("min_dynamic_range_adu", "min_contrast", "min_frames",
                  "dropout_tolerance", "max_saturated")


class DeciderRefused(RuntimeError):
    """The decider cannot be built from this plan; the search does not start."""


def resolve_ceiling(plan: dict) -> int:
    """camera_ceiling -> a whole number of ADU from numbers[], or DeciderRefused."""
    fs = plan.get("focus_search") or {}
    ref = fs.get("camera_ceiling") or {}
    if "gap" in ref:
        raise DeciderRefused(
            f"camera_ceiling is the gap {ref['gap']!r}: the camera's full-scale count is not "
            "known, and the search refuses rather than substitute a value")
    name = ref.get("number")
    entry = next((n for n in plan.get("numbers") or [] if n.get("name") == name), None)
    if entry is None:
        raise DeciderRefused(f"camera_ceiling names {name!r}, which is not in numbers[]")
    if entry.get("unit") != "ADU" or not str(entry.get("source", "")).startswith("kb:"):
        raise DeciderRefused(f"numbers[{name}] must be in ADU with a kb: source; it is "
                             f"{entry.get('unit')!r} from {entry.get('source')!r}")
    value = entry.get("value")
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise DeciderRefused(f"numbers[{name}] = {value!r} is not a whole number of ADU >= 1")
    return value


class MetricMaximumDecider:
    """decide(last_read_um) -> {"branch", "confidence", "note"}, from the copied core.

    `grab()` returns (frame, metadata) for one frame at the current Z; the
    caller supplies it from the run's own acquisition, so this file reaches no
    camera.
    """

    def __init__(self, plan: dict, grab) -> None:
        fs = plan.get("focus_search") or {}
        if fs.get("decided_by") != "metric_maximum":
            raise DeciderRefused(f"decided_by is {fs.get('decided_by')!r}; only metric_maximum "
                                 "is built, and a model's branch has no place here yet")
        self.ceiling = resolve_ceiling(plan)
        given = fs.get("verdict_thresholds")
        if not isinstance(given, dict) or set(given) != set(THRESHOLD_KEYS):
            raise DeciderRefused(
                "the verdict's thresholds are not in the plan: focus_verdict.from_sweep takes "
                f"{list(THRESHOLD_KEYS)}, each the caller's with no default, and the plan "
                "schema has no field for them yet")
        self.thresholds = dict(given)
        args = fs.get("metric_arguments") or {}
        self.metric = (fs.get("metric") or {}).get("name")
        self.bin_px = args.get("bin_px")
        self.blocks_per_side = args.get("blocks_per_side")
        self.grab = grab
        self.classical = _load("_mic_focus_classical_for_decider", _HERE / "focus_classical.py")
        self.verdict = _load("_mic_focus_verdict_for_decider", _HERE / "focus_verdict.py")
        self.z: list[float] = []
        self.stats: list = []
        self.records: list[dict] = []

    def __call__(self, last_read_um: float) -> dict:
        image, _meta = self.grab()
        stats = self.classical.frame_stats(image, self.metric, ceiling=self.ceiling,
                                           bin_px=self.bin_px)
        self.z.append(float(last_read_um))
        self.stats.append(stats)
        verdict = self.verdict.from_sweep(self.z, self.stats, **self.thresholds)
        record = verdict.as_record()
        branch, note = record["verdict"], record["reason"]
        if len(self.stats) < self.thresholds["min_frames"] and branch == "unsure":
            branch = "step_up"
            note = (f"{len(self.stats)} of the {self.thresholds['min_frames']} frames the verdict "
                    "needs: walking up from the retract, as approach_from says (the decider's own "
                    f"choice, not the core's). The core said: {record['reason']}")
        self.records.append({"z_um": float(last_read_um), "score": stats.score,
                             "verdict": record, "branch": branch})
        return {"branch": branch, "confidence": None, "note": note}
