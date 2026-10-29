/**
 * Optics and control (console cards 012 and 023): the light path drawn in the order its source gives, and a draft for the
 * parts software may command. A draft is an ordinary plan card, checked against the schema and saved nowhere.
 */

import { useRef, useState } from "react";

import { type DraftIn, type LatestRun } from "./api";
import { DraftError, DraftView, NumberField, num, useDraft } from "./draft";
import { PathPanel, RunRefuses } from "./path";
import { type DraftKind, MOVED_BY_HAND } from "./parts";

export const REFUSED_UNTIL_LIMIT = "Refused until you write a limit: your safety file has none for this part yet.";

const DRAFT_LABEL: Record<DraftKind, string> = {
  aura: "Aura III LED",
  dialamp: "Transmitted lamp",
  camera_exposure: "Camera red arm exposure",
};

/** The draft form of one part software may command. Every field is the person's; nothing is sent to an instrument. */
export function PartDraft({ kind, label }: { kind: DraftKind; label: string }) {
  const { draft, error, busy, make } = useDraft();
  const [color, setColor] = useState("");
  const [power, setPower] = useState("");
  const [state, setState] = useState<"on" | "off">("on");
  const [intensity, setIntensity] = useState("");
  const [exposure, setExposure] = useState("");
  const body = (): DraftIn => {
    if (kind === "aura") return { kind, color, power_mw: num(power) };
    if (kind === "dialamp") return { kind, state, intensity_percent: num(intensity) };
    return { kind, exposure_ms: num(exposure) };
  };
  return (
    <div role="group" aria-label={label} className="inst-part-draft">
      <strong>{label}</strong>
      <p className="console-muted">{REFUSED_UNTIL_LIMIT}</p>
      <p className="console-muted"><RunRefuses aura={kind === "aura"} /></p>
      <div className="inst-form">
        {kind === "aura" && (
          <>
            <label className="inst-field">Colour<input type="text" value={color} onChange={(e) => setColor(e.target.value)} /></label>
            <NumberField label="Power (mW)" value={power} onChange={setPower} />
          </>
        )}
        {kind === "dialamp" && (
          <>
            <label className="inst-field">
              State
              <select value={state} onChange={(e) => setState(e.target.value === "off" ? "off" : "on")}>
                <option value="on">on</option>
                <option value="off">off</option>
              </select>
            </label>
            <NumberField label="Intensity (%)" value={intensity} onChange={setIntensity} />
          </>
        )}
        {kind === "camera_exposure" && <NumberField label="Exposure (ms)" value={exposure} onChange={setExposure} />}
        <button type="button" disabled={busy} onClick={() => void make(body())}>{`Draft ${DRAFT_LABEL[kind]}`}</button>
      </div>
      <DraftError error={error} />
      {draft !== undefined && <DraftView draft={draft} />}
    </div>
  );
}

/** Until a click opens an element's draft in place (card 023, part 3), the three drafts stay reachable here, below the drawing. */
const TRANSIENT: readonly { kind: DraftKind; label: string }[] = [
  { kind: "aura", label: "Aura III LED" },
  { kind: "dialamp", label: "Transmitted lamp" },
];

export function Optics({ run }: { run: LatestRun }) {
  const drafts = useRef<HTMLDivElement>(null);
  return (
    <section aria-label="Optics and control" className="inst-optics">
      <PathPanel run={run} onDraft={() => drafts.current?.focus()} />
      <p className="console-muted">{MOVED_BY_HAND}</p>
      <div ref={drafts} tabIndex={-1} role="group" aria-label="Drafts" className="inst-panel">
        {TRANSIENT.map((t) => <PartDraft key={t.kind} kind={t.kind} label={t.label} />)}
      </div>
    </section>
  );
}
