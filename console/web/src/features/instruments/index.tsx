/**
 * Instruments area (console card 012; plan.md 15, 15.1): show, draft and stop, and nothing else. Nothing
 * on these screens commands an instrument, connects to the live-view host or saves a draft. A piece the
 * runtime has not built (check now, latest frames) says so, and the console builds no stand-in for it.
 *
 * `rest` forms (after `#/instruments/`): "" | "status", "optics", "cameras", "tweezers", "confocal", "piezo".
 * Data is read when the area opens and on Refresh; nothing polls except the Piezo screen's own refresh,
 * which is off until the person turns it on.
 */

import { useMemo } from "react";

import { useClient } from "../../app/client";
import { useAreaPath } from "../../app/route";
import { useScreenContext } from "../../app/screenContext";
import { PATHS as QUESTION_PATHS } from "../questions/api";
import { Loaded } from "../questions/ui";
import { useFollow } from "./follow";
import { idleView, type LatestRun, type LimitsOut, PATHS, type StatusOut } from "./api";
import "../questions/console.css";
import "./instruments.css";
import { Cameras } from "./cameras";
import { Confocal } from "./confocal";
import { Optics } from "./optics";
import { Piezo } from "./piezo";
import { Status } from "./status";
import { Tweezers } from "./tweezers";

type Tab = "status" | "optics" | "cameras" | "tweezers" | "confocal" | "piezo";

const TABS: { id: Tab; label: string }[] = [
  { id: "status", label: "Status" },
  { id: "optics", label: "Optics and control" },
  { id: "cameras", label: "Cameras" },
  { id: "tweezers", label: "Tweezers" },
  { id: "confocal", label: "Confocal" },
  { id: "piezo", label: "Piezo stage" },
];

export function parseTab(rest: string): Tab {
  const first = rest.replace(/[?#].*$/, "").split("/").filter((p) => p !== "")[0];
  return TABS.find((t) => t.id === first)?.id ?? "status";
}

interface Data {
  status: StatusOut;
  limits: LimitsOut;
  run: LatestRun;
  isPerson: boolean;
}

export default function InstrumentsScreen() {
  const client = useClient();
  const [rest, setRest] = useAreaPath();
  const tab = parseTab(rest);
  const details = useMemo(() => ({ tab }), [tab]);
  useScreenContext(details);

  const { state: data, reload } = useFollow<Data>(async () => {
    const [status, limits, run, signing] = await Promise.all([
      client.get<StatusOut>(PATHS.status),
      client.get<LimitsOut>(PATHS.limits),
      client.get<LatestRun>(PATHS.latestRun),
      client.get<{ is_person?: boolean }>(QUESTION_PATHS.signing).catch(() => ({ is_person: false })),
    ]);
    return { status, limits, run, isPerson: signing?.is_person === true };
  }, (d) => d.run.state === "ok" && d.run.running);

  return (
    <div className="console inst">
      <nav role="tablist" aria-label="Instruments" className="console-tabs">
        {TABS.map((t) => (
          <button key={t.id} type="button" role="tab" aria-selected={tab === t.id} onClick={() => setRest(t.id)}>
            {t.label}
          </button>
        ))}
      </nav>
      <Loaded state={data}>
        {(d) => {
          const view = d.status.state === "present" && d.status.data ? idleView(d.status.data) : null;
          switch (tab) {
            case "optics":
              return <Optics readings={view?.snapshot ?? []} run={d.run} />;
            case "cameras":
              return <Cameras run={d.run} isPerson={d.isPerson} />;
            case "tweezers":
              return <Tweezers run={d.run} limits={d.limits} />;
            case "confocal":
              return <Confocal status={d.status} view={view} run={d.run} />;
            case "piezo":
              return <Piezo run={d.run} limits={d.limits} />;
            default:
              return (
                <Status status={d.status} view={view} run={d.run} isPerson={d.isPerson} onRefresh={reload} />
              );
          }
        }}
      </Loaded>
    </div>
  );
}
