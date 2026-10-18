// The `patterns` area: the pattern designer (card T-20261002-2205 stage 2).
//
// A pattern is one track per target (the XYZ piezo, tweezer traps 0-7), each a list of timed
// points. Shapes (line, circle, raster, spiral, hold; z ramps from z0 to z1) fill a track; the
// points can be edited by hand as CSV. The preview draws every track coloured by time, gray at
// the start to dark green at the end, with a time slider. "Show on live view" opens the live
// view with this pattern over the camera frames. Designing moves nothing; a saved pattern can be
// run (`pattern_run`: the piezo and the traps, behind the engine's guards and rule 12).
//
// Route rest forms: "" (a new pattern) or "<pattern_id>" (that saved pattern).

import { useCallback, useEffect, useMemo, useState } from "react";

import { useClient, useReadOnly } from "../../app/client";
import {
  DEFAULT_SHAPE,
  firstProblem,
  fromCsv,
  generate,
  type PatternSummary,
  patternDuration,
  PatternCanvas,
  PatternReadout,
  PatternRunControls,
  PatternScrubber,
  type ShapeKind,
  type ShapeParams,
  TARGETS,
  targetLabel,
  type ToPx,
  toCsv,
  type Track,
} from "../../app/patterns";
import { areaHref, useAreaPath } from "../../app/route";
import { idFromName, patternsApi } from "./api";

const SIZE = 480;
const SHAPES: ShapeKind[] = ["circle", "line", "raster", "spiral", "hold"];

interface Draft {
  id: string;
  name: string;
  loop: boolean;
  notes: string;
  tracks: Track[];
}

const NEW: Draft = { id: "", name: "", loop: false, notes: "", tracks: [{ target: "piezo", points: generate(DEFAULT_SHAPE) }] };

function message(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

/** Which fields a shape uses, with labels. */
const FIELDS: Record<ShapeKind, [keyof ShapeParams, string][]> = {
  circle: [["cx", "centre x µm"], ["cy", "centre y µm"], ["r", "radius µm"], ["n", "turns"]],
  spiral: [["cx", "centre x µm"], ["cy", "centre y µm"], ["r", "outer radius µm"], ["n", "turns"]],
  line: [["cx", "from x µm"], ["cy", "from y µm"], ["x1", "to x µm"], ["y1", "to y µm"]],
  raster: [["cx", "centre x µm"], ["cy", "centre y µm"], ["r", "width µm"], ["h", "height µm"], ["n", "lines"]],
  hold: [["cx", "x µm"], ["cy", "y µm"]],
};

function Num({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <label className="pattern-num">
      {label}
      <input type="number" step="any" value={value} onChange={(e) => onChange(Number(e.target.value))} />
    </label>
  );
}

function TrackEditor({
  track,
  index,
  used,
  onChange,
  onRemove,
}: {
  track: Track;
  index: number;
  used: string[];
  onChange: (t: Track) => void;
  onRemove: () => void;
}) {
  const [shape, setShape] = useState<ShapeParams>(DEFAULT_SHAPE);
  const [csv, setCsv] = useState<string | null>(null);
  const set = (k: keyof ShapeParams, v: number | ShapeKind) => setShape((s) => ({ ...s, [k]: v }));
  const name = targetLabel(track.target);
  return (
    <fieldset className="pattern-track" aria-label={`Track ${index + 1}: ${name}`}>
      <legend>
        <select
          aria-label={`Target of track ${index + 1}`}
          value={track.target}
          onChange={(e) => onChange({ ...track, target: e.target.value })}
        >
          {TARGETS.map((t) => (
            <option key={t} value={t} disabled={t !== track.target && used.includes(t)}>
              {targetLabel(t)}
            </option>
          ))}
        </select>{" "}
        <span className="muted">
          {track.points.length} points · {patternDuration({ tracks: [track] }).toFixed(2)} s
        </span>{" "}
        <button type="button" onClick={onRemove}>
          Remove track
        </button>
      </legend>
      <div className="pattern-shape">
        <label className="pattern-num">
          shape
          <select aria-label={`Shape for track ${index + 1}`} value={shape.kind} onChange={(e) => set("kind", e.target.value as ShapeKind)}>
            {SHAPES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        {FIELDS[shape.kind].map(([k, label]) => (
          <Num key={k} label={label} value={shape[k] as number} onChange={(v) => set(k, v)} />
        ))}
        <Num label="z start µm" value={shape.z0} onChange={(v) => set("z0", v)} />
        <Num label="z end µm" value={shape.z1} onChange={(v) => set("z1", v)} />
        <Num label="duration s" value={shape.duration_s} onChange={(v) => set("duration_s", v)} />
        <Num label="points / s" value={shape.rate_hz} onChange={(v) => set("rate_hz", v)} />
        <button
          type="button"
          onClick={() => {
            onChange({ ...track, points: generate(shape) });
            setCsv(null);
          }}
        >
          Generate points
        </button>
      </div>
      <details onToggle={(e) => (e.currentTarget.open ? setCsv(toCsv(track.points)) : setCsv(null))}>
        <summary>Edit points (t s, x µm, y µm, z µm per line)</summary>
        {csv !== null && (
          <>
            <textarea
              aria-label={`Points of track ${index + 1}`}
              rows={8}
              value={csv}
              onChange={(e) => setCsv(e.target.value)}
            />
            <button type="button" onClick={() => onChange({ ...track, points: fromCsv(csv) })}>
              Apply points
            </button>
          </>
        )}
      </details>
    </fieldset>
  );
}

/** Fit every point (and at least ±10 µm) into the preview; x right, y down as on the camera image. */
function fitView(tracks: Track[]): { toPx: ToPx; span: number; cx: number; cy: number } {
  const xs = tracks.flatMap((t) => t.points.map((p) => p[1] ?? 0));
  const ys = tracks.flatMap((t) => t.points.map((p) => p[2] ?? 0));
  const lo = (v: number[], d: number) => (v.length ? Math.min(...v) : -d);
  const hi = (v: number[], d: number) => (v.length ? Math.max(...v) : d);
  const cx = (lo(xs, 10) + hi(xs, 10)) / 2;
  const cy = (lo(ys, 10) + hi(ys, 10)) / 2;
  const span = Math.max(20, hi(xs, 10) - lo(xs, 10), hi(ys, 10) - lo(ys, 10)) * 1.15;
  const k = SIZE / span;
  return { toPx: (x, y) => [SIZE / 2 + (x - cx) * k, SIZE / 2 + (y - cy) * k], span, cx, cy };
}

function grid(span: number, cx: number, cy: number) {
  return (ctx: CanvasRenderingContext2D) => {
    ctx.fillStyle = "#111";
    ctx.fillRect(0, 0, SIZE, SIZE);
    // about eight lines: a 1, 2 or 5 step
    const raw = span / 8;
    const mag = 10 ** Math.floor(Math.log10(raw));
    const step = (raw / mag < 2 ? 1 : raw / mag < 5 ? 2 : 5) * mag;
    const k = SIZE / span;
    ctx.strokeStyle = "#2a2a2a";
    ctx.lineWidth = 1;
    for (let v = Math.ceil((cx - span / 2) / step) * step; v <= cx + span / 2; v += step) {
      const x = SIZE / 2 + (v - cx) * k;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, SIZE);
      ctx.stroke();
    }
    for (let v = Math.ceil((cy - span / 2) / step) * step; v <= cy + span / 2; v += step) {
      const y = SIZE / 2 + (v - cy) * k;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(SIZE, y);
      ctx.stroke();
    }
    ctx.fillStyle = "#888";
    ctx.font = "11px sans-serif";
    ctx.fillText(`grid ${step} µm`, 6, SIZE - 6);
  };
}

export default function PatternsScreen() {
  const client = useClient();
  const api = useMemo(() => patternsApi(client), [client]);
  const readOnly = useReadOnly();
  const [rest, setRest] = useAreaPath();
  const [saved, setSaved] = useState<PatternSummary[] | null>(null);
  const [draft, setDraft] = useState<Draft>(NEW);
  const [t, setT] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const openId = rest.split("?")[0];

  const reload = useCallback(async () => {
    try {
      setSaved(await api.list());
    } catch (e) {
      setError(message(e));
    }
  }, [api]);

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    setConfirmDelete(false);
    if (!openId) {
      setDraft(NEW);
      return;
    }
    api.get(openId).then(
      (p) => {
        setDraft({ id: p.id, name: p.name, loop: p.loop ?? false, notes: p.notes ?? "", tracks: p.tracks });
        setError(null);
      },
      (e) => setError(message(e)),
    );
  }, [api, openId]);

  const duration = patternDuration(draft);
  const problem = firstProblem(draft);
  const view = useMemo(() => fitView(draft.tracks), [draft.tracks]);
  const background = useMemo(() => grid(view.span, view.cx, view.cy), [view]);
  const id = draft.id || idFromName(draft.name);
  const isSaved = !!saved?.some((p) => p.id === draft.id) && draft.id === openId;
  const blocked = readOnly.readOnly ? (readOnly.why ?? "read-only") : problem;

  const setTrack = (i: number, tr: Track) =>
    setDraft((d) => ({ ...d, tracks: d.tracks.map((x, j) => (j === i ? tr : x)) }));

  const save = async () => {
    setDone(null);
    try {
      const out = await api.save(id, { name: draft.name || id, loop: draft.loop, notes: draft.notes, tracks: draft.tracks });
      setError(null);
      setDone(`Saved ${out?.id ?? id}`);
      await reload();
      if (out) setRest(out.id);
    } catch (e) {
      setError(message(e));
    }
  };

  const remove = async () => {
    try {
      await api.remove(draft.id);
      setError(null);
      setConfirmDelete(false);
      await reload();
      setRest("");
      setDone(`Deleted ${draft.id}`);
    } catch (e) {
      setError(message(e));
    }
  };

  return (
    <section className="patterns" aria-label="Pattern designer">
      <h2>Pattern designer</h2>
      <p className="muted">
        Piezo XYZ moves are offsets from where the stage is when a run starts; trap positions are from the centre of
        the camera field. x is to the right and y down, as on the camera image (orientation provisional). Ranges are provisional until the piezo and the tweezers are measured. Nothing here moves
        hardware.
      </p>
      <div className="patterns-bar">
        <label>
          Saved{" "}
          <select
            aria-label="Saved patterns"
            value={isSaved ? draft.id : ""}
            onChange={(e) => {
              setDone(null);
              setRest(e.target.value);
            }}
          >
            <option value="">— new pattern —</option>
            {(saved ?? []).map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.duration_s.toFixed(1)} s · {p.targets.map(targetLabel).join(", ")})
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={() => {
            setDone(null);
            setDraft(NEW);
            setRest("");
          }}
        >
          New
        </button>
      </div>
      {error && (
        <p className="warn" role="alert">
          {error}
        </p>
      )}
      {done && <p role="status">{done}</p>}
      <div className="patterns-main">
        <div className="patterns-edit">
          <label className="pattern-num">
            name
            <input aria-label="Pattern name" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
          </label>
          <span className="muted"> id: {id}</span>{" "}
          <label>
            <input type="checkbox" checked={draft.loop} onChange={(e) => setDraft({ ...draft, loop: e.target.checked })} />{" "}
            loop
          </label>
          {draft.tracks.map((tr, i) => (
            <TrackEditor
              key={`${i}-${tr.target}`}
              track={tr}
              index={i}
              used={draft.tracks.map((x) => x.target)}
              onChange={(next) => setTrack(i, next)}
              onRemove={() => setDraft((d) => ({ ...d, tracks: d.tracks.filter((_, j) => j !== i) }))}
            />
          ))}
          <button
            type="button"
            disabled={draft.tracks.length >= TARGETS.length}
            onClick={() => {
              const free = TARGETS.find((x) => !draft.tracks.some((tr) => tr.target === x));
              if (free) setDraft((d) => ({ ...d, tracks: [...d.tracks, { target: free, points: generate({ ...DEFAULT_SHAPE, r: 5 }) }] }));
            }}
          >
            Add track
          </button>
          <div className="patterns-actions">
            <button type="button" disabled={blocked !== null} onClick={() => void save()}>
              Save
            </button>
            {blocked && <span className="muted"> {blocked}</span>}
            {!blocked && !isSaved && saved?.some((p) => p.id === id) && (
              <span className="warn"> Saving replaces the saved pattern {id}.</span>
            )}
            {isSaved && (
              <>
                <a href={areaHref("live", `?pattern=${encodeURIComponent(draft.id)}`)}>Show on live view</a>
                {confirmDelete ? (
                  <>
                    <span className="warn"> Delete {draft.id}?</span>
                    <button type="button" onClick={() => void remove()}>
                      Confirm delete
                    </button>
                    <button type="button" onClick={() => setConfirmDelete(false)}>
                      Cancel
                    </button>
                  </>
                ) : (
                  <button type="button" disabled={readOnly.readOnly} onClick={() => setConfirmDelete(true)}>
                    Delete
                  </button>
                )}
              </>
            )}
          </div>
        </div>
        <div className="patterns-preview">
          <PatternCanvas
            tracks={draft.tracks}
            t={Math.min(t, duration)}
            width={SIZE}
            height={SIZE}
            toPx={view.toPx}
            background={background}
            className="pattern-canvas"
            label="Pattern preview"
          />
          <PatternScrubber duration={duration} t={Math.min(t, duration)} onTime={setT} loop={draft.loop} />
          <PatternReadout tracks={draft.tracks} t={Math.min(t, duration)} />
          {isSaved && <PatternRunControls patternId={draft.id} onTime={setT} />}
        </div>
      </div>
    </section>
  );
}
