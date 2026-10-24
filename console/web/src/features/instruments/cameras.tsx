/**
 * Cameras (canvas `PCameras`, console card 012): four panels. Panel 1 is the red camera, through today's
 * live-view code and only while a signed run is acquiring; the blue camera is not opened by software yet;
 * the fourth panel draws no traps because their mapping onto the camera is not measured. The console opens
 * no camera itself, and Live view connects to nothing until the person presses it.
 */

import { useState } from "react";

import { SmaLiveSwitch } from "../live/smaLive";
import { FollowedRun } from "../questions/runs";
import type { LatestRun } from "./api";
import { PartDraft } from "./optics";

export function Cameras({ run, isPerson }: { run: LatestRun; isPerson: boolean }) {
  const [live, setLive] = useState(false);
  return (
    <section aria-label="Cameras" className="inst-cameras">
      <section aria-label="Camera 1, red" className="inst-panel">
        <h3>Camera 1, red</h3>
        <p className="console-muted">A frame is shown only while a signed run is acquiring.</p>
        {run.state === "ok" && run.run_id !== null && run.run_id !== undefined && (
          <FollowedRun agent="microscope" runId={run.run_id} />
        )}
        {isPerson && (
          <button type="button" onClick={() => setLive((v) => !v)}>{live ? "Hide live view" : "Live view"}</button>
        )}
        {live && <SmaLiveSwitch />}
        <PartDraft kind="camera_exposure" label="Camera red arm" />
      </section>
      <section aria-label="Camera 2, blue" className="inst-panel">
        <h3>Camera 2, blue</h3>
        <p>The blue camera is not opened by software yet.</p>
      </section>
      <section aria-label="Both cameras" className="inst-panel">
        <h3>Both cameras</h3>
        <p>Not shown: the blue camera is not opened by software yet.</p>
      </section>
      <section aria-label="With traps and stage" className="inst-panel">
        <h3>With traps and stage</h3>
        <p>traps not drawn: their mapping onto the camera is not measured</p>
      </section>
    </section>
  );
}
