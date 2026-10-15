# `hardware` screen contract (T-101 stage A)

Area `hardware` (PLAN.md 2절 F2, 9절 WP-G). This file gives the endpoints, commands and events the
screen uses, and the engine piece behind each panel. Layout and wording: `docs/ui-spec.md` 7.0, 7.2 and
5.2 (branch `exec5/T-004-ui-spec` 6fcd8a8). `hardware_scan` steps and profile fields:
`docs/operations-spec.md` 5절. Neither is restated here.

Names checked against: main b164e97 `engine/events.py`, T-002 stage 2 `engine/gates.py`
(`exec1/T-002-stage2-fix`), T-009 `server/app.py` and `server/api/__init__.py`
(`exec7/T-009-server-skeleton`), T-018 `auth/roles.py` (`exec13`).

## 1. Read endpoints (`server/api/hardware.py`, mounted at `/api/hardware`)

All are `GET`, open to remote viewers and every role (`Action.VIEW`). None of them reaches the backend:
they read the last profile and gate verdict that the engine already holds. `/config` reads a file instead (one of a fixed list), never the backend.

| Path | Response model | Body |
|---|---|---|
| `/api/hardware/profile` | `HardwareProfileOut` | `{"profile": <normalised profile> \| null, "path": str \| null, "sha256": str \| null, "previous": {sha256, detected_at, changed: [{key, before, after}]} \| null, "error": str \| null}`. `null` = never scanned; the screen shows `"Not scanned yet"`. `sha256` and `previous` are the engine's (T-028 `ProfileStore`). `error` is set when the engine could not read its hardware state |
| `/api/hardware/gates` | `list[GateRow]` | One row per gate key, off rows first, then by key. `light_set` has one row per mode: `light_set:brightfield`, `light_set:aura`, `light_set:off` |
| `/api/hardware/gates/{op}` | `GateRow` | By gate key. 404 `{code: "unknown_gate"}` for an unknown key (plain `light_set` included) |
| `/api/hardware/status` | `StatusResultOut` | Last `finished(status)`: `{"op_id", "t", "user_id", "summary"}` or `null` if `status` has not run since the server started |
| `/api/hardware/config?path=` | `ConfigTreeOut` | The devices a Micro-Manager `.cfg` declares, parsed from the file text (`engine/mm_config_tree.py`, no core): `{path, sha256, source, available: [{path, name, source}], devices: [{label, library, adapter, parent, link, port, roles, state_labels, preinit, line}], startup, warnings, error}`. `available` is a fixed list, best first: the cfg the last scan loaded (`scanned`), the cfg mm-real would load (`server`, `mm_real.config_path()`), the repo's `configs/micromanager/*.cfg` (`repo`). When the scanned path is not on this machine, a listed file with the scan's `config.sha256` comes first as `scanned-copy`. `path` must be one of them (else 404 `unknown_config`); without it the first is read. `link`: `parent` (a `Parent` line), `port` (pre-init `Port` naming a loaded SerialManager device), `inferred` (no line; the adapter library's only `*Hub` device) |
| `/api/hardware/config/match` | `ConfigMatchOut` | Every listed cfg against the last scan's loaded devices (Core left out), best first: `{detected_at, rows: [{path, name, source, score, exact, matched, differs, missing, extra}], error}`. `score` = matched / labels in either; `differs` = same label, other library or adapter name. `error` before the first scan |
| `/api/hardware/config/draft?base=&no_base=` | `ConfigDraftOut` | A new cfg drafted from the last scan (`engine/mm_config_from_scan.py`): Device, pre-init Property, Parent, Core role and Label lines; no post-init settings, groups or Startup preset. Details the scan did not report come from `base` (a listed path), the best match without it, or nowhere with `no_base=true`. Hub peripherals reported installed but not loaded are commented out. `load_check` is mm-real's load check with the bench device names (null = it would load). 409 `not_scanned` before a scan |
| `POST /api/hardware/config/draft` | `ConfigSavedOut` | Body `{name, base, no_base}`. Writes the same draft to `<settings folder>/micromanager/<name>.cfg` (then listed as `saved`). Local operator only (`server_action_why`, 403 `role` / `remote_view` / `foreign_origin`), 422 `bad_name`, 409 `exists` (never overwrites). The active config (`mm_config` setting) does not change |

Source: `snapshot()["hardware"]`, which is T-028 `operations/hardware_scan.HardwareState` (55d88c2):
`{profile, profile_path, sha256, previous, gates, objective_options}`, plus the runner's `last_status` and
`error`. `objective_options` is for the objective screen (T-104) and is not served here.

The router reshapes `asdict(engine.gates.HardwareProfile)` into the shape the screen draws. That shape is
in `web/src/features/hardware/api.ts` (temporary until gen:api), and the router's pydantic models match it:
- `backend_kind`, `host`, `bench`, `objective`, `config`, `notes` and `errors` are copied.
- `devices` is the profile's `device_list` (properties left out), followed by every role in `devices` that
  no loaded device fills. A missing role shows as a problem row.
- `objectives` is `objective_rows` (falling back to the label list).
- `human_confirmed` is `confirmed` (`{value, by, at}`).
Fields the engine does not report stay null, and the screen shows `"not reported"`.

`GateRow` = `{op, enabled, reasons: list[str], requires: {devices, objectives, confirmed, checks, arg}}`,
copied from T-028 `gates.gate_rows`. `op` is the gate key, and anything but `enabled: true` is off. The router
never evaluates a gate itself (F2.2, PLAN 6절 2항). The screen takes the permission per op (`light_set`) and
the gate per key (`light_set:brightfield` for "Brightfield on", `light_set:aura` for the Aura button).

Light state has no endpoint of its own. It comes from `/api/state` when the screen connects and from
`light_changed` after that (ui-spec 5.2).

## 2. Commands (T-009 `POST /api/commands`, body = engine `Command`)

| Button (ui-spec 7.2) | Body | Who may send it |
|---|---|---|
| `"Scan hardware"` | `{"kind": "start", "op": "hardware_scan", "args": {"include_properties": true, "piezo_port": ""}}` (`""` skips the piezo; G10) | Local operator with control. No experiment session needed (nothing moves, nothing turns on) |
| Save human-confirmed items | `{"kind": "start", "op": "hardware_confirm", "args": {"items": {"<item>": "<value>"}}}` | Same as scan. The engine stamps `by` (user id) and `at` |
| `"Show objective / Z / PFS"` | `{"kind": "start", "op": "status"}` | Local operator with control. No session (read only) |
| `"Brightfield on"` | `{"kind": "start", "op": "light_set", "args": {"mode": "brightfield"}}` | Local operator, control **and** an open experiment session (D15, like motion) |
| `"Aura <line> <pct> % on"` | `{"kind": "start", "op": "light_set", "args": {"mode": "aura", "line": "GREEN", "percent": 1.0}}` | Same as brightfield |
| `"Lights off"` (on this screen; the status-bar button belongs to T-010) | `{"kind": "lights_off"}` | Anyone logged in **on the microscope PC**, including a viewer, a user without control, and a locked session (`Action.STOP`). Refused from a remote client, which may send `abort` only (D2, director-confirmed, under D13). It pre-empts the running operation |

`lights_off` is a command **kind** in `engine/events.py` (`COMMAND_KINDS`). It is not sent as
`start("lights_off")` as ui-spec 4.0 and 4.2 write it (gap G1).

Why a button is off comes from the shared `GET /api/permissions?ops=hardware_scan,hardware_confirm,status,light_set,lights_off`
endpoint, which returns `{op: {allowed, reason}}` (T-009b, backed by T-011 `check()`). That endpoint covers remote,
role, control, session and the running operation. If the permission allows the op, the screen adds this area's
own gate reason from `/api/hardware/gates`. The screen re-reads permissions after every `started`, `finished`,
`aborted`, `error`, `preflight_failed` and `refused` event, and after every reconnect.

Reason texts, in order (shared by every screen):
1. The shell's read-only flag (`useReadOnly()`, remote view) gives `"Read-only: remote view"` on every control,
   `"Lights off"` included (D2). It comes from the shell, not from `/api/permissions`.
2. While the first answer is loading: `"Checking permissions…"`.
3. If the endpoint cannot be read, or an op is missing from its answer: `"Permission check unavailable"`. The
   exception on an unreadable endpoint is this screen's `"Lights off"`: it stays on, like the shell's Abort and
   Lights off.
4. Otherwise, the permission's `reason`, then the gate reason.

The screen talks to the server only through the shell's client (`src/app/client.tsx`: `useClient`,
`useEngineEvents`, `useReadOnly`) and reads positions, lights and running ops with `useEngineStatus()`. It opens
no socket of its own. The lights panel follows the light read-back only (`/api/state` and `light_changed`): the
end of an operation does not mean the lights are off, because a `light_set` survives the next op (T-011). A refusal that reaches a click anyway (a 403 `detail`, or a
`preflight_failed` / `error` event) is shown next to the button. Neither the router nor the screen works out
role, control, session or remote rules itself.

## 3. Events read (`/ws/events`)

| Event | Used for |
|---|---|
| `position` | "Current state" panel: Z (plus XY on the common status bar) |
| `light_changed` | Lights panel: readback, not the requested value (ui-spec 5.2). `verified=false` or `"unknown"` shows the warning colour and the readback text |
| `finished` with `op == "status"` | "Current state" panel: objective, Z, PFS (`enabled`, `locked`, `in_range`) from `summary` |
| `finished` / `preflight_failed` / `error` with `op == "hardware_scan"` or `"hardware_confirm"` | Refetch `/profile` and `/gates`. Show the failure text |
| `started` / `finished` / `aborted` | Disable scan while any operation runs (single owner). `lights_off` stays enabled |

## 4. Panels and the engine piece behind them (ui-spec 7.2)

| Panel | Fields | Engine source | State on main now |
|---|---|---|---|
| Detection summary | `detected_at`, `backend_kind`, `bench`, `host`, `config.{path, sha256, changed_during_load, startup_preset_applied}`, profile sha256, `previous.changed` keys | `hardware_scan` writes `hardware_profile.json` (ops-spec 5) | T-028 (in review) has all of these |
| Devices | per device: `label`, `type`, `library`, `present`, `read_back`, `write_verified`, `note`; problem rows first | Backend `describe_devices()` (T-015) via `hardware_scan` | Skeleton `DeviceStatus{present, readable, label, note}` keyed by role (G3) |
| Objectives | `state`, `label`, `magnification`, `na`, `immersion`, `working_distance_um` (`"not set"` if missing), `pixel_um` | `nosepiece_labels()` (T-015) + lens table | Skeleton: list of labels only. Lens table owner open (Q8, G4) |
| Camera / piezo | `camera.{name, sensor, roi, bit_depth, ceiling_adu, pixel_type}`, `piezo.{port, connected, x_um, y_um, z_um, error}` | `info()`, `piezo_read()` (T-015) | Skeleton: `camera_bit_depth` only (G3) |
| Human-confirmed items | per item: `value`, `by`, `at`; editable form for the local operator, read only otherwise | `hardware_confirm` | Skeleton `confirmed: {item: "who/when"}` has no value field (G5) |
| Gates | `GateRow` (section 1) | `gates.GATES` + `gates.evaluate(profile)` | Skeleton has 3 example gates. WP-G writes the real list (ops-spec 5 gate table) |
| Current state (Step 0) | objective label, Z, PFS triple | `status` op + `position` | `status` op not yet written (WP-C) |
| Lights | the one light shape (server/schemas/state.py `Lights`): DiaLamp `{state, intensity}`, Aura `{state, lines: {LINE: percent}}`, `verified`, `records`, `error`, last readback time | `light_set`, `lights_off`, `light_changed` | Backend has `lamp_on/off`, `aura_line_on/off`, `all_off`; `light_set` op does not exist (G2) |

## 5. Gaps (requests to AF 업무분배보조, to forward to the manager)

Where each gap went (manager, main 176b4c3):

| Gap | Outcome |
|---|---|
| G1 | Confirmed: `lights_off` and `abort` are command kinds. ui-spec is corrected by its author |
| G2, G3, G4, G5 | Go to future WP-G / WP-C cards (`light_set` op, profile fields, lens table, confirmed values). Stage B shows `"not reported"` for missing fields |
| G6 | T-011 and T-028: `snapshot()["hardware"] = {profile, profile_path, sha256, previous, gates, objective_options, last_status}` |
| G7 | T-011: one table op → (action class, needs control token, needs open session), read by T-009 |
| G8 | D2, confirmed by the director (final): a remote client may send `abort` only, and remote `lights_off` is refused. Locally, anyone logged in may send `abort` and `lights_off` |
| G9 | T-028 `ProfileStore.previous`: the panel lists `previous.changed` keys, or `"no previous profile"` |
| G10 | Form and tests default to `piezo_port: ""`. Tests never touch COM ports |

- **G1** `lights_off` is a command kind in `events.py`; ui-spec 4.0/4.2 send it as `start("lights_off")`.
  This contract follows `events.py`. ui-spec should be corrected to match.
- **G2** No `light_set` operation. Proposed args: `mode` (`"brightfield"` / `"aura"` / `"off"`), `line`, `percent`.
  The op calls the backend's semantic light methods and emits `light_changed` with readback `records`. Owner?
  WP-C (port) or WP-G. Under D15 it needs the operator, control and an open session.
- **G3** `HardwareProfile` (T-002-2) carries only part of the ops-spec 5 profile. Missing: `host`, `config{}`, device
  `type`/`library`/`properties`/`write_verified`, objective rows, `camera{}`, `piezo{}`, `positions`, `pfs`,
  `lights`. Stage B shows what exists and `"not reported"` for the rest. WP-G should extend the dataclass.
- **G4** Objective NA and magnification are not in the ops-spec profile fields. They need the lens table
  (registry key, working distance, immersion; ops-spec Q8). Who owns the lens table, and where does it live?
- **G5** `confirmed` maps item → `"who/when"` and has no value. The UI needs `{value, by, at}`, for example
  DiaLamp 608/2100. Proposed `hardware_confirm` args: `{"items": {name: value}}`. The engine adds `by` and `at`.
- **G6** `EngineAPI` exposes only `submit`/`subscribe`/`snapshot`. The router needs the latest profile and gate
  verdict, and the last `status` summary. Proposal: `snapshot()` carries
  `hardware: {profile, profile_path, gates, last_status}`. The alternative is a read method on the
  engine. Either way, the location of the latest profile is still open (ops-spec 5 leaves it to T-002/WP-G).
- **G7** Per-operation permission table. T-009 `/api/commands` checks only loopback today. This screen needs:
  `hardware_scan`, `hardware_confirm`, `status` → `Action.OPERATE` + control, no session;
  `light_set` → `Action.OPERATE` + control + open session (D15); `lights_off` → `Action.STOP`.
  Who maps op → (action, control, session): T-011 runner or a T-009 follow-up? Stage B tests depend on
  it.
- **G8** ui-spec 5.2 and 7.0 disable `"Lights off"` for viewers. PLAN 5절, T-018 `Action.STOP` and D15 allow
  every user to send it. This contract follows PLAN. For a remote client, `lights_off` follows the same
  setting as remote `abort` (checklist U3, default allowed). But T-009 currently refuses every remote
  POST, so remote `lights_off` and `abort` need a T-009 exception.
- **G9** "Diff against the previous profile" needs profile history. Proposal: keep each
  `hardware_scan_<stamp>/summary.json` (ops-spec 5) and have the engine report the previous profile's
  sha256 and changed keys. Until then the panel shows `"no previous profile"`.
- **G10** ops-spec 5 defaults `piezo_port` to `COM4`, and whether opening the port alone changes the
  controller is still unconfirmed (Q19). Answer (업무분배보조): the scan form and the tests default to
  `piezo_port: ""` (skip the piezo), and tests never touch COM ports.
## 6. Stage B plan (after T-009 and T-010 skeletons merge)

- `hardware.py`: the four `GET` routes above with pydantic models, using a fake engine whose snapshot has
  the G6 shape. No command routes.
- `web/src/features/hardware/index.tsx`, registered per the T-010 rule. Common types come from `web/src/api/`.
  The router and permission types sit in `api.ts` until gen:api covers them.
  UI text in English. The screen is a default export with no props (T-010 a5fb986 `web/README.md`). It does
  not edit `src/app/` and does not import from other areas. Z is drawn with the shell's `EncoderZ`.
- Screen context (ui-spec 7.2): `useScreenContext({device, gate, gate_reasons})` holds the selected
  device label, the selected gate `op` and that gate's reasons. Short text only (D7).
- Tests: section 1 routes, unknown gate 404, remote GET allowed, and remote/viewer refusals as T-009 and
  G7 define them (pytest `TestClient`). vitest covers: off gates show their reasons, problem devices sort
  first, the confirm form is read only for remote/viewer, and the lights panel shows readback. No browser
  or desktop windows; any server started in a test is stopped.

## "Configured hardware" panel (2026-10-02)

Below the Scan row. The `.cfg` from `/api/hardware/config` drawn as a hub tree: hubs (`Ti2-E__0`,
`NIDAQHub`, the serial port `COM10` → `CSUW1-Hub` → CSU-W1 parts) fold open with ▸/▾; a hub with a
problem below it starts open. Each device's state is the last scan's device list joined by label:
`Connected` (read back), `Loaded, no read-back`, `Loaded, read failed`, `Not loaded` (in the cfg, not in
the scan), `Not checked` (never scanned). Clicking a label shows adapter, dependency and how it was
found, port, Core role, state labels, pre-init settings and the cfg line. "Check connections" sends the
same read-only `hardware_scan` as "Scan hardware" (its block reason is a tooltip; the text is on the Scan
row). When the scan's `config.sha256` differs from the file shown, the panel says so. Devices the scan
loaded that the cfg lacks are listed under the tree. The types are the generated `ConfigTreeOut` & co.
(`src/api/schema.ts`, aliased in `api.ts`).

## "Find or make a config" panel (2026-10-02)

Under "Configured hardware". "Find matching config" shows `/config/match` (verdict, then a table with
Show buttons that pick the cfg in the tree). "Draft config from scan" shows `/config/draft`: base selector
(best match / any listed cfg / none: from the scan only), notes (base items used, load check, unknown
adapters, hub-reported peripherals), the text, a file name, "Save as new file" and "Download".

Since 2026-10-02 the scan also records per device (`DeviceRow`): `adapter` (Micro-Manager device name),
`parent` (hub label), `preinit` (pre-init property values) and, for hubs, `installed` (the hub's own
`getInstalledDevices`). Reads only (`backend.read_wiring`). The hub query asks the hub's adapter and may reach
the hardware, so it is off on mm-real (`mm_real.READ_HUB_PERIPHERALS = False`, user 2026-10-02) until checked on
the microscope PC (`USER_CHECKS`); mm-demo keeps it.
Profiles written earlier lack them, which is why a draft takes adapters from a base cfg. Checked on the
Micro-Manager demo core: a scan-only draft loads back in a fresh core with the same 13 devices and roles.

