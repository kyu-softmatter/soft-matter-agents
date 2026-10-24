/**
 * The picture of the stand on the Optics screen (console card 012; canvas `POptics`): three rows of parts.
 * A part's `channel` is the run channel whose reading the picture shows for it, **or null**, and a null is
 * the honest answer: the stand's parts share one channel, and which of the two widefield channels is the LED
 * and which the lamp is not recorded, so neither part takes either. Nothing here decides a device's role
 * from how its name is written; a part has a draft only where the runtime's list of what software may
 * command names it (the Aura LED, the transmitted lamp, the red camera's exposure), and every other part
 * is set by hand.
 */

export type Section = "Light source" | "Filters" | "Magnification" | "Camera";
export const SECTIONS: readonly Section[] = ["Light source", "Filters", "Magnification", "Camera"];

export type DraftKind = "aura" | "dialamp" | "camera_exposure";

export interface Part {
  label: string;
  channel: string | null;
  section: Section;
  draft?: DraftKind;
}

export const BY_HAND = "set by hand; software may not move it";
export const COMBINER_SENTENCE = "close was sent; assumed open until a shutter that reads back shows it blocked";
export const COMBINER = "Laser combiner";

export const ROWS: readonly { label: string; parts: readonly Part[] }[] = [
  {
    label: "Transmitted light",
    parts: [
      { label: "Transmitted lamp", channel: null, section: "Light source", draft: "dialamp" },
      { label: "Polarizer", channel: null, section: "Filters" },
      { label: "Condenser turret", channel: "stand_ti2e", section: "Magnification" },
      { label: "XY stage", channel: "stand_ti2e", section: "Magnification" },
      { label: "Piezo stage", channel: "piezo_stage", section: "Magnification" },
    ],
  },
  {
    label: "Light from above",
    parts: [
      { label: "Aura III LED", channel: null, section: "Light source", draft: "aura" },
      { label: "Spectra III via DMD", channel: "dmd", section: "Light source" },
      { label: "Tweez 300 trap", channel: "optical_tweezers", section: "Light source" },
      { label: COMBINER, channel: "laser_combiner", section: "Light source" },
      { label: "Filter turret 1", channel: "stand_ti2e", section: "Filters" },
      { label: "Filter turret 2", channel: "stand_ti2e", section: "Filters" },
      { label: "Objective", channel: "stand_ti2e", section: "Magnification" },
    ],
  },
  {
    label: "To the cameras",
    parts: [
      { label: "Light path selector", channel: "stand_ti2e", section: "Filters" },
      { label: "Eyepieces", channel: null, section: "Camera" },
      { label: "CSU-W1 spinning disk", channel: "confocal_csuw1", section: "Filters" },
      { label: "Camera splitter", channel: null, section: "Camera" },
      { label: "Emission wheel 1", channel: null, section: "Filters" },
      { label: "Emission wheel 2", channel: null, section: "Filters" },
      { label: "Camera red arm", channel: "camera_red", section: "Camera", draft: "camera_exposure" },
      { label: "Camera blue arm", channel: "camera_blue", section: "Camera" },
    ],
  },
];

export const ALL_PARTS: readonly Part[] = ROWS.flatMap((r) => r.parts);
