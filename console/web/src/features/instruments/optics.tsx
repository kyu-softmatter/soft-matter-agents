/**
 * Optics and control (canvas `POptics`, console card 012): a picture of the stand, each part's state from the
 * idle status file by channel id (or "unknown"), and a draft for the three parts software may command. A
 * draft is an ordinary plan card, checked against the schema and saved nowhere.
 */

import { useState } from "react";

import { type DraftIn, HOW_WORDS, type Reading, valueText } from "./api";
import { DraftError, DraftView, NumberField, num, useDraft } from "./draft";
import { ALL_PARTS, BY_HAND, COMBINER, COMBINER_SENTENCE, type DraftKind, type Part, ROWS, SECTIONS, type Section } from "./parts";

export const REFUSED_UNTIL_LIMIT = "Refused until you write a limit: your safety file has none for this part yet.";

/** What a part shows for its state: the channel's reading as read, or "unknown". */
export function stateOf(part: Part, readings: Reading[]): string {
  if (part.channel === null) return "unknown";
  const r = readings.find((x) => x.channel === part.channel);
  if (r === undefined || r.how === "not_read" || r.value === null || r.value === undefined) return "unknown";
  return `${valueText(r.value)} (${HOW_WORDS[r.how] ?? r.how})`;
}

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

function PartRow({ part }: { part: Part }) {
  if (part.draft !== undefined) return <PartDraft kind={part.draft} label={part.label} />;
  return (
    <div role="group" aria-label={part.label} className="inst-part-draft">
      <strong>{part.label}</strong>
      <p className="console-muted">{part.label === COMBINER ? COMBINER_SENTENCE : BY_HAND}</p>
      {part.label === COMBINER && <p className="console-muted">{BY_HAND}</p>}
    </div>
  );
}

export function Optics({ readings }: { readings: Reading[] }) {
  const [section, setSection] = useState<Section>("Light source");
  return (
    <section aria-label="Optics and control" className="inst-optics">
      <figure aria-label="Picture of the stand" className="inst-picture">
        <figcaption className="console-muted">
          A picture of the stand, not a measurement. Double-click a part to open the tab it belongs to.
        </figcaption>
        {ROWS.map((row) => (
          <div key={row.label} role="group" aria-label={row.label} className="inst-row">
            <span className="inst-row-label">{row.label}</span>
            {row.parts.map((p) => (
              <button key={p.label} type="button" className="inst-part" onDoubleClick={() => setSection(p.section)}>
                <span>{p.label}</span> <span className="console-muted">{stateOf(p, readings)}</span>
              </button>
            ))}
          </div>
        ))}
      </figure>
      <nav role="tablist" aria-label="Optics sections" className="console-tabs">
        {SECTIONS.map((s) => (
          <button key={s} type="button" role="tab" aria-selected={section === s} onClick={() => setSection(s)}>{s}</button>
        ))}
      </nav>
      <div role="tabpanel" aria-label={section} className="inst-panel">
        {ALL_PARTS.filter((p) => p.section === section).map((p) => <PartRow key={p.label} part={p} />)}
      </div>
    </section>
  );
}
