/**
 * Library area (console cards 016 and 020): the librarian's generated pages grouped by the kind of data, the data
 * map, and four request forms with the list of requests. It shows generated files and the librarian's inbox and
 * answers and nothing else of the store, holds no caller id and keeps nothing. Send delivers the request into
 * the librarian's inbox; the list then shows it.
 * `rest` forms (after `#/library/`): "" | "pages" | "pages/<page>" | "map" | "ask" | "add" | "withdraw" | "offer".
 */

import { useMemo, useState } from "react";

import { useAreaPath } from "../../app/route";
import { useScreenContext } from "../../app/screenContext";
import "../questions/console.css";
import "./library.css";
import { DataMap } from "./dataMap";
import { AddDocument, AskLibrarian, OfferResult, WithdrawValue } from "./forms";
import { PagesIndex, WikiPage } from "./pages";
import { Requests } from "./requests";

type Tab = "pages" | "map" | "ask" | "add" | "withdraw" | "offer";

const TABS: { id: Tab; label: string }[] = [
  { id: "pages", label: "Pages" },
  { id: "map", label: "Data map" },
  { id: "ask", label: "Ask the librarian" },
  { id: "add", label: "Add a document or value" },
  { id: "withdraw", label: "Withdraw a value" },
  { id: "offer", label: "Offer a result" },
];

export function parseRoute(rest: string): { tab: Tab; page: string | null } {
  const parts = rest.replace(/[?#].*$/, "").split("/").filter((p) => p !== "");
  const tab = TABS.find((t) => t.id === parts[0])?.id ?? "pages";
  return { tab, page: tab === "pages" && parts[1] !== undefined ? parts[1] : null };
}

export default function LibraryScreen() {
  const [rest, setRest] = useAreaPath();
  const { tab, page } = parseRoute(rest);
  const details = useMemo(() => ({ tab, page }), [tab, page]);
  useScreenContext(details);
  const [sent, setSent] = useState(0);
  const onSent = () => setSent((n) => n + 1);
  return (
    <div className="console lib">
      <h2>Library</h2>
      <p className="console-muted">Send the librarian a request. The librarian decides, and nothing is ever erased.</p>
      <nav role="tablist" aria-label="Library" className="console-tabs">
        {TABS.map((t) => (
          <button key={t.id} type="button" role="tab" aria-selected={tab === t.id} onClick={() => setRest(t.id)}>
            {t.label}
          </button>
        ))}
      </nav>
      {tab === "pages" && (page === null ? <PagesIndex /> : <WikiPage id={page} />)}
      {tab === "map" && <DataMap />}
      {tab === "ask" && <AskLibrarian onSent={onSent} />}
      {tab === "add" && <AddDocument onSent={onSent} />}
      {tab === "withdraw" && <WithdrawValue onSent={onSent} />}
      {tab === "offer" && <OfferResult onSent={onSent} />}
      {(tab === "ask" || tab === "add" || tab === "withdraw" || tab === "offer") && <Requests refresh={sent} />}
    </div>
  );
}
