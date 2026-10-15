/** Small pieces shared by the console panels. */

import { type ReactNode, useEffect, useState } from "react";

export interface LoadState<T> {
  data?: T;
  error?: string;
}

export function errorText(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

/** Run `load` when `deps` change (open, Refresh); no polling. Stale answers are dropped. */
export function useLoad<T>(load: () => Promise<T>, deps: readonly unknown[]): LoadState<T> {
  const [state, setState] = useState<LoadState<T>>({});
  useEffect(() => {
    let live = true;
    setState({});
    load().then(
      (data) => live && setState({ data }),
      (e: unknown) => live && setState({ error: errorText(e) }),
    );
    return () => {
      live = false;
    };
  }, deps); // the caller names what the load depends on
  return state;
}

export function Loaded<T>({ state, children }: { state: LoadState<T>; children: (data: T) => ReactNode }) {
  if (state.error !== undefined) return <p role="alert" className="console-error">{state.error}</p>;
  if (state.data === undefined) return <p className="console-muted">Loading…</p>;
  return <>{children(state.data)}</>;
}

export function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

export function asArray(v: unknown): unknown[] {
  return Array.isArray(v) ? v : [];
}

/** A value as the file has it: strings and numbers verbatim, anything else as compact JSON. */
export function show(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "string") return v;
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  return JSON.stringify(v);
}

export function Json({ label, value }: { label: string; value: unknown }) {
  return (
    <details className="console-json">
      <summary>{label}</summary>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}

/** Label/value rows for the fields of `obj` that are present. */
export function Fields({ obj, keys }: { obj: Record<string, unknown>; keys: readonly string[] }) {
  const present = keys.filter((k) => obj[k] !== undefined && obj[k] !== null);
  if (present.length === 0) return null;
  return (
    <dl className="console-fields">
      {present.map((k) => (
        <div key={k}>
          <dt>{k}</dt>
          <dd>{show(obj[k])}</dd>
        </div>
      ))}
    </dl>
  );
}

/** `vN`: version 1 is the unprefixed file, N a `vN_` prefix. No fixed set (v4_, v5_ exist). */
export function versionLabel(v: number): string {
  return `v${v}`;
}

export function shortTime(t: string | null | undefined): string {
  if (!t) return "—";
  return t.replace("T", " ").replace(/(\.\d+)?(Z|[+-]\d\d:\d\d)$/, "");
}
