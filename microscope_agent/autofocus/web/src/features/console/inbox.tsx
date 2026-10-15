/** Inbox threads and their rounds (ui-spec 7.1). */

import type { InboxThread } from "./api";
import { Fields, isRecord, Json, shortTime, show } from "./ui";

const ENVELOPE = ["direction", "trigger", "answerability", "supersedes"] as const;

export function Inbox({ threads }: { threads: InboxThread[] }) {
  if (threads.length === 0) return <p className="console-muted">No inbox threads.</p>;
  return (
    <section aria-label="Inbox">
      {threads.map((t) => (
        <details key={t.thread} className="console-thread">
          <summary>
            <strong>{t.thread}</strong> {t.agent ?? "bridge only"} · {t.state ?? "—"} · round {show(t.round)} · turn{" "}
            {t.turn ?? "—"} · {shortTime(t.updated_at)}
          </summary>
          {t.messages.length === 0 && <p className="console-muted">No messages in a seat's inbox.</p>}
          {t.messages.map((m) => {
            const card = isRecord(m.card) ? m.card : undefined;
            return (
              <div key={m.name} className="console-message">
                <h3>{m.name} <span className="console-muted">round {show(m.round)}, {m.kind}</span></h3>
                {card !== undefined && (
                  <>
                    <Fields obj={card} keys={ENVELOPE} />
                    <Fields
                      obj={{
                        unit_consistency: isRecord(card.unit_consistency) ? card.unit_consistency.verdict : undefined,
                        value_comparison: isRecord(card.value_comparison) ? card.value_comparison.verdict : undefined,
                      }}
                      keys={["unit_consistency", "value_comparison"]}
                    />
                    <Json label="Envelope JSON" value={card} />
                  </>
                )}
                {m.text !== null && <pre className="console-text">{m.text}</pre>}
              </div>
            );
          })}
          {t.status !== null && <Json label="Bridge status.json" value={t.status} />}
        </details>
      ))}
    </section>
  );
}
