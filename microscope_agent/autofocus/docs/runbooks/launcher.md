# Desktop launcher ("DINO Autofocus.exe")

The exe starts the web app server from this clone's uv env and opens the browser. It needs
no system Python: it finds `uv` and runs `uv run python -m dino_autofocus.server`.
Source: `tools/launcher/Launcher.cs`, built by `tools/launcher/build.ps1`.

## Build

Needs `uv` and the .NET Framework 4 compiler that ships with Windows (no SDK).

```
powershell -ExecutionPolicy Bypass -File tools\launcher\build.ps1
```

| Option | Default | Meaning |
|---|---|---|
| `-Port N` | `8765` | port the server is started on and probed at |
| `-Out path` | `Desktop\DINO Autofocus.exe` | where the exe is written (a missing folder is created) |
| `-Force` | off | replace an existing exe at `-Out`. Without it the build stops and prints the old file's size and date: check that it is not a build you want to keep first. With it the old exe is first copied to `<name>.prev.exe` next to it (`<name>.prev.<stamp>.exe` if a `.prev.exe` is already there; nothing is overwritten) and the path is printed |

- The repo path compiled into the exe is the clone `build.ps1` runs from. Build from the
  clone you use day to day, not from a session worktree. Moving the clone means rebuilding.
- `autofocus.ico` is in git. If it is missing, `build.ps1` redraws it with
  `uv run python tools\launcher\make_icon.py`.
- Server code changes need no rebuild; only `Launcher.cs`, the port, or the clone path do.

## Run

| Action | Result |
|---|---|
| Click | Server already answering `GET /api/health` → opens `http://127.0.0.1:<port>/`. Otherwise starts the server hidden, shows "Starting the server…" until `/api/health` answers (up to 60 s), then opens the browser. |
| Click while a start is in progress | Waits for that server; never starts a second one. |
| Ctrl + click (or `--stop`) | Stops the server after a confirmation: graceful first, forced only if it does not exit (see Stop). |

- The server binds `127.0.0.1` only. The exe never turns on remote view.
- Server output goes to `%LOCALAPPDATA%\dino-autofocus\server.log` (the previous run is kept as
  `server.prev.log`), away from the sample records. `server.pid` there names the process the
  launcher started.
- The first start after `git pull` can be slow: `uv run` syncs the env first (torch is large).
  If the 60 s wait runs out, the server keeps starting; click again to keep waiting.
- The old launcher run this way starts its hardware jobs with the repo `.venv` Python, not the
  system Python described in `docs/setup-new-pc.md`. Check that on the microscope PC before
  relying on it.

## Remote view (read-only)

Not available from the exe. Start the server by hand from the clone:

```
uv run python -m dino_autofocus.server --port 8765 --remote-view
```

or set `DINO_AF_REMOTE_VIEW=1`. The server then binds `0.0.0.0`; other PCs can read state and
watch events, and commands are still accepted only from this PC (T-009). Allow the port in
Windows Firewall only for the network you need.

Remote view is not in use for now (user decision 2026-10-02: no remote access or remote
sign-up; VPN or TLS is to be decided if it is opened later). Over plain HTTP, passwords and the
session cookie cross the LAN in clear text.

## Never forward or proxy the port

The server treats requests from loopback as the microscope PC itself: stops and shutdown
without a login, first-run admin setup, commands. A port forwarder or reverse proxy on this PC
(`ssh -L` / `-R`, ngrok, cloudflared, Tailscale serve, RDP or VS Code port forwarding, a local
nginx) makes remote traffic arrive from `127.0.0.1` with those rights. Do not run any of them
for the server port. Requests that carry a forwarding header (`X-Forwarded-For`, `Forwarded`,
`Via`, ...) are refused with 403 `proxied` (`server/edge.py`), but a plain TCP forwarder adds
none, so the header check is not a substitute for this rule. The Vite dev proxy
(`npm run dev`) adds no such header and is fine.

## Stop

Ctrl + click the exe, or run `"DINO Autofocus.exe" --stop`:

1. `POST /api/shutdown` (T-009, accepted from this PC without a login). The engine switches the
   lights off with readback, aborts what runs, finishes its records, and the server exits.
2. The launcher waits up to 10 s for `/api/health` to stop answering and the process to exit.
3. Only if it is still running is the process tree it started (`cmd.exe` → `uv.exe` →
   `python.exe`) killed with `taskkill /T /F`. The message then says the stop was forced:
   check the lights on the microscope.

| Case | Result |
|---|---|
| Server answers and exits | Graceful. "The server stopped: lights off and records finished by the engine." |
| Server answers (or refuses) but does not exit within 10 s | Forced kill of the tree the launcher started, said in the message and in `launcher.log` |
| No server running (it died, or was never started) | "No DINO Autofocus server is running."; a stale `server.pid` is removed |
| Server started by hand, not by this launcher | Graceful request only. If it does not exit, the launcher never kills it: stop it with Ctrl+C in its terminal |

Every stop and how it ended is one line in `%LOCALAPPDATA%\dino-autofocus\launcher.log`
(next to `server.log`), for example `stop: no exit within 10 s of the shutdown request; FORCED
KILL (taskkill /T /F) done`.

## Testing without a desktop

Set `DINO_AF_LAUNCHER_HEADLESS=<file>` before starting the exe. No window or browser opens;
each message, confirmation (answered OK), wait, browser open and stop log line is appended to
`<file>`, and `server.log` / `server.pid` / `launcher.log` go next to it. Build a test copy with `-Out` so the Desktop exe is
untouched, and stop any server the test started (`--stop` with the same variable set).

## Troubleshooting

| Message | Cause and fix |
|---|---|
| `uv not found` | uv is not on `PATH`, `%USERPROFILE%\.local\bin`, `%USERPROFILE%\.cargo\bin`, the winget links folder, or scoop shims. Install uv, run `uv sync` in the clone. |
| `Repository not found` | The clone moved or was deleted. Rebuild from the clone you use. |
| `Server not found in this clone` | `src\dino_autofocus\server\__main__.py` is missing: the clone predates the web server (T-009). `git pull`, `uv sync`. Shift + click still opens the old launcher. |
| `Port N is in use, but no DINO Autofocus server answers there` | Another program holds the port. Find it with `netstat -ano \| findstr :N`, close it, or rebuild with `-Port`. |
| `The server stopped while starting` | The server exited. The message shows the end of `server.log`; the full log has the traceback. Run the same command in a terminal to see it live: `uv run python -m dino_autofocus.server --port 8765`. |
| `The server did not answer … within 60 s` | Usually a slow first `uv run` after a pull. Click again to keep waiting, or Ctrl + click to stop it, then check `server.log`. |
| Nothing happens for a few seconds after clicking | Antivirus scans a freshly built, unsigned exe on its first runs. |
| `The server did not exit within 10 s, so it was killed (forced)` | The engine did not finish its stop in time. Check the lights on the microscope, then `launcher.log` and `server.log`. |
| `The server did not stop within 10 s. This launcher did not start it` | A server started by hand ignored the stop request. Stop it with Ctrl+C where it runs. |
