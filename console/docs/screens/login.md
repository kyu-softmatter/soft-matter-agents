# Login screen and auth API: contract (T-105 stage A)

> **Changed at console card 009: a login is a plain id, never an email.** An account is keyed by a
> login (`^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`, the pattern of `signed_through.login` in
> `plan_approval.schema.json`), stored exactly as typed, with no two logins that differ only by case.
> Sign-up, login and the first start refuse an email in words. The first administrator's login is
> `admin_login` in the settings file (default `softmatter`) and its password is typed at the first
> start; no credential ships. An account an older console kept under an email loads as "needs a login
> id", cannot log in, and is given a plain login by the administrator (the audit line names both).
> Accounts are switched off, never deleted: there is no delete route. dino's take-and-release control
> of the device is gone with the engine it controlled: there are no `/control` routes and no
> `has_control`. Where the tables below still say email, delete or control, read this note first.

Design: PLAN.md §5 "Users and login", §7 D9, D12, D13, D16, design rule 12. Core logic:
`src/sma_console/auth/` (T-018). This file fixes the HTTP surface and the screen so that
stage B (`server/api/auth.py`, `web/src/app/login/`) and the shell (T-010) can be built against it.

## 1. Endpoints

All under `/api/auth` (T-009 mounts `server/api/auth.py` there). JSON in and out. Errors are
T-009b refusals: `{"detail": {code, message}}` plus the `X-DinoAF-Refusal: <code>` header. "Local" means the request comes from the microscope PC
(T-009's loopback check); "remote" means any other PC under remote view.

| Method, path | Who | From | Body → reply |
|---|---|---|---|
| `GET /setup` | anyone | any | → `{state: "needs_admin" \| "ready", admin_login}`. `admin_login` is the login the first administrator will have (a name, not a secret); null once ready, or when the settings name one that is not a plain id |
| `POST /setup/admin` | anyone, only while state ≠ ready | local | `{password, name?}` → `Me` + cookie. The login is the settings', never the caller's (a `login` or `email` field → 422); a blank name is the login. A settings value that is not a plain id → `409 setup_required` |
| `POST /signup` | anyone | **local** | `{name, login, password}` → `201 {status: "pending"}`. Nothing else is accepted (no role field; extra fields → 422). An email or any non-plain id → `422 invalid`; the administrator's own login → `409 login_reserved`. A login that already has an account gets the same `201` and nothing changes (audit `signup_existing`). From another PC: `403 remote_view` (user decision 2026-10-02; may be opened later) |
| `POST /login` | anyone | any | `{login, password}` → `Me` + cookie; `422 not_a_login` for an email or any non-plain id (no password is looked at); `401` with `detail.code` `bad_credentials` \| `pending_approval` \| `disabled`; `429 too_many_attempts` with `Retry-After` after too many wrong passwords (below) |
| `POST /logout` | logged in | any | → `204`, cookie cleared |
| `POST /lock` | logged in | any | → `204`. "Lock" in the user menu |
| `POST /unlock` | logged in, locked | any | `{password}` → `Me`; `401` on a wrong password; `429 too_many_attempts` with `Retry-After` past the limit |
| `POST /activity` | logged in | any | → `204`. The screen calls it on user input (throttled, at most every 30 s) so the idle lock does not fire while someone is working |
| `GET /me` | logged in | any | → `Me`; `401` without a valid cookie |
| `GET /accounts?status=` | admin | local | → `[Account]` (no hashes); `status` (pending / active / disabled) is optional |
| `POST /accounts/{login}/approve` | admin | local | `{role}` → `Account`. Role is set only here (D12) |
| `POST /accounts/{login}/role` | admin | local | `{role}` → `Account` |
| `POST /accounts/{login}/disable` | admin | local | → `Account`. Switches the account off. Never the last active admin |
| `POST /accounts/{login}/enable` | admin | local | → `Account`. Switched off → active, role kept |
| `POST /accounts/{login}/password` | admin | local | `{password}` → `Account`; every login of that account ends; `422 password_policy` |
| `GET /accounts/needs-login` | admin | local | → `[{email, name, role, status, created_at, approved_by, approved_at}]`: accounts an older console kept under an email. None can log in |
| `POST /accounts/give-login` | admin | local | `{email, login}` → `Account`. The email is in the body, never in a path. Name, role, status, password and history are kept; the audit line `account_login_given` names both. `404 no_account`, `422 invalid`, `409 account_exists` |

```
Me      = {user_id, name, role, locked, local, expires_at}     # user_id is the login
Account = {login, name, role, status, created_at, approved_by, approved_at}
```

`local` in `Me` tells the screen whether write controls can work at all (D16: questions, map
flags and commands are local only). The server decides each request again; hiding a button is
not the check.

## 2. Cookie and session

- Cookie `dinoaf_session`: the T-018 login token. `HttpOnly`, `SameSite=Strict`, `Path=/`, no
  `Max-Age` (dies with the browser) and no `Secure` (plain HTTP on the lab network; revisit if
  remote view ever leaves it). The token never appears in a reply body, a URL or a log.
- Idle lock after 15 min without `/activity`; the session ends 12 h after login (T-018
  defaults, `LoginSessions(idle_lock_s, max_age_s)`).
- There is no device-control token any more: the take-and-release control went with the engine it
  controlled (console card 009). Stopping a run needs no control (card 004).
- Every login, failed login, logout, lock, unlock, sign-up, approval, role change, switch off,
  switch on, password reset and giving of a login goes to `audit.jsonl` through T-018. The router adds
  no second log. No password, and no password hash, is ever in it. Old lines stay as written: the log
  is append-only, so earlier lines may hold an email as `user_id` and may name a control or a delete.

### Attempt limits (`auth/throttle.py`)

Wrong passwords on login and unlock are counted per account (the login as typed, case-folded, whether it
exists or not) and per client address. PROVISIONAL limits: 5 per account and 20 per client in
15 min, then that key is refused for 15 min. While a key is locked the password is not checked
at all (no scrypt cost), and the answer is `429 too_many_attempts` with `Retry-After`. A right
password clears the account's count; pending or disabled with the right password is not a
guess. Audit: `login_failed` with `reason` `lockout_started` / `too_many_attempts`. The check
runs outside the login-sessions lock, so a slow check never stalls other requests. State is in
memory (a restart clears it).

## 3. Requests without a login

- Abort (and lights-off from the microscope PC) **never** needs a login, an unlocked screen or
  device control (rule 12). The auth router puts no dependency on `/api/commands` or
  `/ws/events`, and the dependency it offers to other routers (`CurrentUser`, below) is not used
  on the stop path.
- Every other `/api/*` route and `/ws/*` needs a valid cookie, remote view included. The one
  exception is the group needed to get in: `GET /setup`, `POST /signup`, `POST /login`.

For other routers, `auth.py` exports FastAPI dependencies: `CurrentUser` (401 without login,
423 when locked) and `require(Action)` (403 with the reason from `DeviceControl.authorize`,
given T-009's local flag).

## 4. Screen (`web/src/app/login/`)

One component tree, shown by the shell instead of the areas when `GET /me` is 401 or `locked`.

| State | Shows |
|---|---|
| setup needed (`/setup` ≠ ready) | "First start: the administrator". The administrator's login is shown, fixed (from `GET /setup`); a password (twice); under the password, "Choose one you have never written anywhere else, a chat window included. The console cannot tell if a password has been seen." No password is filled in or shown. Local only; remote shows "Set up on the microscope PC". When the settings name a login that is not a plain id, no form: the page says to fix `admin_login` |
| logged out | Login form (login, password). An email is refused in words and nothing is sent. Link to sign-up |
| sign-up | Name, login ("Letters, digits, dot, dash or underscore. Not an email."), password (twice). After submit: "Account created. The administrator approves it and sets what it may do. Until then it cannot log in." |
| pending (login returned `pending_approval`) | "Your account is waiting for an administrator's approval." No retry loop |
| disabled | "This account is disabled. Ask an administrator." |
| locked | "Locked: enter your password to continue" over a dimmed app. **Running work and guards keep going, and the Abort button stays live on the lock screen.** The status bar stays visible |
| accounts page | Area `#/admin` (`web/src/features/admin/`, formerly `#/accounts`; console card 008), in the sidebar for an administrator only, below a rule, and usable only locally. Every account with a status filter. Pending: role picker (no default) and Approve. Active: role picker and Set role, Switch off, Reset password. Switched off: Switch on, Reset password. There is no delete. The admin's own row has no actions. Below, "Needs a login id" lists accounts an older console kept under an email, each with a field and "Give login" |

UI text in English. No email is asked for, and no password is prefilled, remembered or shown. The footer of the app (card 008) has Lock beside Log out, and a chip "viewing from another computer · read only" when `Me.local` is false.

## 5. What the shell (T-010) and server (T-009) must provide

Requests to the AF work-assignment assistant, who forwards them to the manager:

1. **T-009: login over remote view.** `writes_from_this_pc_only` refuses every non-GET from a
   remote PC, so a remote viewer cannot `POST /api/auth/login`, `/logout`, `/lock`, `/unlock`,
   `/activity` or `/signup`. Proposal: an exempt list for exactly these paths. They never reach
   the engine.
2. **T-009: the local flag as a dependency** (for example `IsLocal`), so `auth.py` and other
   routers use T-009's loopback rule instead of copying it.
3. **T-009: auth on `/ws/*` and `/api/*`.** A cookie check on the WebSocket handshake and on
   routers other than the open group in 3. The stop path stays open.
4. **T-010: a route guard.** Before rendering an area, call `GET /api/auth/me`. On 401 or
   `locked`, render `app/login/` (exported `LoginGate`) instead. Any 401 from another call sends
   the app back to it. Hash routing stays as is; no `#/login` route is needed.
5. **T-010: status bar items** (now the footer, card 008 and 009): user name, a chip when `local` is
   false, a Lock button and a Log out button always in view. The control holder with Take / Release
   is gone.
6. **T-010: an activity hook** that calls `POST /api/auth/activity` on user input, throttled.
