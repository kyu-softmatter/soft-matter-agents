import { ProgressBar, StateBadge } from "./Progress";
import type { SimRunInfoJson } from "./types";

export function RunList({ runs, onOpen }: { runs: SimRunInfoJson[]; onOpen: (runId: string) => void }) {
  if (runs.length === 0) return <p className="muted">No simulation runs.</p>;
  return (
    <table className="sim-table" aria-label="Simulation runs">
      <thead>
        <tr>
          <th>run</th>
          <th>state</th>
          <th>progress</th>
          <th>backend</th>
          <th>question</th>
          <th>trajectory</th>
        </tr>
      </thead>
      <tbody>
        {runs.map((r) => (
          <tr key={r.run_id}>
            <td>
              <a
                href={`#/simulation/runs/${encodeURIComponent(r.run_id)}`}
                onClick={(e) => {
                  e.preventDefault();
                  onOpen(r.run_id);
                }}
              >
                {r.run_id}
              </a>
            </td>
            <td>
              <StateBadge state={r.progress.state} />
            </td>
            <td>
              <ProgressBar p={r.progress} />
            </td>
            <td>{r.backend ?? "–"}</td>
            <td>{r.qid ?? "–"}</td>
            <td>{r.trajectory ? "yes" : <span className="muted" title={r.trajectory_unavailable ?? ""}>no</span>}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
