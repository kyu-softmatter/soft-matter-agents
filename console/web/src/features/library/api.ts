/**
 * The Library screen's wire types and paths (console cards 016 and 020). The reads are of the librarian's
 * generated pages and of the librarian's inbox and answers; the one write is `POST /api/library/requests`,
 * which the server writes as an item into the librarian's inbox. The console holds no caller id and asks the
 * store nothing.
 */

import { type Client, CommandRefused } from "../../app/client";
import type { components } from "../../api/schema";

type Schemas = components["schemas"];

export type IndexOut = Schemas["IndexOut"];
export type PageOut = Schemas["PageOut"];
export type MapOut = Schemas["MapOut"];
export type RequestsOut = Schemas["RequestsOut"];
export type RequestView = Schemas["RequestViewOut"];
export type AnswerOut = Schemas["AnswerOut"];
export type UnreadableOut = Schemas["UnreadableOut"];
export type StoreRequest = Schemas["StoreRequestOut"];
export type RequestIn = Schemas["RequestIn"];
export type BlockOut = Schemas["BlockOut"];
export type SpanOut = Schemas["Span"];

export const PATHS = {
  index: "/api/library/index",
  page: (id: string) => `/api/library/pages/${encodeURIComponent(id)}`,
  map: "/api/library/map",
  requests: "/api/library/requests",
};

/** `POST /api/library/requests`: the item the server wrote. Every refusal is thrown with its reason, in words. */
export async function sendRequest(client: Client, body: RequestIn): Promise<StoreRequest> {
  const r = await client.post<StoreRequest>(PATHS.requests, body);
  if (r === null) throw new CommandRefused(502, "the server returned no item");
  return r;
}
