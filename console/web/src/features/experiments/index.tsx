/**
 * Experiments area (console card 014): the Plan page (plans on disk, runs, drafts) and the Sample map page
 * with the sample's record view as a panel. It reads files and sends nothing to a runtime; the one POST,
 * Run, answers "not built yet". `rest` forms (after `#/experiments/`): "" | "plan" | "sample-map".
 */

import { useMemo } from "react";

import { useAreaPath } from "../../app/route";
import { useScreenContext } from "../../app/screenContext";
import "../questions/console.css";
import "../instruments/instruments.css";
import { Plan } from "./plan";
import { SampleMap } from "./sampleMap";

type Tab = "plan" | "sample-map";

const TABS: { id: Tab; label: string }[] = [
  { id: "plan", label: "Plan" },
  { id: "sample-map", label: "Sample map" },
];

export function parseTab(rest: string): Tab {
  const first = rest.replace(/[?#].*$/, "").split("/").filter((p) => p !== "")[0];
  return TABS.find((t) => t.id === first)?.id ?? "plan";
}

export default function ExperimentsScreen() {
  const [rest, setRest] = useAreaPath();
  const tab = parseTab(rest);
  const details = useMemo(() => ({ tab }), [tab]);
  useScreenContext(details);
  return (
    <div className="console exp">
      <nav role="tablist" aria-label="Experiments" className="console-tabs">
        {TABS.map((t) => (
          <button key={t.id} type="button" role="tab" aria-selected={tab === t.id} onClick={() => setRest(t.id)}>
            {t.label}
          </button>
        ))}
      </nav>
      {tab === "plan" ? <Plan /> : <SampleMap />}
    </div>
  );
}
