/**
 * What one read-back element says of itself, shared by the list (card 017) and the drawing (card 023): its state in 017's
 * four labels, how it was read, and the refusal notice beside everything drafted. Nothing here sends anything.
 */

import { shortTime } from "../questions/ui";
import type { LatestRun } from "./api";
import { RUN_REFUSES } from "./parts";

export type Element = LatestRun["path"]["elements"][number];

export const BY_HAND_LABEL = "moved by hand";
export const STATE_LABEL: Record<Element["state"], string> = {
  read_back: "read back", sent: "sent", not_open: "not open", not_read: "not read",
};

/** What the person is told beside the red camera's exposure draft. */
export function RunRefuses() {
  return <span className="inst-refuses">{RUN_REFUSES}</span>;
}

export function Reading({ e }: { e: Element }) {
  const mock = e.backend === "mock" ? <> · <span className="inst-backend">the mock&apos;s state</span></> : null;
  if (e.state === "read_back") return <>{e.value} · read {shortTime(e.t_wall)}{mock}</>;
  if (e.state === "sent") {
    return (
      <>
        {e.value !== null && e.value !== undefined && <>{e.value}{e.t_wall ? ` (read ${shortTime(e.t_wall)})` : ""} · </>}
        {e.sent ? `sent ${e.sent}${e.sent_at ? ` at ${shortTime(e.sent_at)}` : ""}` : "nothing sent in this run's events"}
        {e.reason && <> · {e.reason}</>}
        {mock}
      </>
    );
  }
  return <>{e.reason}{mock}</>;
}
