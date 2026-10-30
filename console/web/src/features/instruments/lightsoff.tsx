/**
 * [Lights off] (console card 023, part 5). One press sends the server one request with nothing in it; the server sends the
 * live-view host the one line `{"lights_off": true}` and answers with what the host said, already checked against
 * `lights_off_reply`. The page shows that answer and decides nothing from it: a row is shown as the host gave it, a source
 * is never shown off unless the host's row says off with a read-back, and anything the page does not recognise is shown as
 * no answer. There is no confirmation, no password and no draft: a lights-off that waits is a slower one.
 *
 * It is not the assistant's lights-off and it is not a stop. It is the only request this screen makes besides the ones the
 * person asks for by other buttons; nothing is sent while it renders or refreshes.
 */

import { useRef, useState } from "react";

import { useClient } from "../../app/client";
import { type LightSourceOut, type LightsOffOut, PATHS } from "./api";

export const ALSO_STOPS_THE_PLAN = "While a plan is running, this also stops that plan.";
export const NOTHING_KNOWN = "Nothing is known about the lights: use the switches.";
export const USE_THE_SWITCH = "Use the switch on the device.";
const CHECK_EACH = "Check each light at its switch: none is shown off.";
const NOTHING_SENT = "Nothing was sent to any light. Use the switches.";

const ANSWERS = new Set(["done", "stop_sent", "refused", "no_answer", "no_host"]);
const RESULTS = new Set(["off", "sent", "not_turned_off"]);
const RUN_ID = /^run-[0-9]{8}-[0-9]{3}$/;

type Shown =
  | { kind: "done"; how: "own_run" | "run_stop"; runId: string; rows: LightSourceOut[] }
  | { kind: "stop_sent"; runId: string; reason: string }
  | { kind: "refused"; reason: string }
  | { kind: "none"; reason: string | null };

const none = (reason: string | null = null): Shown => ({ kind: "none", reason });

function isRow(r: unknown): r is LightSourceOut {
  if (typeof r !== "object" || r === null) return false;
  const row = r as Record<string, unknown>;
  if (typeof row.source !== "string" || typeof row.channel !== "string") return false;
  if (typeof row.result !== "string" || !RESULTS.has(row.result)) return false;
  if (row.result === "off") return typeof row.read_back === "string";
  if (row.result === "sent") return row.read_back === null || row.read_back === undefined;
  return typeof row.reason === "string" && row.reason !== "";
}

/** What the page may show of an answer: only a shape it fully understands, else no answer. */
export function shownOf(out: unknown): Shown {
  if (typeof out !== "object" || out === null) return none();
  const o = out as Partial<LightsOffOut> & Record<string, unknown>;
  if (typeof o.answer !== "string" || !ANSWERS.has(o.answer)) return none();
  const reason = typeof o.reason === "string" && o.reason !== "" ? o.reason : null;
  if (o.answer === "done") {
    if ((o.how !== "own_run" && o.how !== "run_stop") || typeof o.run_id !== "string" || !RUN_ID.test(o.run_id)) return none();
    if (!Array.isArray(o.sources) || o.sources.length === 0 || !o.sources.every(isRow)) return none();
    return { kind: "done", how: o.how, runId: o.run_id, rows: o.sources };
  }
  if (o.answer === "stop_sent") {
    if (typeof o.run_id !== "string" || !RUN_ID.test(o.run_id) || reason === null) return none();
    return { kind: "stop_sent", runId: o.run_id, reason };
  }
  if (o.answer === "refused") return reason === null ? none() : { kind: "refused", reason };
  return none(reason);
}

function ResultText({ row }: { row: LightSourceOut }) {
  if (row.result === "off") return <>Off. Read back {row.read_back}.</>;
  if (row.result === "sent") return <>Sent. It cannot be read back, so it is not known to be off.</>;
  return (
    <>
      Not turned off: {row.reason}. {USE_THE_SWITCH}
    </>
  );
}

export function LightsOff({ running, onAnswered }: { running: boolean; onAnswered?: () => void }) {
  const client = useClient();
  const inFlight = useRef(false);
  const [busy, setBusy] = useState(false);
  const [shown, setShown] = useState<Shown | null>(null);

  const press = async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setShown(null);
    try {
      setShown(shownOf(await client.post<unknown>(PATHS.lightsOff)));
      onAnswered?.(); // read the run's files again, so the path shows what the run recorded; a read, never a resend
    } catch (e) {
      setShown(none(e instanceof Error ? e.message : String(e)));
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  };

  return (
    <div className="inst-lights-off">
      <button type="button" className="abort-button" disabled={busy} onClick={() => void press()}>
        Lights off
      </button>
      {running && <p className="console-muted">{ALSO_STOPS_THE_PLAN}</p>}
      {busy && (
        <p className="console-muted" role="status">
          Waiting for the lights…
        </p>
      )}
      {shown && (
        <div role="status" data-testid="lights-off-result" className="inst-lights-off-result">
          {shown.kind === "done" && (
            <>
              <p>
                Run {shown.runId} turned the lights off.
                {shown.how === "run_stop" && " The running plan was stopped."}
              </p>
              <table aria-label="Light sources">
                <thead>
                  <tr>
                    <th>Source</th>
                    <th>Channel</th>
                    <th>Result</th>
                  </tr>
                </thead>
                <tbody>
                  {shown.rows.map((r, i) => (
                    <tr key={`${r.channel}-${i}`}>
                      <td>{r.source}</td>
                      <td>{r.channel}</td>
                      <td>
                        <ResultText row={r} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
          {shown.kind === "stop_sent" && (
            <>
              <p>
                A stop was sent to run {shown.runId}. {shown.reason}.
              </p>
              <p className="warn">{CHECK_EACH}</p>
            </>
          )}
          {shown.kind === "refused" && (
            <>
              <p>The lights-off request was refused: {shown.reason}.</p>
              <p className="warn">{NOTHING_SENT}</p>
            </>
          )}
          {shown.kind === "none" && (
            <>
              {shown.reason && <p>{shown.reason}</p>}
              <p className="warn">{NOTHING_KNOWN}</p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
