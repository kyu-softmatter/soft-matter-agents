/**
 * The Library's request forms (console cards 016 and 020): what each form hands the librarian, and the
 * console's own check of the form. A good form is sent as the words exactly as typed, the request without the
 * field that holds those words (the server sets that field from the words), and at most one file. The server
 * writes it into the librarian's inbox. A request is never an instruction to write: the librarian decides.
 *
 * The shapes are the four kinds of `console_store_request.schema.json`. `shapes.fixture.json` holds one case per
 * shape, and a pytest delivers each through the server's own writer and validates the item against that schema,
 * so this file cannot drift from it unnoticed.
 */

export const SENT = "Sent to the librarian.";

export const REMEMBERED_NOTE =
  "A remembered value enters at the lowest grade. The grade comes from the kind of source and is never chosen here.";
export const WORDS_ALONE_NOTE =
  "Words alone cannot refute a value. To refute it, give a reading or a document, or name the entry that replaces it; otherwise the librarian keeps it and says why. Nothing is erased.";

export type SourceKind = "spec" | "literature" | "operator_read" | "operator_recall";

export const SOURCE_KINDS: { id: SourceKind; label: string }[] = [
  { id: "spec", label: "A maker's document" },
  { id: "literature", label: "A paper" },
  { id: "operator_read", label: "Read off the instrument" },
  { id: "operator_recall", label: "I remember it" },
];

export type EvidenceKind = "none" | "reading" | "document" | "replacing_entry";

export const EVIDENCE_KINDS: { id: EvidenceKind; label: string }[] = [
  { id: "none", label: "None, only my words" },
  { id: "reading", label: "A reading" },
  { id: "document", label: "A document" },
  { id: "replacing_entry", label: "An entry that replaces it" },
];

export interface AddForm {
  sourceKind: SourceKind;
  readBy: string;
  /** the name of the file the person picked, or "" */
  fileName: string;
  value: string;
  unit: string;
  factWanted: string;
}

export interface WithdrawForm {
  entryId: string;
  reason: string;
  evidence: EvidenceKind;
  readBy: string;
  value: string;
  unit: string;
  /** a reading may name a document too; a document evidence must */
  fileName: string;
  documentKind: "spec" | "literature";
  replacingEntryId: string;
}

export interface OfferForm {
  resultCard: string;
  fact: string;
}

export interface AskForm {
  question: string;
  conditions: string;
}

export type Request = Record<string, unknown>;
/** `words` is the text of the one field the server sets from it, exactly as typed; `request` leaves that field out. */
export type Built = { ok: true; words: string; request: Request } | { ok: false; problems: string[] };

export const EMPTY_ADD: AddForm = { sourceKind: "spec", readBy: "", fileName: "", value: "", unit: "", factWanted: "" };
export const EMPTY_WITHDRAW: WithdrawForm = {
  entryId: "", reason: "", evidence: "none", readBy: "", value: "", unit: "", fileName: "",
  documentKind: "spec", replacingEntryId: "",
};
export const EMPTY_OFFER: OfferForm = { resultCard: "", fact: "" };
export const EMPTY_ASK: AskForm = { question: "", conditions: "" };

const ENTRY_ID = /^[a-z][a-z0-9_]*$/;
const RESULT_CARD = /^(microscope_agent|simulation_agent)\/questions\/[a-z0-9-]+\/result_[A-Za-z0-9_.-]+\.json$/;

/** An attached file's name as the inbox may keep it: cleaned to what a file name may hold. The server adds the item id. */
export function cleanName(fileName: string): string | null {
  const cleaned = fileName.trim().replace(/[^A-Za-z0-9._-]+/g, "_").replace(/^[^A-Za-z0-9]+/, "").slice(0, 128);
  return cleaned === "" ? null : cleaned;
}

function number(text: string): number | null {
  if (text.trim() === "") return null;
  const n = Number(text);
  return Number.isFinite(n) ? n : null;
}

/** A value with its unit, or the reasons it is not one. Both parts, or neither. */
function valueOf(text: string, unit: string, what: string, problems: string[]): { value: number; unit: string } | null {
  const v = number(text);
  if (v === null) {
    problems.push(text.trim() === "" ? `Give the ${what}.` : `The ${what} is not a number: "${text.trim()}".`);
    return null;
  }
  if (unit.trim() === "") {
    problems.push(`Give the unit of the ${what}, as you would write it.`);
    return null;
  }
  return { value: v, unit: unit.trim() };
}

function need(text: string, message: string, problems: string[]): string {
  if (text.trim() === "") problems.push(message);
  return text.trim();
}

function done(problems: string[], words: string, request: Request): Built {
  return problems.length > 0 ? { ok: false, problems } : { ok: true, words, request };
}

export function buildAdd(f: AddForm): Built {
  const problems: string[] = [];
  const readBy = need(f.readBy, f.sourceKind === "operator_recall" ? "Say who remembers the value." : "Say who read it.", problems);
  need(f.factWanted, "Say what to take, in your own words.", problems);
  const request: Request = { kind: "enter_document", source_kind: f.sourceKind, read_by: readBy };
  const file = f.fileName.trim() === "" ? null : cleanName(f.fileName);
  if (f.fileName.trim() !== "" && file === null) problems.push("The file's name has nothing the inbox can keep; rename the file.");
  if (f.sourceKind === "spec" || f.sourceKind === "literature") {
    if (f.fileName.trim() === "") problems.push(f.sourceKind === "spec" ? "Attach the maker's document." : "Attach the paper.");
    else if (file !== null) request.document = file;
  } else if (f.sourceKind === "operator_recall") {
    const v = valueOf(f.value, f.unit, "remembered value", problems);
    if (v !== null) request.value = v;
    if (f.fileName.trim() !== "") problems.push("A remembered value has no file: give the value and its unit.");
  } else {
    const hasValue = f.value.trim() !== "" || f.unit.trim() !== "";
    if (!hasValue && f.fileName.trim() === "") problems.push("Give the value you read with its unit, or attach the file you read it from.");
    if (hasValue) {
      const v = valueOf(f.value, f.unit, "value you read", problems);
      if (v !== null) request.value = v;
    }
    if (file !== null) request.document = file;
  }
  return done(problems, f.factWanted, request);
}

export function buildWithdraw(f: WithdrawForm): Built {
  const problems: string[] = [];
  const entry = f.entryId.trim();
  if (entry === "") problems.push("Give the name of the entry to withdraw.");
  else if (!ENTRY_ID.test(entry)) problems.push("An entry name is lowercase letters, digits and underscores, starting with a letter. Type or paste it as the page shows it.");
  need(f.reason, "Say why, in your own words.", problems);
  let evidence: Request = { kind: "none" };
  if (f.evidence === "reading") {
    const readBy = need(f.readBy, "Say who took the reading.", problems);
    const v = valueOf(f.value, f.unit, "reading", problems);
    evidence = { kind: "reading", read_by: readBy };
    if (v !== null) evidence.value = v;
    if (f.fileName.trim() !== "") {
      const file = cleanName(f.fileName);
      if (file === null) problems.push("The file's name has nothing the inbox can keep; rename the file.");
      else evidence.document = file;
    }
  } else if (f.evidence === "document") {
    evidence = { kind: "document", source_kind: f.documentKind };
    const file = f.fileName.trim() === "" ? null : cleanName(f.fileName);
    if (f.fileName.trim() === "") problems.push("Attach the document.");
    else if (file === null) problems.push("The file's name has nothing the inbox can keep; rename the file.");
    else evidence.document = file;
  } else if (f.evidence === "replacing_entry") {
    const id = f.replacingEntryId.trim();
    if (id === "") problems.push("Give the name of the entry that replaces it.");
    else if (!ENTRY_ID.test(id)) problems.push("The replacing entry's name is lowercase letters, digits and underscores, starting with a letter.");
    else evidence = { kind: "replacing_entry", entry_id: id };
  }
  return done(problems, f.reason, { kind: "withdraw_value", entry_id: entry, evidence });
}

export function buildOffer(f: OfferForm): Built {
  const problems: string[] = [];
  const card = f.resultCard.trim();
  if (card === "") problems.push("Give the path of the result card.");
  else if (!RESULT_CARD.test(card)) {
    problems.push("A result card's path looks like microscope_agent/questions/<question>/result_<name>.json (or simulation_agent/...).");
  }
  need(f.fact, "Say the fact in words.", problems);
  return done(problems, f.fact, { kind: "offer_result", result_card: card });
}

export function buildAsk(f: AskForm): Built {
  const problems: string[] = [];
  need(f.question, "Type the question.", problems);
  const request: Request = { kind: "ask" };
  if (f.conditions.trim() !== "") request.conditions = f.conditions.trim();
  return done(problems, f.question, request);
}

/** The one file a built request names, as the server will check it: `document` at the top or inside `evidence`. */
export function documentOf(request: Request): string | null {
  const direct = request.document;
  if (typeof direct === "string") return direct;
  const evidence = request.evidence;
  if (typeof evidence === "object" && evidence !== null) {
    const nested = (evidence as Record<string, unknown>).document;
    if (typeof nested === "string") return nested;
  }
  return null;
}
