# 009 — login and accounts, with plain login ids

Written by `manager-console-office-20261017-1`. You read this; you do not edit it.

**Assigned to `console-office-20261017-1` (Console 1)**, from 2026-10-24, after
card 008 landed at `313a152a`. If you are not that seat, take nothing from
this card and report up.

**Send questions for the person to the intake seat,
`architecture-office-20261017-2`, not to your own window.**

## Why

Card 007's second app card. Today an account is keyed by its email. A
console-signed approval carries the login as a plain id, and an email is
refused there: `plan_approval.schema.json`'s `signed_through.login`, pattern
`^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`, landed at `e2f5b08b`. A committed
approval is published, and an email in it would publish the person's
address. The runtime compares that login byte for byte with
`microscope_runtime/envelope/console_login.json`, which uses the same
pattern. The person named the administrator's login `softmatter`
(I-20261022-office-04). The canvas screens are `PLogin` and the Accounts tab
of `PAdmin`, version 58.

## What to do

1. **A login is a plain id, never an email**, in the pattern above.
   - Accounts are keyed by it.
   - Registration takes a name, a login and a password.
   - Logging in takes a login and a password.
   - The audit log's `user_id` becomes the login. Old lines stay as written:
     the log is append-only.
   - The account routes take a login in place of an email.
2. **The first administrator's login.** It comes from `admin_login` in the
   console's settings file outside the tree, and defaults to `softmatter`
   when that key is absent. `admin_email` is no longer read.
   - The first-start screen creates that account, with the password typed
     there by the person.
   - Under the password field, in these words: "Choose one you have never
     written anywhere else, a chat window included. The console cannot tell
     if a password has been seen."
   - No credential ships with the console, in code, tests or docs.
3. **An existing `accounts.json` keyed by email** is not guessed into ids.
   - Each such account loads as "needs a login id". It cannot log in, and
     nothing is deleted.
   - The administrator gives it a plain login from the Admin screen. That
     writes an audit line naming both.
   - If the only administrator is email-keyed, the first-start screen
     appears as for a fresh install, and the old record stays in the file.
4. **Accounts are switched off, never deleted.** Remove the delete route and
   its method, `POST /accounts/{id}/delete` and `Accounts.delete`, and any
   button that calls them. Switching off and on stays. The docstring of
   `accounts.py` already says accounts are never deleted. Make the code
   agree.
5. **The take-and-release control** (`auth/control.py`, `/control/acquire`,
   `/release`, `/revoke`) held dino's device control, which card 077
   retired. Card 008 took it out of the shell. Remove the routes and the
   module if nothing outside tests calls them. If the stop or anything else
   does, keep them and report what.
6. **Two things back in the footer**, from your report on 008:
   - when the server says this browser is not on the microscope computer, a
     chip "viewing from another computer · read only";
   - a Lock button beside Log out.
7. **The login screen**, as `PLogin` draws it: login and password; "Create
   an account", whose result says the administrator approves it and sets
   what it may do; the first-start state. STOP stays reachable on the lock
   and login screens, as card 004 made it.
8. **Tests, each watched failing first:**
   - an email is refused as a login at registration, login and first start;
   - `admin_login` defaults to `softmatter`, and a settings value overrides
     it;
   - an email-keyed account loads as "needs a login id", cannot log in, and
     is not lost;
   - there is no delete route;
   - no password appears in any response or in the audit log;
   - the remote chip and the Lock button render.

## What not to do

- No change to roles or what each may do. The console-side permissions are
  the admin card's.
- No retheme yet. The switch to the canvas's dark look comes with the
  Simulation and Results card (007's seventh), once no screen hard-codes
  light colours. Keep "Stop all runs" as the button's words.
- Install nothing. Write nothing outside `console/`.

## Done when

- `npm run typecheck`, `npm test` and `npm run build` pass from `web/`.
- `uv run pytest` passes.
- The validator ends `0 failed`.
- One commit through `contracts/tools/seat_commit.py`. Report the hash to
  this seat.
