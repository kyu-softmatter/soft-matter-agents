import { useEffect, useMemo, useState } from "react";

import type {
  Geometry,
  GeometryField,
  GeometryRaw,
  LoadingState,
  SampleDetail,
  SampleSummary,
  ValueSource,
} from "./api";

/** A disabled-reason or refusal, next to its control (ui-spec 7.0). */
export function Reason({ text }: { text: string | null | undefined }) {
  if (!text) return null;
  return (
    <span className="sample-reason" role="note">
      {text}
    </span>
  );
}

export function sourceText(s: ValueSource): string {
  if (s.kind === "entered") return `entered by ${s.by ?? "?"} ${s.t ?? ""}`.trim();
  return s.kind === "default" ? "default" : "not set";
}

export function SampleList({
  samples,
  currentId,
  selectedId,
  onView,
  onOpen,
  openBlocked,
  reasons,
}: {
  samples: SampleSummary[];
  currentId: string | null;
  selectedId: string | null;
  onView: (id: string) => void;
  onOpen: (id: string) => void;
  openBlocked: string | null;
  reasons: Record<string, string>;
}) {
  if (samples.length === 0) return <p className="muted">No samples yet.</p>;
  return (
    <table className="sample-table">
      <thead>
        <tr>
          <th>Sample</th>
          <th>Created</th>
          <th>Hole fitted</th>
          <th>Objectives</th>
          <th>Last session</th>
          <th />
        </tr>
      </thead>
      <tbody>
        {samples.map((s) => (
          <tr key={s.sample_id} aria-selected={s.sample_id === selectedId}>
            <td>
              <button className="link" onClick={() => onView(s.sample_id)}>
                {s.sample_id}
              </button>
              {s.sample_id === currentId && <span className="tag">open</span>}
              {s.reserved && <span className="tag">reserved, no session yet</span>}
              {s.awaiting_return && <span className="tag warn">awaiting return</span>}
            </td>
            <td>{s.created ?? "unknown"}</td>
            <td>{s.fitted_at ?? "never"}</td>
            <td>{s.objectives_used.join(", ") || "none"}</td>
            <td>{s.last_session ? `${s.last_session.session_id} (${s.last_session.opened_at})` : "none"}</td>
            <td>
              <button
                disabled={openBlocked !== null || s.sample_id === currentId}
                onClick={() => onOpen(s.sample_id)}
                aria-label={`Open ${s.sample_id}`}
              >
                Open
              </button>
              <Reason text={reasons[`open:${s.sample_id}`]} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function SampleSummaryPanel({
  detail,
  canOpenFolder,
  onOpenFolder,
  folderReason,
}: {
  detail: SampleDetail;
  canOpenFolder: boolean;
  onOpenFolder: () => void;
  folderReason: string | undefined;
}) {
  const h = detail.hole;
  return (
    <section aria-label="Opened sample" className="sample-panel">
      <h3>{detail.sample_id}</h3>
      <p>
        Folder: <code>{detail.dir}</code>{" "}
        {canOpenFolder && <button onClick={onOpenFolder}>Open folder</button>}
        <Reason text={folderReason} />
      </p>
      <p>
        Hole:{" "}
        {h
          ? `${h.diameter_mm ?? "?"} mm at (${h.centre_um ? `${h.centre_um[0]}, ${h.centre_um[1]}` : "?"}) um, ` +
            `rms ${h.fit_rms_um ?? "?"} um, ` +
            `${h.n_points} points, ${h.arc_deg}° arc, fitted ${h.fitted_at ?? "unknown"}` +
            (h.status ? ` (${h.status})` : "")
          : "not traced"}
      </p>
      <p>
        Flags {detail.counts.flags} · candidates {detail.counts.candidates} · fields visited{" "}
        {detail.counts.visits} · boundary points {detail.counts.boundary_points}
      </p>
    </section>
  );
}

/** a pair while it is being typed: either half may still be empty */
type HalfPair = [number | null, number | null];
type DraftValue = GeometryRaw | HalfPair | null;
type Draft = Record<string, DraftValue>;

const isHalf = (v: DraftValue): v is HalfPair => Array.isArray(v) && (v[0] === null || v[1] === null);

function draftOf(g: Geometry): Draft {
  return Object.fromEntries(Object.entries(g.values).map(([k, v]) => [k, v.value]));
}

const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

function num(text: string): number | null {
  if (text.trim() === "") return null;
  const n = Number(text);
  return Number.isFinite(n) ? n : null;
}

function FieldInput({
  field,
  value,
  disabled,
  onChange,
}: {
  field: GeometryField;
  value: DraftValue;
  disabled: boolean;
  onChange: (v: DraftValue) => void;
}) {
  if (field.kind === "choice") {
    return (
      <select
        aria-label={field.label}
        disabled={disabled}
        value={typeof value === "string" ? value : ""}
        onChange={(e) => onChange(e.target.value === "" ? null : e.target.value)}
      >
        <option value="">not set</option>
        {(field.choices ?? []).map((c) => (
          <option key={c} value={c}>
            {c}
          </option>
        ))}
      </select>
    );
  }
  if (field.kind === "pair") {
    const pair: HalfPair = Array.isArray(value) ? value : [null, null];
    const part = (i: 0 | 1, text: string) => {
      const next: HalfPair = [...pair];
      next[i] = num(text);
      onChange(next[0] === null && next[1] === null ? null : next);
    };
    return (
      <span>
        <input
          type="number"
          aria-label={`${field.label} (first)`}
          disabled={disabled}
          value={pair[0] ?? ""}
          onChange={(e) => part(0, e.target.value)}
        />
        {" × "}
        <input
          type="number"
          aria-label={`${field.label} (second)`}
          disabled={disabled}
          value={pair[1] ?? ""}
          onChange={(e) => part(1, e.target.value)}
        />
      </span>
    );
  }
  return (
    <input
      type="number"
      aria-label={field.label}
      disabled={disabled}
      value={typeof value === "number" ? value : ""}
      onChange={(e) => onChange(num(e.target.value))}
    />
  );
}

/**
 * F3.1 geometry form. Renders whatever field list the server serves; no field
 * name appears here. Saving sends only the changed keys; the engine stamps who
 * and when, and the new sources come back with the next GET.
 */
export function GeometryForm({
  fields,
  geometry,
  blocked,
  reason,
  onSave,
}: {
  fields: GeometryField[];
  geometry: Geometry;
  blocked: string | null;
  reason: string | undefined;
  onSave: (values: Record<string, GeometryRaw | null>) => void;
}) {
  const loaded = useMemo(() => draftOf(geometry), [geometry]);
  const [draft, setDraft] = useState<Draft>(loaded);
  useEffect(() => setDraft(loaded), [loaded]);
  const changed = useMemo(
    () => Object.fromEntries(Object.entries(draft).filter(([k, v]) => !same(v, loaded[k]))),
    [draft, loaded],
  );
  const nChanged = Object.keys(changed).length;
  const half = fields.filter((f) => isHalf(changed[f.key] ?? null)).map((f) => f.label);
  const incomplete = half.length ? `Enter both values: ${half.join(", ")}` : null;
  return (
    <section aria-label="Geometry" className="sample-panel">
      <h3>Geometry</h3>
      <p className="muted">Field list is provisional (F3.1 not confirmed yet).</p>
      <table className="sample-table">
        <tbody>
          {fields.map((f) => {
            const v = geometry.values[f.key];
            return (
              <tr key={f.key} data-field={f.key}>
                <th scope="row">
                  {f.label}
                  {f.unit ? ` (${f.unit})` : ""}
                  {f.safety && (
                    <span className="tag warn" title="This value feeds a safety limit in the engine">
                      safety limit
                    </span>
                  )}
                </th>
                <td>
                  <FieldInput
                    field={f}
                    value={draft[f.key] ?? null}
                    disabled={blocked !== null}
                    onChange={(nv) => setDraft((d) => ({ ...d, [f.key]: nv }))}
                  />
                </td>
                <td className="muted" data-testid={`source-${f.key}`}>
                  {v ? sourceText(v.source) : "not set"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <button
        disabled={blocked !== null || nChanged === 0 || incomplete !== null}
        onClick={() => onSave(changed as Record<string, GeometryRaw | null>)}
      >
        Save geometry
      </button>
      <Reason text={blocked ?? incomplete ?? reason} />
    </section>
  );
}

const STEP_NAMES = { geometry: "geometry", person: "person", image: "image" } as const;

/**
 * Three-step loading check (ui-spec 7.3). "Loading confirmed" only when the
 * engine's sample view says so; the screen lists what is missing otherwise.
 */
export function LoadingCheck({
  loading,
  personBlocked,
  imageBlocked,
  reasons,
  imageStatus,
  onPerson,
  onImage,
}: {
  loading: LoadingState;
  personBlocked: string | null;
  imageBlocked: string | null;
  reasons: Record<string, string>;
  imageStatus: string | null;
  onPerson: () => void;
  onImage: () => void;
}) {
  const missing = (Object.keys(STEP_NAMES) as (keyof typeof STEP_NAMES)[]).filter((k) => !loading[k].done);
  const tick = (done: boolean) => (done ? "✓" : "○");
  const img = loading.image;
  return (
    <section aria-label="Loading check" className="sample-panel">
      <h3>Loading check</h3>
      <ol className="sample-steps">
        <li>
          {tick(loading.geometry.done)} Geometry entered
          {loading.geometry.done && loading.geometry.by && ` (${loading.geometry.by} ${loading.geometry.t ?? ""})`}
        </li>
        <li>
          {tick(loading.person.done)} Person:{" "}
          {loading.person.done ? (
            `confirmed by ${loading.person.by ?? "?"} ${loading.person.t ?? ""}`
          ) : (
            <button disabled={personBlocked !== null} onClick={onPerson}>
              Sample is on the stage
            </button>
          )}
          <Reason text={loading.person.done ? reasons.person : (personBlocked ?? reasons.person)} />
        </li>
        <li>
          {tick(img.done && img.ok === true)} Image:{" "}
          {img.done && img.ok === true ? (
            `hole edge seen, grade computed (${img.by ?? "?"} ${img.t ?? ""})`
          ) : (
            <button disabled={imageBlocked !== null || imageStatus !== null} onClick={onImage}>
              Check with an image
            </button>
          )}
          {img.done && img.ok === false && <Reason text={`image check failed (grade computed): ${img.why ?? "no reason given"}`} />}
          {imageStatus && <span className="muted"> {imageStatus}</span>}
          <Reason text={img.done && img.ok === true ? reasons.image : (imageBlocked ?? reasons.image)} />
        </li>
      </ol>
      {loading.confirmed ? (
        <p className="sample-confirmed" role="status">
          Loading confirmed (person + image)
        </p>
      ) : (
        <p className="muted" role="status">
          Loading not confirmed{missing.length ? `: missing ${missing.join(", ")}` : ""}
        </p>
      )}
    </section>
  );
}
