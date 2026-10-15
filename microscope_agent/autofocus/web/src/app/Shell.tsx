import {
  Component,
  type ComponentType,
  type ErrorInfo,
  lazy,
  type ReactNode,
  Suspense,
  useMemo,
} from "react";

import { type AreaEntry, type AreaId, registry as defaultRegistry } from "./areas";
import { AssistantSlot } from "./AssistantSlot";
import { useArea } from "./route";
import { ScreenContextProvider } from "./screenContext";

export function Placeholder({ entry }: { entry: AreaEntry }) {
  return (
    <div className="placeholder" role="status">
      <h2>{entry.label}</h2>
      <p>{entry.label}: not implemented yet</p>
      <p className="muted">
        Add <code>web/src/features/{entry.id}/index.tsx</code> with a default-exported component.
      </p>
    </div>
  );
}

class AreaErrorBoundary extends Component<{ label: string; children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`area ${this.props.label} failed`, error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="placeholder" role="alert">
          <h2>{this.props.label}</h2>
          <p>This screen failed to load: {this.state.error.message}</p>
        </div>
      );
    }
    return this.props.children;
  }
}

function AreaView({ entry }: { entry: AreaEntry }) {
  // one lazy component per area entry; React keeps it across re-renders
  const Screen = useMemo<ComponentType | null>(() => (entry.load ? lazy(entry.load) : null), [entry]);
  if (Screen === null) return <Placeholder entry={entry} />;
  return (
    <AreaErrorBoundary key={entry.id} label={entry.label}>
      <Suspense fallback={<p className="muted">Loading {entry.label}…</p>}>
        <Screen />
      </Suspense>
    </AreaErrorBoundary>
  );
}

export function Nav({
  entries,
  current,
  onSelect,
}: {
  entries: AreaEntry[];
  current: AreaId;
  onSelect: (id: AreaId) => void;
}) {
  return (
    <nav className="nav" aria-label="Areas">
      {entries.map((e) => (
        <a
          key={e.id}
          href={`#/${e.id}`}
          aria-current={e.id === current ? "page" : undefined}
          className={e.load ? undefined : "not-ready"}
          onClick={(ev) => {
            ev.preventDefault();
            onSelect(e.id);
          }}
        >
          {e.label}
        </a>
      ))}
    </nav>
  );
}

/**
 * The app frame: header with the area navigation, the area screen, the prompt
 * box slot and the status bar slot. The shell has no hardware logic; screens
 * talk to the server API only.
 */
export function Shell({
  registry = defaultRegistry,
  statusBar,
  notice,
  admin = false,
}: {
  registry?: AreaEntry[];
  /** the logged-in user is an admin: admin-only areas show in the navigation */
  admin?: boolean;
  statusBar?: ReactNode;
  /** shown above the area screen, e.g. the last-shutdown light readback */
  notice?: ReactNode;
}) {
  const [area, go] = useArea();
  const entry = registry.find((e) => e.id === area) ?? registry[0];
  return (
    <ScreenContextProvider area={entry.id}>
      <div className="shell">
        <header className="header">
          <span className="title">Takatori Lab Console</span>
          <Nav entries={registry.filter((e) => admin || !e.adminOnly)} current={entry.id} onSelect={go} />
        </header>
        <main className="main">
          {notice}
          <AreaView key={entry.id} entry={entry} />
        </main>
        <aside className="side">
          <AssistantSlot />
        </aside>
        <footer className="status" aria-label="Status">
          {statusBar ?? <span className="muted">status: not connected</span>}
        </footer>
      </div>
    </ScreenContextProvider>
  );
}
