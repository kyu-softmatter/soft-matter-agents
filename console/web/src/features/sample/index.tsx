/**
 * `sample` area: samples and the loading check (PLAN F3; contract docs/screens/sample.md).
 *
 * Route rest: `?sample_id=<id>` views that sample; empty views the sample the
 * engine has open. Viewing is not opening: "Open" sends `sample_open`.
 *
 * The screen decides nothing: refusals come from the server (403 detail,
 * /api/permissions, /api/sample/access) or the engine (`preflight_failed`), and
 * the loading state comes from the engine's sample view. All traffic goes
 * through the shell's client.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  type CommandInput,
  CommandRefused,
  type EventOut,
  useClient,
  useEngineEvents,
  useEventsConnected,
  useReadOnly,
} from "../../app/client";
import { useAreaPath } from "../../app/route";
import { useScreenContext } from "../../app/screenContext";
import { readLights } from "../../app/status";
import { placeholderNotice } from "../../app/unavailable";
import {
  CHECKING_PERMISSIONS,
  type CurrentSample,
  type Geometry,
  type GeometryField,
  type LoadingState,
  PATHS,
  type Permissions,
  READ_ONLY_REMOTE,
  readPermissions,
  SAMPLE_OPS,
  type SampleAccess,
  type SampleDetail,
  type SampleOp,
  type SampleSummary,
} from "./api";
import { GeometryForm, LoadingCheck, Reason, SampleList, SampleSummaryPanel } from "./parts";
import "./sample.css";

function sampleIdOf(rest: string): string | null {
  const q = rest.startsWith("?") ? rest.slice(1) : rest;
  return new URLSearchParams(q).get("sample_id");
}

const isSampleOp = (op: unknown): op is SampleOp => (SAMPLE_OPS as readonly unknown[]).includes(op);

const start = (op: SampleOp, args: Record<string, unknown> = {}): CommandInput => ({
  kind: "start",
  op,
  op_id: "",
  args,
});

/** which control a command belongs to, so its refusal shows next to it */
function controlOf(op: SampleOp, args: Record<string, unknown>): string {
  switch (op) {
    case "sample_open":
      return `open:${String(args.sample_id)}`;
    case "sample_new":
      return "new";
    case "sample_geometry_set":
      return "geometry";
    case "loading_confirm_person":
      return "person";
    case "loading_check_image":
      return "image";
  }
}

/** preflight_failed carries `checks: [{name, ok, why}]` (ui-spec 4.0) or a plain `why` */
function failureText(ev: EventOut): string {
  const d = ev.data ?? {};
  if (ev.kind === "error") return `error: ${String(d.message ?? "unknown")}`;
  if (ev.kind === "aborted") return `stopped: ${String(d.why ?? "unknown")}`;
  const checks = Array.isArray(d.checks) ? (d.checks as { ok?: boolean; why?: string; name?: string }[]) : [];
  const why = checks.filter((c) => c.ok === false).map((c) => c.why ?? c.name ?? "check failed");
  return why.length > 0 ? why.join("; ") : String(d.why ?? "refused");
}

interface Selected {
  detail: SampleDetail;
  geometry: Geometry;
  loading: LoadingState;
}

export default function SampleScreen() {
  const client = useClient();
  const { readOnly, why: readOnlyWhy } = useReadOnly();
  const connected = useEventsConnected();
  const [rest, setRest] = useAreaPath();
  const [list, setList] = useState<SampleSummary[]>([]);
  const [fields, setFields] = useState<GeometryField[]>([]);
  const [current, setCurrent] = useState<CurrentSample | null>(null);
  const [selected, setSelected] = useState<Selected | null>(null);
  const [access, setAccess] = useState<SampleAccess | null>(null);
  const [perms, setPerms] = useState<Permissions | null>(null);
  const [error, setError] = useState<string | null>(null);
  // the placeholder engine has no sample store: one notice instead of the 503 (app/unavailable)
  const [unavailable, setUnavailable] = useState<string | null>(null);
  const fail = useCallback((e: Error) => {
    const notice = placeholderNotice(e);
    if (notice !== null) setUnavailable(notice);
    else setError(e.message);
  }, []);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [imageStatus, setImageStatus] = useState<string | null>(null);
  const [light, setLight] = useState<string | null>(null);
  const [tick, setTick] = useState(0); // bump to re-read everything
  const pending = useRef(new Map<string, string>()); // op_id -> control

  const viewId = sampleIdOf(rest) ?? current?.sample_id ?? null;
  const refresh = useCallback(() => setTick((t) => t + 1), []);

  // events in a gap are lost: re-read everything when the socket opens again
  useEffect(() => {
    if (connected) refresh();
  }, [connected, refresh]);

  useEffect(() => {
    let live = true;
    Promise.all([
      client.get<SampleSummary[]>(PATHS.list),
      client.get<GeometryField[]>(PATHS.fields),
      client.get<{ sample?: CurrentSample | null }>(PATHS.state),
    ])
      .then(([l, f, s]) => {
        if (!live) return;
        setList(l);
        setFields(f);
        setCurrent(s.sample ?? null);
      })
      .catch((e: Error) => live && fail(e));
    return () => {
      live = false;
    };
  }, [client, tick]);

  useEffect(() => {
    let live = true;
    void readPermissions(client).then((p) => live && setPerms(p));
    client
      .get<SampleAccess>(PATHS.access(viewId))
      .then((a) => live && setAccess(a))
      .catch((e: Error) => live && fail(e));
    if (viewId === null) {
      setSelected(null);
      return () => {
        live = false;
      };
    }
    Promise.all([
      client.get<SampleDetail>(PATHS.detail(viewId)),
      client.get<Geometry>(PATHS.geometry(viewId)),
      client.get<LoadingState>(PATHS.loading(viewId)),
    ])
      .then(([detail, geometry, loading]) => live && setSelected({ detail, geometry, loading }))
      .catch((e: Error) => live && fail(e));
    return () => {
      live = false;
    };
  }, [client, viewId, tick]);

  const setReason = useCallback((control: string, why: string | null) => {
    setReasons((r) => {
      const next = { ...r };
      if (why) next[control] = why;
      else delete next[control];
      return next;
    });
  }, []);

  const onEvent = useCallback(
    (ev: EventOut) => {
      const control = pending.current.get(ev.op_id);
      // sample_opened and map_changed join EVENT_KINDS with T-011; until then the schema does not name them
      switch (ev.kind as string) {
        case "sample_opened":
          setRest("");
          refresh();
          return;
        case "map_changed":
          refresh();
          return;
        case "light_changed": {
          // the one light shape, through the shell's reader (T-010-6)
          const lamp = readLights(ev.data)?.lights.find((l) => l.name === "DiaLamp");
          setLight(lamp === undefined ? null : lamp.on === null ? "unknown" : lamp.on ? "on" : "off");
          return;
        }
        case "started":
        case "progress":
          if (control === "image") setImageStatus(String(ev.data?.status ?? "Checking…"));
          return;
        case "preflight_failed":
        case "aborted":
        case "error":
          if (control) setReason(control, failureText(ev));
          if (control === "image") setImageStatus(null);
          pending.current.delete(ev.op_id);
          refresh(); // the engine's answer to "may I" may have changed
          return;
        case "finished": {
          if (control === "image") setImageStatus(null);
          pending.current.delete(ev.op_id);
          const op = ev.data?.op;
          if (!isSampleOp(op)) return;
          const summary = (ev.data?.summary ?? {}) as { sample_id?: unknown };
          if (op === "sample_new" && typeof summary.sample_id === "string") {
            setRest(`?sample_id=${encodeURIComponent(summary.sample_id)}`);
          }
          refresh();
          return;
        }
      }
    },
    [refresh, setReason, setRest],
  );
  useEngineEvents(onEvent);

  const send = useCallback(
    async (op: SampleOp, args: Record<string, unknown> = {}) => {
      const control = controlOf(op, args);
      setReason(control, null);
      try {
        const opId = await client.command(start(op, args));
        pending.current.set(opId, control);
      } catch (e) {
        setReason(control, e instanceof CommandRefused ? e.detail : String(e));
      }
    },
    [client, setReason],
  );

  const openFolder = useCallback(async () => {
    if (!selected) return;
    try {
      await client.post(PATHS.openFolder(selected.detail.sample_id));
      setReason("folder", null);
    } catch (e) {
      setReason("folder", e instanceof CommandRefused ? e.detail : String(e));
    }
  }, [client, selected, setReason]);

  // ui-spec 7.0 order: read-only (shell), then the shared verdict, then the sample-specific one
  const readOnlyText = readOnly ? (readOnlyWhy === "remote view" || !readOnlyWhy ? READ_ONLY_REMOTE : `Read-only: ${readOnlyWhy}`) : null;
  const denied = (op: SampleOp): string | null => {
    if (readOnlyText) return readOnlyText;
    if (perms === null) return CHECKING_PERMISSIONS;
    const p = perms[op];
    return p.allowed ? null : (p.reason ?? `${op} is not allowed now`);
  };
  const openBlocked = denied("sample_open") ?? access?.open_reason ?? null;
  const newBlocked = denied("sample_new") ?? access?.open_reason ?? null;
  const id = selected?.detail.sample_id ?? null;

  const details = useMemo(() => {
    if (!selected) return {};
    const geometry = Object.fromEntries(
      Object.entries(selected.geometry.values).map(([k, v]) => [k, { value: v.value, source: v.source.kind }]),
    );
    const l = selected.loading;
    return {
      sample_id: selected.detail.sample_id,
      geometry,
      loading: { geometry: l.geometry.done, person: l.person.done, image: l.image.done && l.image.ok === true, confirmed: l.confirmed },
    };
  }, [selected]);
  useScreenContext(details);

  if (unavailable !== null) {
    return (
      <div className="sample-screen">
        <h2>Sample</h2>
        <p className="muted" role="status">
          {unavailable}
        </p>
      </div>
    );
  }

  return (
    <div className="sample-screen">
      <h2>Sample</h2>
      {error && (
        <p className="sample-reason" role="alert">
          {error}
        </p>
      )}
      <section aria-label="Samples" className="sample-panel">
        <h3>Samples</h3>
        <p>
          <button disabled={newBlocked !== null} onClick={() => void send("sample_new")}>
            New sample
          </button>
          <Reason text={newBlocked ?? reasons.new} />
        </p>
        <SampleList
          samples={list}
          currentId={current?.sample_id ?? null}
          selectedId={id}
          onView={(sid) => setRest(`?sample_id=${encodeURIComponent(sid)}`)}
          onOpen={(sid) => void send("sample_open", { sample_id: sid })}
          openBlocked={openBlocked}
          reasons={reasons}
        />
      </section>
      {selected && id && (
        <>
          <SampleSummaryPanel
            detail={selected.detail}
            canOpenFolder={access?.can_open_folder === true && !readOnly}
            onOpenFolder={() => void openFolder()}
            folderReason={reasons.folder}
          />
          <GeometryForm
            fields={fields}
            geometry={selected.geometry}
            blocked={denied("sample_geometry_set")}
            reason={reasons.geometry}
            onSave={(values) => void send("sample_geometry_set", { sample_id: id, values })}
          />
          <LoadingCheck
            loading={selected.loading}
            personBlocked={denied("loading_confirm_person")}
            imageBlocked={denied("loading_check_image")}
            reasons={reasons}
            imageStatus={imageStatus}
            onPerson={() => void send("loading_confirm_person", { sample_id: id })}
            onImage={() => void send("loading_check_image", { sample_id: id })}
          />
          {light && <p className="muted">Brightfield: {light}</p>}
        </>
      )}
      {!selected && <p className="muted">No sample selected. Pick one from the list or make a new one.</p>}
    </div>
  );
}
