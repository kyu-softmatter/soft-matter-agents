import { useCallback, useEffect, useState } from "react";

import { useClient, useEngineEvents } from "../../app/client";
import {
  type CamFrame,
  FocusPanel,
  type FocusSample,
  LiveView,
  pushSample,
  sampleOf,
  type Trap,
  TrapOverlay,
} from "../../app/live";
import { SmaLiveSwitch } from "./smaLive";

const TRAP_EVENTS = ["motion", "finished"] as const;

/**
 * The live area (owned by the shell, T-010). With tweezers on the setup, "Traps" draws where each
 * trap is now. Beside the frames: each camera's live focus score and the focus height (stage z +
 * piezo z) over the last minute. The overlay and the panel are display only: they move nothing.
 * The motion-pattern overlay went with the pattern routes (console card 003).
 */
export default function LiveScreen() {
  const client = useClient();
  const [traps, setTraps] = useState<Trap[] | null>(null);
  const [showTraps, setShowTraps] = useState(true);
  const [samples, setSamples] = useState<FocusSample[]>([]);
  const onFrame = useCallback((f: CamFrame) => setSamples((list) => pushSample(list, sampleOf(f))), []);

  const readTraps = useCallback(() => {
    client.get<{ tweezers?: { traps?: Trap[] } | null }>("/api/state").then(
      (s) => setTraps(s.tweezers ? (s.tweezers.traps ?? []) : null),
      () => setTraps(null),
    );
  }, [client]);
  useEffect(readTraps, [readTraps]);
  useEngineEvents(readTraps, TRAP_EVENTS);

  const trapsShown = showTraps && traps !== null;
  const overlay = useCallback(
    (frame: CamFrame) => (trapsShown && traps ? <TrapOverlay traps={traps} meta={frame.meta} /> : null),
    [trapsShown, traps],
  );

  return (
    <section aria-label="Live view">
      <h2>Live view</h2>
      {traps !== null && (
        <div className="patterns-bar">
          <label>
            <input type="checkbox" checked={showTraps} onChange={(e) => setShowTraps(e.target.checked)} /> Traps
          </label>
        </div>
      )}
      <SmaLiveSwitch />
      <div className="live-with-focus">
        <LiveView overlay={trapsShown ? overlay : undefined} onFrame={onFrame} />
        <FocusPanel samples={samples} />
      </div>
    </section>
  );
}
