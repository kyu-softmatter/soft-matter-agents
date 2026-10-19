/**
 * What an area shows once the routes it called are retired (soft-matter-agents card 077, console
 * card 003). The console sends no command to the instrument, so an area that only drove dino's
 * engine says what it was for, that it is not connected here, and what replaces it. It requests
 * nothing: this component has no client, no effect and no control.
 */

export interface RetiredNotice {
  /** the area's name, as the navigation shows it */
  area: string;
  /** what the area was for, finishing the sentence "<area> was for ..." */
  wasFor: string;
  /** what replaces it, finishing the sentence "Instead, ..." */
  replacedBy: string;
}

const PLAN = "a plan is drafted for the person to approve, and a running plan can be asked to stop.";

/** The notice of each retired area. Kept in one place so the tests can walk them. */
export const RETIRED_AREAS = {
  hardware: {
    area: "Hardware",
    wasFor: "detecting the devices, reading their status, switching the lights and drafting a Micro-Manager configuration",
    replacedBy: `${PLAN} The run that executes it loads the configuration the person approved, by its hash.`,
  },
  sample: {
    area: "Sample",
    wasFor: "creating and opening a sample, entering its geometry and confirming how it was loaded",
    replacedBy: `${PLAN} The plan names the sample it runs on.`,
  },
  map: {
    area: "Map",
    wasFor: "the sample map, and moving the stage by clicking on it",
    replacedBy: `${PLAN} A stage move is a step of a plan, not a click.`,
  },
  objective: {
    area: "Objective",
    wasFor: "changing the objective and running the 100x focus search",
    replacedBy: `${PLAN} A focus search is a plan the person approves.`,
  },
  patterns: {
    area: "Patterns",
    wasFor: "drawing, saving and running motion patterns",
    replacedBy: PLAN,
  },
  tweezers: {
    area: "Tweezers",
    wasFor: "moving and switching the optical traps",
    replacedBy: `${PLAN} Trap moves are the steps of a trap plan.`,
  },
  sessions: {
    area: "Sessions",
    wasFor: "opening and closing experiment sessions and browsing their records",
    replacedBy:
      "the questions and runs in the Console area are read from the agents' files, and a running plan can be asked to stop there.",
  },
} as const satisfies Record<string, RetiredNotice>;

export type RetiredAreaId = keyof typeof RETIRED_AREAS;

export function Retired({ area, wasFor, replacedBy }: RetiredNotice) {
  return (
    <section className="retired-area" aria-label={area} data-testid="retired-area">
      <h2>{area}</h2>
      <p role="status">
        {area} was for {wasFor}. It is not connected here: the console sends no command to the instrument.
      </p>
      <p className="muted">Instead, {replacedBy}</p>
    </section>
  );
}
