"""The four judgements of plan.md 13.5, record-only (card 081): DM-1, DM-2 and DM-4 here, DM-3 in the watcher.

IT IS HANDED DATA AND HANDS BACK EVENTS, AND THAT IS ALL IT CAN DO. Like the watcher it holds no device
module, no core, no reference to abort, the stop channel, dispatch or the prompt to the person, and it
imports none of them, so no answer can reach any of them: what an answer may do is a question of what this
object can reach, not of what it chooses. The orchestrator tells it that the run reached a point, hands it
the run's frames (the tee that feeds the frame tap and the pre-stop buffer) and, after a stop's abort and
save, the saved window; it puts its events in an outbox and the orchestrator records them.

THERE IS NO THRESHOLD, NO ACTION ON AN ANSWER AND NO PROMPT FOR THE PERSON (13.5: every judgement records only
until the person has chosen its threshold from the record). An answer is written down as the model gave it,
checked against the plan's lists and never beyond them: a code the plan did not declare, a YES that names
`unknown`, an `OK` with no answer are an `ERROR` record. A question never holds up the run: it is asked on its
own thread, and what is still open when the run ends is written as an `ERROR` and its late answer dropped.

DM-1 and DM-2 are asked at every point the plan names that the run reaches, normal ones included, so a
false-alarm rate can later be counted; DM-4 only through `stopped()`, which the orchestrator calls after the
abort has finished and the buffer is saved. Images are card 076's reduced copies and nothing else: the
backend never gets a raw frame. The backend is the watcher's interface with one more method, `judge`, and is a
RUN argument, never a plan field.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import re
import sys
import threading
import time
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)                             # type: ignore[union-attr]
    return module


W = _load("_watcher_for_judgements", _HERE / "watcher.py")
R = W.R
make_backend = W.make_backend

#: What the questions below are versioned by. A plan's own `prompt_version` is keyed with it, the
#: judgement and the plan, so each answer replays against the words that were asked.
JUDGEMENTS_VERSION = "judgements-1"

QUESTIONS = {
    "DM-1": "Are the particles the fixed code detected suitable for the planned measurement?",
    "DM-2": "Is this field of view suitable for the measurement that is about to start?",
    "DM-4": "Can the cause of this stop be identified from the evidence given, and as which of the listed causes?",
}
#: The plan's block key for each judgement, in the order a point asks them.
KEYS = (("dm1", "DM-1"), ("dm2", "DM-2"), ("dm4", "DM-4"))

#: The point a stop is, which only `stopped()` reaches and DM-4 alone may name.
STOP_POINT = "stop"

#: How long `close()` waits for open questions when the caller names no time. A code choice, not a plan
#: number: the judgements block has no question budget (the watcher's is its own), and a question that is
#: still open at the end of the run is recorded as unanswered either way.
CLOSE_WAIT_S = 2.0

_CODE = re.compile(r"^[a-z][a-z0-9_]*$")


class BlockRefused(ValueError):
    """The plan's judgements block cannot be asked as written; the judgements are off, the run goes on."""


def check_block(block) -> None:
    """Judge the block by what the plan schema says of it. Raises BlockRefused naming the field."""
    if not isinstance(block, dict) or not block:
        raise BlockRefused("judgements is not an object with at least one of dm1, dm2, dm4")
    extra = set(block) - {k for k, _ in KEYS}
    if extra:
        raise BlockRefused(f"judgements names {sorted(extra)}, which are not judgements the plan may declare")
    for key, judgement in KEYS:
        if key not in block:
            continue
        b = block[key]
        if not isinstance(b, dict):
            raise BlockRefused(f"{key} is not an object")
        points = b.get("points")
        if not (isinstance(points, list) and points and all(isinstance(p, str) and p for p in points)):
            raise BlockRefused(f"{key}.points must be a non-empty list of point names")
        if not (isinstance(b.get("prompt_version"), str) and b["prompt_version"]):
            raise BlockRefused(f"{key}.prompt_version must be a non-empty text")
        frames = b.get("frames")
        if not (isinstance(frames, dict) and isinstance(frames.get("given"), bool)):
            raise BlockRefused(f"{key}.frames.given must be true or false")
        if frames["given"]:
            try:
                R.check_conversion(frames.get("conversion"))
            except R.RenderRefused as exc:
                raise BlockRefused(f"{key}.frames.conversion: {exc}") from None
        list_key = "cause_labels" if key == "dm4" else "reason_codes"
        codes = b.get(list_key)
        if not (isinstance(codes, list) and codes and all(isinstance(c, str) and _CODE.match(c) for c in codes)
                and len(set(codes)) == len(codes)):
            raise BlockRefused(f"{key}.{list_key} must be a non-empty list of distinct lower-case names")
        if key == "dm4" and ("unknown" not in codes or len(codes) < 2):
            raise BlockRefused("dm4.cause_labels must list `unknown` and at least one cause beside it")


def _backend_record(backend) -> dict:
    return {"name": backend.name, "version": backend.version, "kind": backend.kind}


def prompt_version(key: str, plan: dict, block: dict) -> str:
    """Keyed by judgement and plan: the same text asked of a different plan is a different version."""
    return f"{key}/{plan.get('id')}/r{plan.get('revision')}/{block['prompt_version']}/{JUDGEMENTS_VERSION}"


def build(plan: dict, backend, run_folder, clock):
    """A started-able object and the event to record after run_started, or None and what to record.

    A plan with no `judgements` block builds nothing and says nothing: there is nothing declared to be silent
    about. A block that cannot be asked is `judgements_off` with the reason, and the run goes on.
    """
    block = plan.get("judgements")
    if block is None:
        return None, None
    try:
        check_block(block)
    except BlockRefused as exc:
        return None, {"event": "judgements_off", "from": "judgements", "t_mono": clock(),
                      "judgements": {"why": "did_not_start", "detail": str(exc)}}
    judgements = Judgements(plan, block, backend, Path(run_folder), clock)
    body = {"backend": _backend_record(backend), "questions_version": JUDGEMENTS_VERSION}
    for key, _ in KEYS:
        if key in block:
            body[key] = {"points": list(block[key]["points"]), "prompt_version": prompt_version(key, plan, block[key])}
    return judgements, {"event": "judgements_started", "from": "judgements", "t_mono": clock(), "judgements": body}


def _usable(frame) -> bool:
    try:
        a = np.asarray(frame)
    except Exception:                                           # noqa: BLE001
        return False
    return a.ndim == 2 and a.dtype.kind in "uif" and min(a.shape) >= 1


class _Open:
    """One question in flight."""

    __slots__ = ("seq", "key", "judgement", "version", "done", "closed")

    def __init__(self, seq, key, judgement, version):
        self.seq, self.key, self.judgement, self.version = seq, key, judgement, version
        self.done = self.closed = False


class Judgements:
    def __init__(self, plan: dict, block: dict, backend, folder: Path, clock) -> None:
        self._plan_id, self._revision = plan.get("id"), plan.get("revision")
        self._blocks = {key: block[key] for key, _ in KEYS if key in block}
        self._versions = {key: prompt_version(key, plan, b) for key, b in self._blocks.items()}
        self._backend = backend
        self._folder = Path(folder)
        self._clock = clock
        self._lock = threading.Lock()
        self._outbox: list[dict] = []
        self._open: dict[int, _Open] = {}
        self._threads: list[threading.Thread] = []
        self._next_seq = 1
        self._latest: tuple | None = None           # (copy, frame index, t_mono)
        self._frames_seen = 0
        self._wants_frames = any(b["frames"]["given"] for b in self._blocks.values()) or "watcher" in plan
        self.reached: dict[str, int] = {}
        self.failure: str | None = None
        self._watcher_block, self._ceiling, self._ceiling_why = None, None, None
        wb = plan.get("watcher")
        if wb is None:
            self._ceiling_why = "the plan declares no watcher block, so no camera ceiling is stated"
        else:
            try:
                R.check_plan_block(wb)
                self._ceiling, gap = R.resolve_ceiling(wb, plan)
                self._watcher_block = wb
                if self._ceiling is None:
                    self._ceiling_why = f"the camera ceiling is the gap {gap!r}, so saturated pixels cannot be marked"
            except R.RenderRefused as exc:
                self._ceiling_why = f"the plan's watcher block cannot be rendered: {exc}"
        self._gap = None if self._ceiling is not None else self._ceiling_why

    # -- what the run hands in -------------------------------------------------------------------------- #

    def start(self) -> None:
        pass

    def put_frame(self, image, metadata, t_mono: float) -> None:
        """Keep a copy of the latest frame, only when something here could use it."""
        index = self._frames_seen
        self._frames_seen += 1
        if not self._wants_frames:
            return
        kept = image.copy() if hasattr(image, "copy") else bytes(image)
        with self._lock:
            self._latest = (kept, index, float(t_mono))

    def reach(self, point: str, t_mono: float | None = None) -> None:
        """The run is at `point`: DM-1 and DM-2 are asked wherever the plan names it."""
        with self._lock:
            self.reached[point] = self.reached.get(point, 0) + 1
            latest = self._latest
        if self._backend.kind == "none":
            return                                              # the none backend asks nobody
        for key, judgement in KEYS[:2]:
            block = self._blocks.get(key)
            if block is not None and point in block["points"]:
                self._ask(key, judgement, point, latest, None, None)

    def stopped(self, reason: str, window: list, saved, recent: list, t_mono: float) -> None:
        """A stop's abort has finished and its buffer is saved: DM-4 is asked, if the plan names the stop."""
        with self._lock:
            self.reached[STOP_POINT] = self.reached.get(STOP_POINT, 0) + 1
        if self._backend.kind == "none":
            return
        block = self._blocks.get("dm4")
        if block is not None and STOP_POINT in block["points"]:
            self._ask("dm4", "DM-4", STOP_POINT, None, window, {"reason": reason, "saved": saved, "recent": recent})

    def unreached(self) -> dict:
        """The points the plan names that the run never reached (the stop point is a stop's and is not listed)."""
        out = {}
        for key, block in self._blocks.items():
            missing = [p for p in block["points"] if p != STOP_POINT and p not in self.reached]
            if missing:
                out[key] = missing
        return out

    # -- what comes back -------------------------------------------------------------------------------- #

    def drain(self) -> list[dict]:
        with self._lock:
            out, self._outbox = self._outbox, []
        return out

    def close(self, wait_s: float | None = None) -> None:
        """Wait for open questions up to `wait_s`; what is still open is an ERROR and its late answer is dropped."""
        deadline = time.monotonic() + (CLOSE_WAIT_S if wait_s is None else wait_s)
        for thread in list(self._threads):
            thread.join(max(0.0, deadline - time.monotonic()))
        with self._lock:
            still = [o for o in self._open.values() if not o.done]
            for o in still:
                o.closed = True
        for o in still:
            self._emit_answer(o, {"status": "ERROR", "error": "the run ended before the backend answered"}, forced=True)

    # -- asking ----------------------------------------------------------------------------------------- #

    def _emit(self, event: dict) -> None:
        with self._lock:
            self._outbox.append(event)

    def _ask(self, key, judgement, point, latest, window, stop) -> None:
        block = self._blocks[key]
        seq = self._next_seq
        self._next_seq += 1
        asked_t = self._clock()
        codes = list(block["cause_labels"] if key == "dm4" else block["reason_codes"])
        version = self._versions[key]
        images, images_note = self._images(seq, block, latest, window)
        text = self._context(key, judgement, point, version, codes, asked_t, latest, images, images_note, stop)
        context_name = f"judgement_{seq:06d}_context.txt"
        data = text.encode("utf-8")
        (self._folder / context_name).write_bytes(data)
        request = {"judgement": judgement, "seq": seq, "point": point, "prompt_version": version,
                   "allowed_answers": ["YES", "NO"], "allowed_codes": codes,
                   "images": [{k: v for k, v in img.items() if k in ("role", "frame_index", "sha256", "path")}
                              for img in images],
                   "context_sha256": "sha256:" + hashlib.sha256(data).hexdigest(), "context_path": context_name,
                   "asked_t_mono": asked_t}
        entry = _Open(seq, key, judgement, version)
        with self._lock:
            self._open[seq] = entry
        self._emit({"event": "judgement_asked", "from": f"judgements.{key}", "t_mono": asked_t, "judgement": request})
        thread = threading.Thread(target=self._work, args=(entry, text, codes, copy.deepcopy(images) or None),
                                  name=f"judgement-{seq}", daemon=True)
        self._threads.append(thread)
        thread.start()

    def _work(self, entry: _Open, text: str, codes: list, images) -> None:
        try:
            raw = self._backend.judge(entry.judgement, text, list(codes), images)
            payload = self._normalise(entry.judgement, codes, raw)
        except Exception as exc:                                # noqa: BLE001 - a backend failure is a record
            payload = {"status": "ERROR", "error": f"{type(exc).__name__}: {exc}"}
        self._emit_answer(entry, payload)

    def _emit_answer(self, entry: _Open, payload: dict, forced: bool = False) -> None:
        with self._lock:
            if entry.done or (entry.closed and not forced):
                return                                          # answered once already, or a late answer: dropped
            entry.done = True
        body = {"judgement": entry.judgement, "seq": entry.seq, **payload,
                "model": _backend_record(self._backend), "prompt_version": entry.version,
                "answered_t_mono": self._clock()}
        self._emit({"event": "judgement_answered", "from": f"judgements.{entry.key}", "t_mono": body["answered_t_mono"],
                    "judgement": body})

    @staticmethod
    def _normalise(judgement: str, allowed: list, raw) -> dict:
        """The backend's answer as the schema's response, or an ERROR saying how it did not fit. Nothing else gets in."""
        def error(why):
            return {"status": "ERROR", "error": f"the backend's answer does not fit the shape: {why}"}

        if not isinstance(raw, dict):
            return error(f"{type(raw).__name__} is not an object")
        status = raw.get("status")
        if status == "ERROR":
            return {"status": "ERROR", "error": str(raw.get("error") or "the backend reported an error")}
        if status == "ABSTAIN":
            return {"status": "ABSTAIN"}
        if status != "OK":
            return error(f"status {status!r} is not OK, ABSTAIN or ERROR")
        answer = raw.get("answer")
        if answer not in ("YES", "NO"):
            return error(f"an OK answer is YES or NO, not {answer!r}")
        out = {"status": "OK", "answer": answer}
        if judgement == "DM-4":
            label = raw.get("cause_label")
            if answer == "YES":
                if label == "unknown":
                    return error("a YES that names `unknown`: unknown is a NO, never a cause")
                if label not in allowed:
                    return error(f"a YES names the cause {label!r}, which is not one of {allowed}")
            elif label is not None and label != "unknown":
                return error(f"a NO names the cause {label!r}; only `unknown` goes with a NO")
            if label is not None:
                out["cause_label"] = label
        else:
            codes = raw.get("reason_codes", [])
            if not (isinstance(codes, list) and all(isinstance(c, str) for c in codes)):
                return error("reason_codes is not a list of names")
            outside = [c for c in codes if c not in allowed]
            if outside:
                return error(f"reason code(s) {outside} are not the plan's {allowed}")
            out["reason_codes"] = list(codes)
        score = raw.get("score")
        if score is not None:
            if not (isinstance(score, dict) and set(score) == {"kind", "value"} and isinstance(score["kind"], str)
                    and _CODE.match(score["kind"]) and isinstance(score["value"], (int, float))
                    and not isinstance(score["value"], bool)):
                return error("score is not {kind, value}")
            out["score"] = {"kind": score["kind"], "value": score["value"]}
        return out

    # -- what is given ---------------------------------------------------------------------------------- #

    def _images(self, seq: int, block: dict, latest, window):
        """The reduced images (card 076's conversion), written whole, or [] and the reason there are none."""
        if not block["frames"]["given"]:
            return [], "the plan does not give images to this judgement"
        if self._ceiling is None:
            return [], f"no image was made: {self._ceiling_why}"
        conversion = block["frames"]["conversion"]
        if window is not None:
            pairs = [(f"pre_stop_{i:03d}", entry[0], entry[2]) for i, entry in enumerate(window)]
            if not pairs:
                return [], "the pre-stop buffer holds no frame, so there is no image"
        else:
            if latest is None:
                return [], "no frame has arrived in this run yet, so there is no current image"
            pairs = [("current", latest[1], latest[0])]
        made = []
        try:
            for role, index, frame in pairs:
                if not _usable(frame):
                    return [], "no image was made: a frame that is not a 2-D numeric image cannot be reduced"
                data, info = R.convert_frame(np.asarray(frame), conversion, self._ceiling)
                made.append((role, index, data, info))
        except R.RenderRefused as exc:
            return [], f"no image was made: {exc}"
        out = []
        for role, index, data, info in made:
            name = f"judgement_{seq:06d}_{role}.png"
            (self._folder / name).write_bytes(data)
            out.append({"role": role, "frame_index": index, "sha256": "sha256:" + info["sha256"], "path": name,
                        "png": data})
        return out, None

    def _detections(self, latest) -> list[str]:
        wb = self._watcher_block
        if wb is None:
            return [f"none: {self._ceiling_why}"]
        frame = None if latest is None else latest[0]
        why = None
        if latest is None:
            why = "no frame has arrived in this run yet"
        elif not _usable(frame):
            why = "the latest frame is not a 2-D numeric image"
            frame = None
        try:
            values = R.image_values({"block": wb, "frame": None if frame is None else np.asarray(frame),
                                     "frame_index": None if latest is None else latest[1],
                                     "ceiling": self._ceiling, "ceiling_gap": self._gap, "level": None,
                                     "level_absent_because": "not tracked for the judgements", "reference": None,
                                     "no_frame_because": why})
        except Exception as exc:                                # noqa: BLE001 - a missing context is said, not fatal
            return [f"none: the fixed detections could not be computed: {type(exc).__name__}: {exc}"]
        lines = []
        for name in R.FRAME_VALUES + ("particle_count",):
            v = values.get(name)
            if v is None:
                continue
            if v["value"] is None:
                lines.append(f"{name}: absent ({v.get('absent_because')})")
            else:
                lines.append(f"{name}: {v['value']} {v['unit']} (method {v['method']}, frame {v['frame_index']})")
        return lines

    def _context(self, key, judgement, point, version, codes, asked_t, latest, images, images_note, stop) -> str:
        lines = [f"judgement: {judgement}", f"question: {QUESTIONS[judgement]}",
                 f"plan: {self._plan_id} revision {self._revision}", f"point: {point}",
                 f"prompt_version: {version}", "allowed answers: YES, NO",
                 ("allowed cause labels (`unknown` is a NO, never a cause): " if judgement == "DM-4"
                  else "allowed reason codes: ") + ", ".join(codes),
                 f"asked at t_mono: {asked_t}", ""]
        if judgement == "DM-4":
            saved = stop["saved"]
            lines += [f"stop reason: {stop['reason']}"]
            if isinstance(saved, dict) and saved.get("path"):
                lines.append(f"saved evidence: {saved['frames']} frame(s) of the last {saved['length_s']} s in "
                             f"{saved['path']} ({saved['sha256']})")
            elif isinstance(saved, dict):
                lines.append(f"saved evidence: nothing was saved ({saved.get('why')})")
            else:
                lines.append("saved evidence: nothing was saved (the plan states no pre-stop buffer)")
            lines += ["events before the stop, oldest first:"] + [f"  {name}" for name in stop["recent"]]
        else:
            lines += ["fixed detections on the latest frame:"] + [f"  {line}" for line in self._detections(latest)]
        lines.append("")
        if images:
            lines.append("images (reduced copies, the raw frame never leaves):")
            lines += [f"  {img['role']}: frame {img['frame_index']}, {img['sha256']}" for img in images]
        else:
            lines.append(f"images: none ({images_note})")
        return "\n".join(lines) + "\n"
