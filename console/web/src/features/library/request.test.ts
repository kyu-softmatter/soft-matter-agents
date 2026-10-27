import { describe, expect, it } from "vitest";

import fixture from "./shapes.fixture.json";
import {
  attachedName,
  buildAdd,
  buildAsk,
  buildOffer,
  buildWithdraw,
  EMPTY_ADD,
  EMPTY_WITHDRAW,
  NOT_SENT,
  previewItemId,
  sendOutcome,
} from "./request";

/** The request forms' own check (console card 016): the shapes the fixture holds are what the builders make. */

const ID = fixture.item_id;

function built(c: { form: string; input: unknown }) {
  const f = c.input as never;
  if (c.form === "add") return buildAdd(f, ID);
  if (c.form === "withdraw") return buildWithdraw(f, ID);
  if (c.form === "offer") return buildOffer(f);
  return buildAsk(f);
}

describe("each form builds the shape the librarian's request schema has", () => {
  for (const c of fixture.cases) {
    it(c.name, () => {
      const got = built(c);
      expect(got.ok).toBe(true);
      if (got.ok) expect(got.request).toEqual(c.request);
    });
  }
});

describe("the check", () => {
  it("names what is missing instead of guessing", () => {
    const got = buildAdd(EMPTY_ADD, ID);
    expect(got.ok).toBe(false);
    if (!got.ok) expect(got.problems.length).toBeGreaterThanOrEqual(3);
  });

  it("wants a unit with every value and a number for it", () => {
    const base = { ...EMPTY_ADD, sourceKind: "operator_recall" as const, readBy: "k", factWanted: "x" };
    expect(buildAdd({ ...base, value: "1.5", unit: "" }, ID).ok).toBe(false);
    expect(buildAdd({ ...base, value: "abc", unit: "mm" }, ID).ok).toBe(false);
    expect(buildAdd({ ...base, value: "1.5", unit: "mm" }, ID).ok).toBe(true);
  });

  it("gives a remembered value no file", () => {
    const base = { ...EMPTY_ADD, sourceKind: "operator_recall" as const, readBy: "k", factWanted: "x", value: "1.5", unit: "mm" };
    expect(buildAdd(base, ID).ok).toBe(true);
    expect(buildAdd({ ...base, fileName: "note.pdf" }, ID).ok).toBe(false);
  });

  it("wants an entry name as the store spells one", () => {
    const base = { ...EMPTY_WITHDRAW, entryId: "dia_lamp_power", reason: "wrong" };
    expect(buildWithdraw(base, ID).ok).toBe(true);
    for (const bad of ["Bad Name", "1abc", "dia-lamp", "Dia_lamp"]) {
      expect(buildWithdraw({ ...base, entryId: bad }, ID).ok, bad).toBe(false);
    }
  });

  it("refuses a result card path that is not a result card", () => {
    expect(buildOffer({ resultCard: "microscope_agent/questions/q1/plan.json", fact: "x" }).ok).toBe(false);
    expect(buildOffer({ resultCard: "../x/questions/q1/result_a.json", fact: "x" }).ok).toBe(false);
  });

  it("makes an attached file's name from the item id and a cleaned name", () => {
    expect(attachedName(ID, "ZYLA datasheet.pdf")).toBe(`${ID}--ZYLA_datasheet.pdf`);
    expect(attachedName(ID, "...")).toBeNull();
  });

  it("makes an item id of the inbox's shape for the check only", () => {
    expect(previewItemId(new Date(Date.UTC(2026, 9, 26, 10, 15, 0)), () => 0)).toBe("ci-20261026-101500-aaaa");
  });
});

describe("Send", () => {
  it("never sends: a good form and a bad one both answer not sent", () => {
    const good = sendOutcome(buildAsk({ question: "what is the lamp power?", conditions: "" }));
    expect(good).toEqual({ sent: false, message: NOT_SENT, problems: [] });
    const bad = sendOutcome(buildAsk({ question: "", conditions: "" }));
    expect(bad.sent).toBe(false);
    expect(bad.problems.length).toBe(1);
  });
});
