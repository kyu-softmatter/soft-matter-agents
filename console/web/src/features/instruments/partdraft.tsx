/**
 * The draft form of one part software may command (console cards 012, 017 and 023). Every field is the person's; nothing is
 * sent to an instrument. A click on a drafted element opens this in place; "Add to the changes" collects it into the one draft.
 */

import { useState } from "react";

import { type DraftIn } from "./api";
import { DraftError, DraftView, NumberField, num, useDraft } from "./draft";
import { type DraftKind } from "./parts";
import { RunRefuses } from "./readout";

export const REFUSED_UNTIL_LIMIT = "Refused until you write a limit: your safety file has none for this part yet.";

export const DRAFT_LABEL: Record<DraftKind, string> = {
  aura: "Aura III LED",
  dialamp: "Transmitted lamp",
  camera_exposure: "Camera red arm exposure",
};

/** What a filled draft says, in words, in the changes list. */
export function wordsOf(body: DraftIn): string {
  if (body.kind === "aura") return `${DRAFT_LABEL.aura}: ${body.color}, ${body.power_mw} mW`;
  if (body.kind === "dialamp") return `${DRAFT_LABEL.dialamp}: ${body.state}, ${body.intensity_percent} %`;
  return `${DRAFT_LABEL.camera_exposure}: ${body.exposure_ms} ms`;
}

export function PartDraft({
  kind, label, onAdd,
}: { kind: DraftKind; label: string; onAdd?: (part: DraftKind, body: DraftIn, words: string) => string | undefined }) {
  const { draft, error, busy, make } = useDraft();
  const [color, setColor] = useState("");
  const [power, setPower] = useState("");
  const [state, setState] = useState<"on" | "off">("on");
  const [intensity, setIntensity] = useState("");
  const [exposure, setExposure] = useState("");
  const [refused, setRefused] = useState<string | undefined>(undefined);
  const body = (): DraftIn => {
    if (kind === "aura") return { kind, color, power_mw: num(power) };
    if (kind === "dialamp") return { kind, state, intensity_percent: num(intensity) };
    return { kind, exposure_ms: num(exposure) };
  };
  /** What is still empty, by the field's own name. */
  const missing = (): string[] => {
    if (kind === "aura") return [...(color.trim() === "" ? ["colour"] : []), ...(num(power) === undefined ? ["power"] : [])];
    if (kind === "dialamp") return num(intensity) === undefined ? ["intensity"] : [];
    return num(exposure) === undefined ? ["exposure"] : [];
  };
  const add = () => {
    const lacking = missing();
    if (lacking.length > 0) return setRefused(`Not added: fill in the ${lacking.join(" and the ")} first.`);
    const b = body();
    setRefused(onAdd?.(kind, b, wordsOf(b)));
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
        {onAdd !== undefined && <button type="button" onClick={add}>Add to the changes</button>}
      </div>
      {refused !== undefined && <p role="alert" className="console-error">{refused}</p>}
      <DraftError error={error} />
      {draft !== undefined && <DraftView draft={draft} />}
    </div>
  );
}
