/**
 * The draft form of the red camera's exposure, the one part a draft is offered for (console cards 012, 017, 023 and 024). Every
 * field is the person's; nothing is sent to an instrument. A click on the camera's element opens this in place; "Add to the
 * changes" collects it into the one draft.
 */

import { useState } from "react";

import { type DraftIn } from "./api";
import { DraftError, DraftView, NumberField, num, useDraft } from "./draft";
import { type DraftKind } from "./parts";
import { RunRefuses } from "./readout";

export const REFUSED_NO_LIMIT = "No limit has been named for this quantity yet, so this draft is refused before it can be signed.";

export const DRAFT_LABEL: Record<DraftKind, string> = {
  camera_exposure: "Camera red arm exposure",
};

/** What a filled draft says, in words, in the changes list. */
export function wordsOf(body: DraftIn): string {
  return `${DRAFT_LABEL.camera_exposure}: ${body.exposure_ms} ms`;
}

export function PartDraft({
  kind, label, onAdd,
}: { kind: DraftKind; label: string; onAdd?: (part: DraftKind, body: DraftIn, words: string) => string | undefined }) {
  const { draft, error, busy, make } = useDraft();
  const [exposure, setExposure] = useState("");
  const [refused, setRefused] = useState<string | undefined>(undefined);
  const body = (): DraftIn => ({ kind, exposure_ms: num(exposure) });
  /** What is still empty, by the field's own name. */
  const missing = (): string[] => (num(exposure) === undefined ? ["exposure"] : []);
  const add = () => {
    const lacking = missing();
    if (lacking.length > 0) return setRefused(`Not added: fill in the ${lacking.join(" and the ")} first.`);
    const b = body();
    setRefused(onAdd?.(kind, b, wordsOf(b)));
  };
  return (
    <div role="group" aria-label={label} className="inst-part-draft">
      <strong>{label}</strong>
      <p className="console-muted">{REFUSED_NO_LIMIT}</p>
      <p className="console-muted"><RunRefuses /></p>
      <div className="inst-form">
        <NumberField label="Exposure (ms)" value={exposure} onChange={setExposure} />
        <button type="button" disabled={busy} onClick={() => void make(body())}>{`Draft ${DRAFT_LABEL[kind]}`}</button>
        {onAdd !== undefined && <button type="button" onClick={add}>Add to the changes</button>}
      </div>
      {refused !== undefined && <p role="alert" className="console-error">{refused}</p>}
      <DraftError error={error} />
      {draft !== undefined && <DraftView draft={draft} />}
    </div>
  );
}
