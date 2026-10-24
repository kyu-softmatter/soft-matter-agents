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
  const link = (e: AreaEntry) => (
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
  );
  const everyone = entries.filter((e) => !e.adminOnly);
  const admin = entries.filter((e) => e.adminOnly);
  return (
    <nav className="sidebar" aria-label="Areas">
      <span className="brand">Soft-matter agents</span>
      {everyone.map(link)}
      {admin.length > 0 && <hr className="sidebar-rule" />}
      {admin.map(link)}
    </nav>
  );
}

/**
 * The app frame: a left sidebar of areas (Admin below a rule, for an administrator only), the
 * area screen, and a footer on every screen. The shell has no hardware logic; screens talk to the
 * server API only. What the footer holds is the app's to say (`footer`), so the shell stays a frame.
 */
export function Shell({
  registry = defaultRegistry,
  footer,
  admin = false,
}: {
  registry?: AreaEntry[];
  /** the logged-in user is an administrator: admin-only areas show in the sidebar and open */
  admin?: boolean;
  footer?: ReactNode;
}) {
  const [area, go] = useArea();
  // An administrator-only area is not opened for anyone else, whatever the address says.
  const visible = registry.filter((e) => admin || !e.adminOnly);
  const entry = visible.find((e) => e.id === area) ?? visible[0];
  return (
    <ScreenContextProvider area={entry.id}>
      <div className="shell">
        <Nav entries={visible} current={entry.id} onSelect={go} />
        <main className="main">
          <AreaView key={entry.id} entry={entry} />
        </main>
        <footer className="shell-footer" data-testid="shell-footer" aria-label="Footer">
          {footer ?? <span className="muted">not connected</span>}
        </footer>
      </div>
    </ScreenContextProvider>
  );
}
