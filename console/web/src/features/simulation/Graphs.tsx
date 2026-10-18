import { useState } from "react";

import { fmt, HistogramChart, LineChart } from "./Charts";
import type { RunSeriesJson } from "./types";

const X_CHOICES = ["steps_taken", "simulated_time", "t_mono"] as const;
// columns that are an x axis or a counter, not worth a chart of their own
const NOT_PLOTTED = new Set<string>([...X_CHOICES, "frames_saved", "fraction_of_planned_steps"]);

/** F6.4: the progress-log columns against step or time, then the observables' curves and numbers. */
export function Graphs({ series }: { series: RunSeriesJson }) {
  const available = X_CHOICES.filter((k) => series.log[k]?.length);
  const [xKey, setXKey] = useState<string>(available[0] ?? "steps_taken");
  const [logLog, setLogLog] = useState(false);
  const x = series.log[xKey] ?? [];
  const columns = Object.keys(series.log).filter((k) => !NOT_PLOTTED.has(k));
  const scalars = Object.entries(series.scalars);

  return (
    <section className="sim-panel" aria-label="Graphs">
      <h3>Log</h3>
      {columns.length === 0 ? (
        <p className="muted">The log has no progress values.</p>
      ) : (
        <>
          <label>
            x axis{" "}
            <select value={xKey} onChange={(e) => setXKey(e.target.value)} aria-label="x axis">
              {available.map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
          </label>
          <div className="sim-charts">
            {columns.map((k) => (
              <LineChart key={k} title={k} x={x} y={series.log[k]} xLabel={xKey} />
            ))}
          </div>
        </>
      )}

      <h3>Observables{series.observable ? `: ${series.observable}` : ""}</h3>
      {series.observables == null ? (
        <p className="muted">No observables.json yet.</p>
      ) : (
        <>
          {series.curves.some((c) => c.kind === "line") ? (
            <label>
              <input type="checkbox" checked={logLog} onChange={(e) => setLogLog(e.target.checked)} /> log–log
            </label>
          ) : null}
          <div className="sim-charts">
            {series.curves.map((c) =>
              c.kind === "histogram" ? (
                <HistogramChart key={c.path} title={c.path} edges={c.x} counts={c.y} xLabel={c.x_name ?? "x"} />
              ) : (
                <LineChart key={c.path} title={c.path} x={c.x} y={c.y} xLabel={c.x_name ?? "x"} logX={logLog} logY={logLog} />
              ),
            )}
          </div>
          {scalars.length ? (
            <table className="sim-table sim-scalars" aria-label="Observable values">
              <tbody>
                {scalars.map(([k, v]) => (
                  <tr key={k}>
                    <th>{k}</th>
                    <td title={String(v)}>{fmt(v)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
        </>
      )}
    </section>
  );
}
