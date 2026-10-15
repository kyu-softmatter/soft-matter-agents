/**
 * Plottable data from a qid's records. The numbers are the numbers in the cards and run
 * records; this file only finds them and pairs them up.
 *
 * Conventions (user, 2026-10-02):
 * - A dataset is any JSON object holding two or more numeric arrays of the same length. Its
 *   columns are those arrays. An optional `x_name` string names the x column, an optional
 *   `units` object gives a unit per column.
 * - A column named `<y>_theory` or `theory_<y>` is the theory for `<y>` and is drawn dashed on
 *   the same x. A column named `theory` is the theory for `y` when there is one, else for the
 *   dataset's only measured column.
 * - A goal target `{metric, kind, value, unit}` is drawn as a horizontal dashed line on a plot
 *   of `metric` only when its kind names a value (`DRAWN_TARGET_KINDS`); the other kinds are
 *   tolerances or decisions (decade_resolution, detection, ...) and are listed, not drawn.
 */

export type Num = number | null;

export interface Column {
  name: string;
  values: Num[];
  unit?: string;
}

export interface Dataset {
  /** unique within the qid: source + path */
  id: string;
  /** where it came from: a card name or `<run_id>/<record>` */
  source: string;
  /** the path inside that JSON, "" for the top level */
  path: string;
  columns: Column[];
  /** the x column's name */
  x: string;
  note?: string;
}

export interface Target {
  metric: string;
  kind: string;
  value: number;
  unit: string;
  drawn: boolean;
}

export const DRAWN_TARGET_KINDS = ["value", "theory", "expected", "reference", "target"] as const;

const X_HINTS = [/^x$/i, /^t$/i, /time/i, /^lag/i, /^q$/i, /^z/i, /^dwell/i];
const MAX_DEPTH = 8;

function numericArray(v: unknown): Num[] | null {
  if (!Array.isArray(v) || v.length < 2) return null;
  let finite = 0;
  for (const e of v) {
    if (e === null) continue;
    if (typeof e !== "number") return null;
    if (Number.isFinite(e)) finite += 1;
  }
  return finite >= 2 ? (v as Num[]) : null;
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

export function isTheory(name: string): boolean {
  return name === "theory" || name.startsWith("theory_") || name.endsWith("_theory");
}

/** The measured column a theory column belongs to, or null when there is none. */
export function theoryOf(name: string, columns: readonly Column[]): string | null {
  const names = new Set(columns.map((c) => c.name));
  let base: string | null = null;
  if (name.endsWith("_theory")) base = name.slice(0, -"_theory".length);
  else if (name.startsWith("theory_")) base = name.slice("theory_".length);
  else if (name === "theory") {
    if (names.has("y")) base = "y";
    else {
      const measured = columns.filter((c) => !isTheory(c.name));
      if (measured.length === 2) base = measured[1].name; // the one that is not x
    }
  }
  return base !== null && names.has(base) ? base : null;
}

function pickX(names: string[], hinted: unknown): string {
  if (typeof hinted === "string" && names.includes(hinted)) return hinted;
  const plain = names.filter((n) => !isTheory(n));
  for (const re of X_HINTS) {
    const hit = plain.find((n) => re.test(n));
    if (hit) return hit;
  }
  return plain[0] ?? names[0];
}

function walk(v: unknown, source: string, path: string, depth: number, out: Dataset[]): void {
  if (depth > MAX_DEPTH) return;
  if (Array.isArray(v)) {
    v.forEach((e, i) => {
      if (typeof e === "object" && e !== null) walk(e, source, `${path}[${i}]`, depth + 1, out);
    });
    return;
  }
  if (!isRecord(v)) return;
  const byLength = new Map<number, Column[]>();
  const units = isRecord(v.units) ? v.units : {};
  for (const [k, child] of Object.entries(v)) {
    const arr = numericArray(child);
    if (arr) {
      const unit = units[k];
      const col: Column = typeof unit === "string" && unit !== "" ? { name: k, values: arr, unit } : { name: k, values: arr };
      const group = byLength.get(arr.length) ?? [];
      group.push(col);
      byLength.set(arr.length, group);
    } else if (typeof child === "object" && child !== null) {
      walk(child, source, path === "" ? k : `${path}.${k}`, depth + 1, out);
    }
  }
  const groups = [...byLength.values()].filter((g) => g.length >= 2);
  groups.forEach((columns, i) => {
    const suffix = groups.length > 1 ? `#${i + 1}` : "";
    const note = typeof v.theory_note === "string" ? v.theory_note : undefined;
    out.push({
      id: `${source}:${path}${suffix}`,
      source,
      path: path + suffix,
      columns,
      x: pickX(columns.map((c) => c.name), v.x_name),
      ...(note ? { note } : {}),
    });
  });
}

/** Every dataset in one JSON document. */
export function datasetsIn(data: unknown, source: string): Dataset[] {
  const out: Dataset[] = [];
  walk(data, source, "", 0, out);
  return out;
}

/** The goal card's numeric targets. */
export function targetsIn(goal: unknown): Target[] {
  if (!isRecord(goal) || !Array.isArray(goal.targets)) return [];
  const out: Target[] = [];
  for (const t of goal.targets) {
    if (!isRecord(t) || typeof t.metric !== "string" || typeof t.value !== "number") continue;
    const kind = typeof t.kind === "string" ? t.kind : "";
    out.push({
      metric: t.metric,
      kind,
      value: t.value,
      unit: typeof t.unit === "string" ? t.unit : "",
      drawn: (DRAWN_TARGET_KINDS as readonly string[]).includes(kind),
    });
  }
  return out;
}

export interface Panel {
  dataset: Dataset;
  y: Column;
  theory: Column | null;
  targets: Target[];
}

/** The basic plots: one per measured, non-x column, with its theory and drawn targets. */
export function basicPanels(datasets: readonly Dataset[], targets: readonly Target[]): Panel[] {
  const out: Panel[] = [];
  for (const d of datasets) {
    for (const y of d.columns) {
      if (y.name === d.x || isTheory(y.name)) continue;
      const theory = d.columns.find((c) => isTheory(c.name) && theoryOf(c.name, d.columns) === y.name) ?? null;
      out.push({ dataset: d, y, theory, targets: targets.filter((t) => t.drawn && t.metric === y.name) });
    }
  }
  return out;
}

export function label(c: Column): string {
  return c.unit ? `${c.name} (${c.unit})` : c.name;
}
