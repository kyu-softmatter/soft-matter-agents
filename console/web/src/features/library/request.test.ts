import { describe, expect, it } from "vitest";

import fixture from "./shapes.fixture.json";
import {
  buildAdd,
  buildAsk,
  buildOffer,
  buildWithdraw,
  cleanName,
  documentOf,
  EMPTY_ADD,
  EMPTY_WITHDRAW,
  SENT,
} from "./request";

/** The request forms' own check (console card 016): the shapes the fixture holds are what the builders make. */

function built(c: { form: string; input: unknown }) {
  const f = c.input as never;
  if (c.form === "add") return buildAdd(f);
  if (c.form === "withdraw") return buildWithdraw(f);
  if (c.form === "offer") return buildOffer(f);
  return buildAsk(f);
}

describe("each form builds the shape the librarian's request schema has", () => {
  for (const c of fixture.cases) {
    it(c.name, () => {
      const got = built(c);
      expect(got.ok).toBe(true);
      if (got.ok) {
        expect(got.request).toEqual(c.request);
        expect(got.words).toBe(c.words);
      }
    });
  }

  it("leaves the field that holds the words out of the request, and names a file by its plain name", () => {
    for (const c of fixture.cases) {
      const got = built(c);
      if (!got.ok) throw new Error(c.name);
      for (const field of ["fact_wanted", "reason", "fact_in_words", "question"]) expect(got.request).not.toHaveProperty(field);
      const name = documentOf(got.request);
      expect(name).toBe("file" in c ? c.file : null);
      if (name !== null) expect(name).toMatch(/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/);
    }
  });

  it("hands the words exactly as typed, not trimmed", () => {
    const got = buildAsk({ question: "  what is the lamp power?\n", conditions: "" });
    expect(got.ok && got.words).toBe("  what is the lamp power?\n");
  });
});

describe("the check", () => {
  it("names what is missing instead of guessing", () => {
    const got = buildAdd(EMPTY_ADD);
    expect(got.ok).toBe(false);
    if (!got.ok) expect(got.problems.length).toBeGreaterThanOrEqual(3);
  });

  it("wants a unit with every value and a number for it", () => {
    const base = { ...EMPTY_ADD, sourceKind: "operator_recall" as const, readBy: "k", factWanted: "x" };
    expect(buildAdd({ ...base, value: "1.5", unit: "" }).ok).toBe(false);
    expect(buildAdd({ ...base, value: "abc", unit: "mm" }).ok).toBe(false);
    expect(buildAdd({ ...base, value: "1.5", unit: "mm" }).ok).toBe(true);
  });

  it("gives a remembered value no file", () => {
    const base = { ...EMPTY_ADD, sourceKind: "operator_recall" as const, readBy: "k", factWanted: "x", value: "1.5", unit: "mm" };
    expect(buildAdd(base).ok).toBe(true);
    expect(buildAdd({ ...base, fileName: "note.pdf" }).ok).toBe(false);
  });

  it("wants an entry name as the store spells one", () => {
    const base = { ...EMPTY_WITHDRAW, entryId: "dia_lamp_power", reason: "wrong" };
    expect(buildWithdraw(base).ok).toBe(true);
    for (const bad of ["Bad Name", "1abc", "dia-lamp", "Dia_lamp"]) {
      expect(buildWithdraw({ ...base, entryId: bad }).ok, bad).toBe(false);
    }
  });

  it("refuses a result card path that is not a result card", () => {
    expect(buildOffer({ resultCard: "microscope_agent/questions/q1/plan.json", fact: "x" }).ok).toBe(false);
    expect(buildOffer({ resultCard: "../x/questions/q1/result_a.json", fact: "x" }).ok).toBe(false);
  });

  it("cleans an attached file's name to what the inbox keeps", () => {
    expect(cleanName("ZYLA datasheet.pdf")).toBe("ZYLA_datasheet.pdf");
    expect(cleanName("  ..hidden.pdf")).toBe("hidden.pdf");
    expect(cleanName("a".repeat(200))).toHaveLength(128);
    expect(cleanName("...")).toBeNull();
  });

  it("finds the one file a request names, at the top or in its evidence", () => {
    expect(documentOf({ kind: "enter_document", document: "a.pdf" })).toBe("a.pdf");
    expect(documentOf({ kind: "withdraw_value", evidence: { kind: "document", document: "b.pdf" } })).toBe("b.pdf");
    expect(documentOf({ kind: "ask" })).toBeNull();
  });

  it("reports a problem with an empty question, and a sent form says so in the librarian's words", () => {
    const bad = buildAsk({ question: "", conditions: "" });
    expect(bad.ok).toBe(false);
    if (!bad.ok) expect(bad.problems.length).toBe(1);
    expect(SENT).toBe("Sent to the librarian.");
  });
});
