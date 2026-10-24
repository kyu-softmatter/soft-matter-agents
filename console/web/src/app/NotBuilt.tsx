/**
 * A screen of an area that is not built yet (console card 008): its title, one sentence of what it
 * will show, and "not built yet". It has no client, no effect and no control, so it requests nothing.
 */
export function NotBuilt({ title, shows }: { title: string; shows: string }) {
  return (
    <section className="not-built" aria-label={title}>
      <h2>{title}</h2>
      <p className="muted">{shows}</p>
      <p>
        <span className="chip">not built yet</span>
      </p>
    </section>
  );
}
