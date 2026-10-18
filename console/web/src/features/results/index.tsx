// The `results` area: a qid's results as plots. Read-only; it sends no command.
//
// Route rest forms:  ""  the qid list;  "<qid>"  that qid's plots and the axis explorer.
// Data: the console's read API (GET /api/console/questions, /questions/{qid}, /runs,
// /runs/{agent}/{run_id}) and local simulation runs of the qid (GET /api/simulation/runs,
// /runs/{run_id}/series); the plotted numbers are the result cards' and run records' own.
// Dataset, theory and target conventions: extract.ts.

import { useEffect, useMemo, useRef, useState } from "react";

import type { components } from "../../api/schema";
import { useClient } from "../../app/client";
import { useAreaPath } from "../../app/route";
import { useScreenContext } from "../../app/screenContext";
import {
  basicPanels,
  type Column,
  type Dataset,
  datasetsIn,
  isTheory,
  label,
  type Target,
  targetsIn,
  theoryOf,
} from "./extract";
import { COLORS, type Line, Plot } from "./Plot";
import "./results.css";

type Schemas = components["schemas"];
type QuestionSummary = Schemas["QuestionSummaryOut"];
type QuestionDetail = Schemas["QuestionDetailOut"];
type RunSummary = Schemas["RunSummaryOut"];
type RunDetail = Schemas["RunDetailOut"];
type SimRun = Schemas["RunInfoOut"];
type Series = Schemas["SeriesOut"];

const seg = encodeURIComponent;
export const PATHS = {
  questions: "/api/console/questions",
  question: (qid: string) => `/api/console/questions/${seg(qid)}`,
  runs: "/api/console/runs",
  run: (agent: string, runId: string) => `/api/console/runs/${seg(agent)}/${seg(runId)}`,
  simRuns: "/api/simulation/runs",
  simSeries: (runId: string) => `/api/simulation/runs/${seg(runId)}/series`,
};

/** A route segment as a qid; a malformed `%` escape is taken as written. */
function decodeSegment(s: string): string {
  try {
    return decodeURIComponent(s);
  } catch {
    return s;
  }
}

/** The series of a local simulation run as datasets: the log columns and each curve. */
export function seriesDatasets(series: Series, source: string): Dataset[] {
  const out = datasetsIn(series.log, `${source}/log`);
  for (const c of series.curves) {
    const xName = c.x_name || "x";
    const yName = c.path === xName ? `${c.path} (y)` : c.path;
    out.push(...datasetsIn({ x_name: xName, [xName]: c.x, [yName]: c.y }, `${source}/${c.path}`));
  }
  return out;
}

function errorText(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

interface QidData {
  detail: QuestionDetail;
  datasets: Dataset[];
  targets: Target[];
  /** runs of this qid whose detail could not be read */
  runErrors: string[];
}

function useQidData(qid: string | null, runs: RunSummary[] | null): { data: QidData | null; error: string | null } {
  const client = useClient();
  const [state, setState] = useState<{ qid: string; data: QidData | null; error: string | null } | null>(null);
  useEffect(() => {
    if (qid === null || runs === null) return;
    let live = true;
    (async () => {
      const detail = await client.get<QuestionDetail>(PATHS.question(qid));
      const datasets: Dataset[] = [];
      for (const card of detail.results) datasets.push(...datasetsIn(card.data, card.name));
      const runErrors: string[] = [];
      const mine = runs.filter((r) => r.qid === qid);
      for (const r of mine) {
        try {
          const rd = await client.get<RunDetail>(PATHS.run(r.agent, r.run_id));
          for (const [name, rec] of Object.entries(rd.records)) datasets.push(...datasetsIn(rec, `${r.run_id}/${name}`));
        } catch (e) {
          runErrors.push(`${r.run_id}: ${errorText(e)}`);
        }
      }
      // local simulation runs (the simulation area's list); a run the console already gave is skipped
      let simRuns: SimRun[] = [];
      try {
        simRuns = await client.get<SimRun[]>(PATHS.simRuns);
      } catch {
        simRuns = []; // no simulation runs on this server
      }
      for (const r of simRuns.filter((r) => r.qid === qid && !mine.some((m) => m.run_id === r.run_id))) {
        try {
          datasets.push(...seriesDatasets(await client.get<Series>(PATHS.simSeries(r.run_id)), r.run_id));
        } catch (e) {
          runErrors.push(`${r.run_id}: ${errorText(e)}`);
        }
      }
      return { detail, datasets, targets: targetsIn(detail.goal?.data), runErrors };
    })().then(
      (data) => live && setState({ qid, data, error: null }),
      (e) => live && setState({ qid, data: null, error: errorText(e) }),
    );
    return () => {
      live = false;
    };
  }, [client, qid, runs]);
  if (qid === null || state === null || state.qid !== qid) return { data: null, error: null };
  return { data: state.data, error: state.error };
}

export default function ResultsScreen() {
  const client = useClient();
  const [rest, setRest] = useAreaPath();
  const qid = decodeSegment(rest.split("?")[0]) || null;
  const [questions, setQuestions] = useState<QuestionSummary[] | null>(null);
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [listError, setListError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    Promise.all([client.get<QuestionSummary[]>(PATHS.questions), client.get<RunSummary[]>(PATHS.runs)]).then(
      ([q, r]) => {
        if (!live) return;
        setQuestions(q);
        setRuns(r);
      },
      (e) => live && setListError(errorText(e)),
    );
    return () => {
      live = false;
    };
  }, [client]);

  const details = useMemo(() => (qid ? { qid } : {}), [qid]);
  useScreenContext(details);
  const { data, error } = useQidData(qid, runs);

  return (
    <div className="results">
      <h2>Results</h2>
      <div className="res-layout">
        <nav className="res-list" aria-label="qids">
          {listError ? <p className="res-error" role="alert">{listError}</p> : null}
          {questions === null && !listError ? <p>Loading…</p> : null}
          {questions?.length === 0 ? <p>No questions.</p> : null}
          <ul>
            {questions?.map((q) => {
              const nRuns = runs?.filter((r) => r.qid === q.qid).length ?? 0;
              return (
                <li key={q.qid}>
                  <button type="button" className={q.qid === qid ? "res-qid active" : "res-qid"}
                    aria-current={q.qid === qid ? "true" : undefined} onClick={() => setRest(seg(q.qid))}>
                    <span className="res-qid-id">{q.qid}</span>
                    <span className="res-qid-title">{q.title}</span>
                    <span className="res-qid-meta">{q.agent} · {q.status ?? "no status"} · {nRuns} run{nRuns === 1 ? "" : "s"}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>
        <section className="res-main">
          {qid === null ? <p>Pick a qid to see its results.</p> : null}
          {qid !== null && error ? <p className="res-error" role="alert">{qid}: {error}</p> : null}
          {qid !== null && !error && data === null ? <p>Loading {qid}…</p> : null}
          {qid !== null && data ? <QidResults qid={qid} data={data} /> : null}
        </section>
      </div>
    </div>
  );
}

function QidResults({ qid, data }: { qid: string; data: QidData }) {
  const { detail, datasets, targets, runErrors } = data;
  const panels = useMemo(() => basicPanels(datasets, targets), [datasets, targets]);
  const listed = targets.filter((t) => !t.drawn);
  return (
    <>
      <header className="res-head">
        <h3>{qid}</h3>
        <p>{detail.summary.title} · {detail.summary.agent} · version {detail.version} · {detail.results.length} result card{detail.results.length === 1 ? "" : "s"} · {datasets.length} dataset{datasets.length === 1 ? "" : "s"}</p>
        {listed.length > 0 ? (
          <p className="res-note">
            Goal targets not drawn (not a value): {listed.map((t) => `${t.metric} ${t.kind} ${t.value} ${t.unit}`.trim()).join("; ")}
          </p>
        ) : null}
        {runErrors.map((e) => <p key={e} className="res-error" role="alert">{e}</p>)}
      </header>
      {datasets.length === 0 ? (
        <p>No plottable data for this qid yet: no result card or run record has two numeric arrays of the same length.</p>
      ) : (
        <>
          <h4>Plots</h4>
          <p className="res-note">Solid: measured. Dashed: theory (a <code>&lt;y&gt;_theory</code> column) or a goal target value.</p>
          <div className="res-grid">
            {panels.map((p) => {
              const x = p.dataset.columns.find((c) => c.name === p.dataset.x) as Column;
              const lines: Line[] = [{ label: p.y.name, x: x.values, y: p.y.values }];
              if (p.theory) lines.push({ label: p.theory.name, x: x.values, y: p.theory.values, dashed: true, color: "#6e7781" });
              return (
                <div key={`${p.dataset.id}/${p.y.name}`} className="res-cell">
                  <Plot title={`${p.y.name} · ${p.dataset.source}${p.dataset.path ? ` · ${p.dataset.path}` : ""}`}
                    lines={lines} xLabel={label(x)} yLabel={label(p.y)}
                    hlines={p.targets.map((t) => ({ label: `target ${t.value}${t.unit ? ` ${t.unit}` : ""}`, y: t.value }))} />
                  {p.theory && p.dataset.note ? <p className="res-note">{p.dataset.note}</p> : null}
                </div>
              );
            })}
          </div>
          <Explorer datasets={datasets} />
        </>
      )}
    </>
  );
}

/** Pick a dataset, its x column and one or more y columns; theory for each y on request. */
export function Explorer({ datasets }: { datasets: Dataset[] }) {
  const [dsId, setDsId] = useState(datasets[0].id);
  const ds = datasets.find((d) => d.id === dsId) ?? datasets[0];
  const [x, setX] = useState(ds.x);
  const firstY = ds.columns.find((c) => c.name !== ds.x && !isTheory(c.name))?.name;
  const [ys, setYs] = useState<string[]>(firstY ? [firstY] : []);
  const [withTheory, setWithTheory] = useState(true);
  const [logX, setLogX] = useState(false);
  const [logY, setLogY] = useState(false);

  const pickDataset = (id: string) => {
    const d = datasets.find((e) => e.id === id) ?? datasets[0];
    setDsId(d.id);
    setX(d.x);
    const y = d.columns.find((c) => c.name !== d.x && !isTheory(c.name))?.name;
    setYs(y ? [y] : []);
  };
  const xCol = ds.columns.find((c) => c.name === x) ?? ds.columns[0];
  const lines: Line[] = [];
  ys.forEach((name, i) => {
    const c = ds.columns.find((e) => e.name === name);
    if (!c) return;
    const color = COLORS[i % COLORS.length]; // a theory line takes its measured column's colour
    lines.push({ label: c.name, x: xCol.values, y: c.values, dashed: isTheory(c.name), color });
    if (withTheory && !isTheory(c.name)) {
      const t = ds.columns.find((e) => isTheory(e.name) && theoryOf(e.name, ds.columns) === c.name);
      if (t && !ys.includes(t.name)) lines.push({ label: t.name, x: xCol.values, y: t.values, dashed: true, color });
    }
  });
  const yCols = ds.columns.filter((c) => ys.includes(c.name));
  const units = [...new Set(yCols.map((c) => c.unit).filter(Boolean))];
  const yLabel = yCols.length === 1 ? label(yCols[0]) : `${ys.join(", ") || "y"}${units.length === 1 ? ` (${units[0]})` : ""}`;

  return (
    <section className="res-explorer" aria-label="Explore">
      <h4>Explore</h4>
      <div className="res-controls">
        <label>
          Dataset{" "}
          <select value={ds.id} onChange={(e) => pickDataset(e.target.value)}>
            {datasets.map((d) => (
              <option key={d.id} value={d.id}>{d.source}{d.path ? ` · ${d.path}` : ""}</option>
            ))}
          </select>
        </label>
        <label>
          X axis{" "}
          <select value={xCol.name} onChange={(e) => setX(e.target.value)}>
            {ds.columns.map((c) => <option key={c.name} value={c.name}>{label(c)}</option>)}
          </select>
        </label>
        <YPicker columns={ds.columns.filter((c) => c.name !== xCol.name)} ys={ys} setYs={setYs} />
        <label><input type="checkbox" checked={withTheory} onChange={(e) => setWithTheory(e.target.checked)} /> theory (dashed)</label>
        <label><input type="checkbox" checked={logX} onChange={(e) => setLogX(e.target.checked)} /> log x</label>
        <label><input type="checkbox" checked={logY} onChange={(e) => setLogY(e.target.checked)} /> log y</label>
      </div>
      {lines.length === 0 ? <p>Pick at least one Y column.</p> : (
        <Plot lines={lines} xLabel={label(xCol)} yLabel={yLabel} logX={logX} logY={logY}
          title={`${ys.join(", ")} vs ${xCol.name}`} />
      )}
    </section>
  );
}

/** The Y axis as a drop-down: a button naming the picked columns, opening a checklist (several may be picked). */
function YPicker({ columns, ys, setYs }: { columns: Column[]; ys: string[]; setYs: (ys: string[]) => void }) {
  const ref = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    const close = (e: Event) => {
      const el = ref.current;
      if (!el?.open) return;
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !el.contains(e.target as Node)) el.open = false;
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, []);
  const picked = ys.filter((n) => columns.some((c) => c.name === n)); // pick order, as in the plot title and colours
  return (
    <details className="res-ypick" ref={ref}>
      <summary aria-label="Y axis">
        Y axis <span className="res-ypick-btn">{picked.length ? picked.join(", ") : "none"}</span>
      </summary>
      <div className="res-ypick-menu" role="group" aria-label="Y columns">
        {columns.map((c) => (
          <label key={c.name}>
            <input type="checkbox" checked={ys.includes(c.name)}
              onChange={(e) => setYs(e.target.checked ? [...ys, c.name] : ys.filter((n) => n !== c.name))} />
            {label(c)}
          </label>
        ))}
      </div>
    </details>
  );
}
