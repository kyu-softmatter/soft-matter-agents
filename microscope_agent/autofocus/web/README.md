# dino-autofocus web app

The browser UI (PLAN.md 5, D1). FastAPI (`python -m dino_autofocus.server`, T-009) serves the
built `web/dist`; Node is needed to build, not to run. Node comes from the uv `web` group, so
there is no system install: always go through `uv run`.

```
uv sync                                  # once: installs Node 22 into the repo env
uv run npm --prefix web ci               # install the locked packages
uv run npm --prefix web run dev          # dev server; /api and /ws go to 127.0.0.1:8765
uv run npm --prefix web test             # vitest (jsdom, no browser window)
uv run npm --prefix web run typecheck    # tsc --noEmit
uv run npm --prefix web run build        # typecheck + vite build -> web/dist (not committed)
uv run npm --prefix web run gen:api      # regenerate src/api/ from the server's OpenAPI
```

For `npm run dev`, start the server so it accepts the dev page's origin (T-009c checks the
`Origin` of every REST and WebSocket request):

```
uv run python -m dino_autofocus.server --dev-origin http://localhost:5173
```

The Vite dev server is pinned to `http://localhost:5173` (`strictPort`), so that origin stays
right. The proxy never rewrites `Origin`. Set `DINO_AF_SERVER` to point the proxy at another
server address. The built app served by the server itself needs no `--dev-origin`.

## Layout

| Path | Owner | What |
|---|---|---|
| `src/app/` | shell (T-010) | layout, navigation, area registry, screen context, status bar, shared components |
| `src/app/assistant/` | prompt box (T-014) | the prompt box on every screen. Not part of the shell |
| `src/api/` | generated | OpenAPI types from `npm run gen:api`. Never edited by hand |
| `src/features/<area>/` | that area's work package | the area's screen |
| `src/features/live/` | shell (T-010) | the live view |
| `package.json`, `package-lock.json` | T-010 only | ask the manager for a package; one session changes these at a time |

## Adding an area screen

The areas and their order are fixed in `src/app/areas.ts`: `console`, `hardware`, `sample`,
`map`, `objective`, `live`, `simulation`, `sessions`. Login (`src/app/login/`, T-105) is not an
area and has no navigation entry. To give an area its screen:

1. Create `src/features/<area>/index.tsx`.
2. Default-export a React component that takes no props.
3. That is all. The shell finds the file at build time (`import.meta.glob`) and lazy-loads it
   when the area is opened. Do not edit `src/app/`.

Until the file exists the shell shows "<Area>: not implemented yet". A folder whose name is not
one of the areas is ignored with a console warning; adding a new area is a shell change (ask the
manager). If the screen throws while loading, the shell shows the error inside the area and the
rest of the app keeps working.

Inside `src/features/<area>/` the area owns its files and folders. Keep imports from other
areas out; shared pieces belong in `src/app/` (ask for them).

## Routes and links between areas

Routes are hashes `#/<area>/<rest>`. The shell routes on `<area>` only and hands everything after
it, query included, to the area untouched. The area decides what `<rest>` means:

| Hash | Area | `rest` |
|---|---|---|
| `#/simulation/runs/run-20260924-001` | simulation | `runs/run-20260924-001` |
| `#/map?sample_id=20260930_1849_1` | map | `?sample_id=20260930_1849_1` |
| `#/console` | console | (empty) |

An unknown area falls back to the console. Inside a screen:

```tsx
import { areaHref, useAreaPath } from "../../app/route";

const [rest, setRest] = useAreaPath();        // read and change your own rest; no remount
<a href={areaHref("simulation", `runs/${runId}`)}>open run</a>   // link to another area
```

Linking is a plain href, so areas never import each other. Each area documents the `rest` forms it
accepts in its own `index.tsx`.

## Screen context for the prompt box

Every prompt carries the context of the screen in view (PLAN X1). The shell fills `area`. A
screen adds short ids and names only, never frames or file contents (PLAN D7):

```tsx
import { useMemo } from "react";
import { useScreenContext } from "../../app/screenContext";

export default function MapScreen() {
  const details = useMemo(() => ({ sample_id, region }), [sample_id, region]);
  useScreenContext(details);   // cleared when the screen unmounts or the area changes
  ...
}
```

The prompt box reads it with `useCurrentScreenContext()`. Its component goes in
`src/app/assistant/index.tsx` (default export, no props). The shell's prompt slot picks that
file up the same way as an area screen, with a placeholder until it exists.

## Shared components

- `FocusVerdict` (`src/app/Verdict.tsx`): `<FocusVerdict verdict={v} source="computed" | "model" />`.
  Only the five words `in_focus | step_up | step_down | no_sample_here | unsure`, tagged with
  `source` in the grade vocabulary (measured / computed / model). `source` is required. A
  classical result from code, such as the 100x focus sweep, is "computed"; a DINO head or Claude
  is "model". Any other word is shown as "Unsure" and marked invalid, and an unknown source shows
  as "model". A model never gives a Z (PLAN 6, rule 3).
- `EncoderZ`: Z from the ZDrive encoder read-back, in µm. The only way a screen shows Z.

## Talking to the server

`src/app/client.tsx` holds the one client the app shares. Screens use hooks and never open
their own sockets:

| Hook | What |
|---|---|
| `useClient().get(path)` | `GET` JSON from the server |
| `useClient().command(cmd)` | engine commands: `POST /api/commands` (types from `src/api/schema.ts`), returns the `op_id` |
| `useClient().post(path, body?)` | an area's own routes (console submit, map writes, sessions, sample "Open folder", auth). Returns the JSON reply, `null` for 204. Same 403 / 401 / 423 handling as `command` |
| `useClient().postStream(path, body?)` | a POST whose reply streams (NDJSON, e.g. the prompt box). Same 401 / 423 / 403 rules as `post`, applied before the body is read; returns the raw `Response` with its body unread |
| `useEngineEvents(handler, kinds?)` | engine events from the shared `/ws/events` socket. Pass a stable `handler` (`useCallback`) |
| `useEventsConnected()` | whether that socket is open. Re-read your state when it turns true again: events in a gap are lost |
| `useClient().events.onLock(fn)` | `{"type": "lock", "locked"}` messages on the same socket (T-009c). No events arrive while locked; the login gate re-reads `/me`, and `useEngineStatus` re-reads `/api/state` when `useAuth().resumed` changes after an unlock |
| `useReadOnly()` | `{readOnly, why}`. Disable command buttons when true |

Read-only starts on when the page was opened from another PC (a non-loopback host), and turns on
for good if the server answers a command with 403 (remote view, D13). The server decides; the flag
only keeps people from pressing buttons that will be refused.

The status bar (`src/app/StatusBar.tsx`) shows the server connection, the read-only badge, the
lights, XY and the encoder Z, the running operation and the assistant's provider and data stage
(PLAN D7; "assistant: unavailable" until `GET /api/assistant/status` answers). The first screen
shows the last shutdown's light readback from `GET /api/state` when the engine reports one.

While the event socket is down, the lights and XY/Z are never shown as current: the bar says
"unknown" and gives the last known values with their time. `GET /api/state` restores them on
reconnect.

## Login

The login screen is T-105's (`src/app/login/`, not an area, no route). The shell reaches it only
through `src/app/auth.tsx`, which uses `LoginGate`, `useAuth` and `ApprovalList` from
`./login/index.ts` when that file is in the build, and pass-through stand-ins until then:

- `App` wraps everything in `<LoginGate abort={<AbortButton />}>`. Abort needs no login and no
  control, so it stays on screen while logged out or locked.
- Any 401 or 423 from the client (`client.onAuthFailure`) calls `useAuth().refresh()`, which
  shows the login or lock screen again.
- The status bar shows the user and role, the control holder (`GET /api/auth/control`) with
  Take / Release for a local operator or admin, and a menu: Log out, Lock, and Approve accounts
  (admins, `ApprovalList`). `me.local === false` turns the app read-only.
- `useActivity` posts `/api/auth/activity` on input, at most every 30 s, while logged in.

## Live view

`src/features/live/` (shell-owned) shows `/ws/frames`: one `WsFrame` text message, then the JPEG.
It shows the frame time, the receive rate, the binning and the display range. Z appears only when
the frame metadata has the encoder read-back. A 501 ("this engine provides no frames") is shown
and not retried. Raw frames stay on disk.

Tests use `src/test/fakes.ts` (`fakeTransport`, `FakeSocket`): no network, no browser.

UI text is English.
