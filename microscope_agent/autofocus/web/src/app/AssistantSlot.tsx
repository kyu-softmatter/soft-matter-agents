import { type ComponentType, lazy, Suspense, useMemo } from "react";

/**
 * Where the shared prompt box sits on every screen (PLAN X1). The component is
 * T-014's, in `src/app/assistant/index.tsx` (default export, no props; it reads
 * the screen with useCurrentScreenContext). Until that file exists the slot
 * shows a placeholder.
 */
type PromptModule = { default: ComponentType };
type PromptLoader = () => Promise<PromptModule>;

const found = import.meta.glob<PromptModule>("./assistant/index.tsx");

export function assistantLoaderFrom(modules: Record<string, PromptLoader>): PromptLoader | undefined {
  return Object.values(modules)[0];
}

const defaultLoad = assistantLoaderFrom(found);

/** The slot with a given loader (tests pass `assistantLoaderFrom({})` for the placeholder). */
export function AssistantSlotView({ load }: { load: PromptLoader | undefined }) {
  const PromptBox = useMemo(() => (load ? lazy(load) : null), [load]);
  return (
    <section className="assistant-slot" aria-label="Prompt">
      {PromptBox ? (
        <Suspense fallback={<p className="muted">Loading prompt box…</p>}>
          <PromptBox />
        </Suspense>
      ) : (
        <p className="muted">Prompt box: not implemented yet</p>
      )}
    </section>
  );
}

/** The slot as the app uses it: T-014's prompt box once it is in the build. */
export function AssistantSlot() {
  return <AssistantSlotView load={defaultLoad} />;
}
