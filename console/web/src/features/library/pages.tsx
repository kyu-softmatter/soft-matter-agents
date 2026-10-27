/**
 * The Library's pages (console card 016): the wiki's front page grouped by the kind of data, and each generated
 * page as it stands. A link to another wiki page is followed; a link to an entry or a guide is text and is never
 * followed. A page built from an older version of the store says so. Nothing shown here is kept or cited: a fact
 * is cited by its entry, never by a page.
 */

import type { ReactNode } from "react";

import { useClient } from "../../app/client";
import { areaHref } from "../../app/route";
import { Loaded, useLoad } from "../questions/ui";
import { type BlockOut, type IndexOut, PATHS, type PageOut, type SpanOut } from "./api";

export function ExampleNote({ note }: { note: string | null }) {
  return note === null ? null : (
    <p role="note" className="console-muted lib-example">
      <span className="console-tag">example data</span> {note}
    </p>
  );
}

export function pageHref(page: string): string {
  return areaHref("library", `pages/${page}`);
}

export function Spans({ spans }: { spans: readonly SpanOut[] }): ReactNode {
  return spans.map((s, i) => {
    const text = s.code ? <code>{s.text}</code> : s.text;
    return s.page === null ? <span key={i}>{text}</span> : <a key={i} href={pageHref(s.page)}>{text}</a>;
  });
}

function Block({ b }: { b: BlockOut }) {
  switch (b.type) {
    case "heading": {
      const level = Math.min(Math.max((b.level ?? 2) + 1, 3), 6);
      const Tag = `h${level}` as "h3" | "h4" | "h5" | "h6";
      return <Tag>{b.text}</Tag>;
    }
    case "paragraph":
      return <p><Spans spans={b.spans ?? []} /></p>;
    case "quote":
      return <blockquote><Spans spans={b.spans ?? []} /></blockquote>;
    case "list":
      return <ul>{(b.items ?? []).map((it, i) => <li key={i}><Spans spans={it} /></li>)}</ul>;
    case "code":
      return <pre className="console-text">{b.text}</pre>;
    case "table":
      return (
        <table className="console-table">
          <thead><tr>{(b.header ?? []).map((c, i) => <th key={i}><Spans spans={c} /></th>)}</tr></thead>
          <tbody>
            {(b.rows ?? []).map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j}><Spans spans={c} /></td>)}</tr>)}
          </tbody>
        </table>
      );
    case "rule":
      return <hr />;
  }
}

function Behind({ behind, note }: { behind: boolean; note: string | null }) {
  return behind || note !== null ? <p role="note" className="console-reason lib-behind">{note}</p> : null;
}

export function PagesIndex() {
  const client = useClient();
  const state = useLoad(() => client.get<IndexOut>(PATHS.index), [client]);
  return (
    <Loaded state={state}>
      {(d) => (
        <section aria-label="Pages" className="lib-pages">
          <ExampleNote note={d.example_note} />
          {d.state !== "shown" ? (
            <p>{d.message}</p>
          ) : (
            <>
              <h3>{d.title ?? "The library"}</h3>
              <Behind behind={d.behind} note={d.note} />
              {d.facts.length > 0 && (
                <dl className="console-fields" aria-label="About the store">
                  {d.facts.map((f) => (
                    <div key={f.label}><dt>{f.label}</dt><dd>{f.value}</dd></div>
                  ))}
                </dl>
              )}
              {d.groups.map((g) => (
                <section key={g.key} aria-label={g.title}>
                  <h4>{g.title}</h4>
                  <ul>
                    {g.links.map((l) => (
                      <li key={l.page}>
                        <a href={pageHref(l.page)}>{l.label}</a>
                        {l.entries !== null && <span className="console-muted"> ({l.entries} entries)</span>}
                      </li>
                    ))}
                  </ul>
                </section>
              ))}
              {d.registered_unused.length > 0 && (
                <section aria-label="Names with no entry yet">
                  <h4>Names with no entry yet</h4>
                  <p className="console-muted">{d.registered_unused.join(", ")}</p>
                </section>
              )}
              <p className="console-muted lib-footer">{d.footer}</p>
            </>
          )}
        </section>
      )}
    </Loaded>
  );
}

export function WikiPage({ id }: { id: string }) {
  const client = useClient();
  const state = useLoad(() => client.get<PageOut>(PATHS.page(id)), [client, id]);
  return (
    <section aria-label="Page" className="lib-page">
      <p><a href={areaHref("library", "pages")}>All pages</a></p>
      <Loaded state={state}>
        {(d) => (
          <>
            <ExampleNote note={d.example_note} />
            <Behind behind={d.behind} note={d.note} />
            <h3>{d.title}</h3>
            {d.blocks.map((b, i) => <Block key={i} b={b} />)}
            <p className="console-muted lib-footer">{d.footer}</p>
          </>
        )}
      </Loaded>
    </section>
  );
}
