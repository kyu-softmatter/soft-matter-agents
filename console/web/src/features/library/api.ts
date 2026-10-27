/**
 * The Library screen's wire types and paths (console card 016). Every route is a read of the librarian's
 * generated pages; there is no route that sends. The console holds no caller id and asks the store nothing.
 */

import type { components } from "../../api/schema";

type Schemas = components["schemas"];

export type IndexOut = Schemas["IndexOut"];
export type PageOut = Schemas["PageOut"];
export type MapOut = Schemas["MapOut"];
export type AnswersOut = Schemas["AnswersOut"];
export type AnswerOut = Schemas["AnswerOut"];
export type BlockOut = Schemas["BlockOut"];
export type SpanOut = Schemas["Span"];

export const PATHS = {
  index: "/api/library/index",
  page: (id: string) => `/api/library/pages/${encodeURIComponent(id)}`,
  map: "/api/library/map",
  answers: "/api/library/answers",
};
