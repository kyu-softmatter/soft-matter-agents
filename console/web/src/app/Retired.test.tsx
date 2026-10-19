import { render, screen } from "@testing-library/react";
import type { ComponentType } from "react";
import { afterEach, describe, expect, it } from "vitest";

import HardwareScreen from "../features/hardware/index";
import MapScreen from "../features/map/index";
import ObjectiveScreen from "../features/objective/index";
import PatternsScreen from "../features/patterns/index";
import SampleScreen from "../features/sample/index";
import SessionsScreen from "../features/sessions/index";
import TweezersScreen from "../features/tweezers/index";
import { fakeTransport } from "../test/fakes";
import { AREAS } from "./areas";
import { Client, ClientProvider } from "./client";
import { RETIRED_AREAS, type RetiredAreaId } from "./Retired";

const clients: Client[] = [];
afterEach(() => {
  clients.splice(0).forEach((c) => c.events.stop());
});

const SCREENS: Record<RetiredAreaId, ComponentType> = {
  hardware: HardwareScreen,
  sample: SampleScreen,
  map: MapScreen,
  objective: ObjectiveScreen,
  patterns: PatternsScreen,
  tweezers: TweezersScreen,
  sessions: SessionsScreen,
};

describe("the areas whose routes were retired (console card 003)", () => {
  it.each(Object.keys(SCREENS) as RetiredAreaId[])(
    "%s says what it was for, that it is not connected here and what replaces it, and requests nothing",
    (id) => {
      const fake = fakeTransport({});
      const client = new Client(fake.transport, "127.0.0.1");
      clients.push(client);
      const Screen = SCREENS[id];
      render(
        <ClientProvider client={client}>
          <Screen />
        </ClientProvider>,
      );
      const notice = RETIRED_AREAS[id];
      const text = screen.getByTestId("retired-area").textContent ?? "";
      expect(text).toContain(`${notice.area} was for `);
      expect(text).toContain("It is not connected here");
      expect(text).toContain("the console sends no command to the instrument");
      expect(text).toContain("Instead, ");
      expect(text).toMatch(/a plan is drafted for the person to approve|a running plan can be asked to stop/);
      expect(screen.queryAllByRole("button")).toHaveLength(0);
      expect(screen.queryAllByRole("textbox")).toHaveLength(0);
      expect(fake.calls).toEqual([]); // no request of any kind, retired route or not
    },
  );

  it("every retired area is still in the navigation, so the notice can be found", () => {
    const ids = AREAS.map((a) => a.id) as string[];
    for (const id of Object.keys(SCREENS)) expect(ids).toContain(id);
  });
});

describe("no web source names a retired route", () => {
  const sources = import.meta.glob("../**/*.{ts,tsx}", { query: "?raw", import: "default", eager: true }) as Record<
    string,
    string
  >;
  // a route, not a module path such as `server/api/hardware.GateRow` in a model's docstring
  const RETIRED = /(?<![\w/])\/api\/(commands|hardware|map|objective|patterns|sample|sessions)\b/;

  it("reads every non-test source file", () => {
    const files = Object.keys(sources).filter((f) => !/\.test\.(ts|tsx)$/.test(f));
    expect(files.length).toBeGreaterThan(50);
    expect(files.some((f) => f.endsWith("/api/schema.ts"))).toBe(true);
  });

  it("finds none of the retired routes, in the schema or in any screen", () => {
    const hits = Object.entries(sources)
      .filter(([f]) => !/\.test\.(ts|tsx)$/.test(f))
      .filter(([, text]) => RETIRED.test(text))
      .map(([f]) => f);
    expect(hits).toEqual([]);
  });

  it("the guard itself fires on a retired route", () => {
    expect(RETIRED.test('client.post("/api/commands", cmd)')).toBe(true);
    expect(RETIRED.test("`/api/sample/${id}`")).toBe(true);
    expect(RETIRED.test("/api/console/runs")).toBe(false);
    expect(RETIRED.test("server/api/hardware.GateRow")).toBe(false);
  });
});
