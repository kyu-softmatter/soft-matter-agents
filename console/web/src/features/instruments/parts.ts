/**
 * The words the Optics screen says about what software may and may not command (console cards 012 and 017). **The list of
 * parts and the picture of the stand that lived here are gone** (card 023): which elements there are, and in what order light
 * travels through them, come from the order the run's source gives, and no part is named on this page.
 */

export type DraftKind = "camera_exposure";

/** Beside the red camera's exposure draft. The server words the same sentence in `refused_today`. */
export const RUN_REFUSES =
  "The run will refuse this draft even when it is made and signed: nothing recorded yet tells it how to set the red camera's exposure on this microscope.";
/** What the control of the Aura and the transmitted lamp says, now that no draft is offered for them (card 024). The reasons come with the row. */
export const NO_DRAFT_LABEL = "no draft is offered yet";
export const BY_HAND = "set by hand; software may not move it";
export const COMBINER_SENTENCE = "close was sent; assumed open until a shutter that reads back shows it blocked";
export const MOVED_BY_HAND =
  "Moved by hand: the filters, the objectives, the light path, the spinning disk, the large XY stage and the trap laser. Software does not move them, and no draft is offered for them.";
