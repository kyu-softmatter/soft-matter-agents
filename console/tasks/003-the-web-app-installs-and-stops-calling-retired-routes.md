# 003 — the web app is installed from its lock, and stops calling the retired routes

Written by `manager-console-office-20261017-1`. You read this; you do not edit it.

**Assigned to `console-office-20261017-1` (Console 1)**, from 2026-10-18. If
you are not that seat, take nothing from this card and report up.

**Send questions for the person to the intake seat,
`architecture-office-20261017-2`, not to your own window.**

## Why

The cut at `0cd095c` retired these routes:
- `/api/commands`;
- `/api/{hardware,map,objective,patterns,sample,sessions}`;
- the command messages on `/ws/events`.

The web app still calls them, and `web/src/api/schema.ts`, generated before
the cut and before the rename, still describes them. Regenerating it and
running the web tests needs the web packages, which were never installed.

**The person allowed the download, and only this download.** Committed at
`48d7a66f`, `docs/ideas/20261018.md`, Q-20261018-02, said in the intake
seat's window: "콘솔 웹 패키지 158개를 잠금 파일대로 npm에서 내려받아
설치하는 것을 허락해." ("I permit downloading and installing the console's
158 web packages from npm, exactly as the lock file lists them.") The scope,
as asked and answered:
- the packages `console/web/package-lock.json` lists, and nothing else;
- from the public npm registry;
- into `console/web/node_modules`, which is never committed.

Anything beyond that -- a package the lock does not list, a rewritten
lock, a global install, a download from anywhere else -- is outside those
words. It goes back to the person through the intake seat first.

## What to do

1. **Node comes from the uv cache, not from a download.** `nodejs-wheel`
   22.20.0 is already in this computer's uv cache, so from `console/` run
   `uv sync --offline --group web`. If it will not resolve offline, stop and
   report. A Python-side download is not what the person allowed.
2. **Install exactly the lock**, from `console/web/`, with
   `npm ci --no-audit --no-fund --ignore-scripts`.
   - `ci` installs the lock and never rewrites it; `install` may rewrite it.
   - `--no-audit` keeps the lock's contents from being sent anywhere.
   - `--ignore-scripts` runs no package's install code.
   - Afterwards `git diff --exit-code -- console/web/package.json
     console/web/package-lock.json` must be empty.
   - If something fails because a script did not run, stop and report what
     failed. Do not drop the flag yourself.
   - **Measure `node_modules`**: total bytes and the file count. Send both to
     me and to the intake seat, which records them for the person.
3. **Regenerate the schema**: `npm run gen:api`, with `UV_OFFLINE=1` set
   so its `uv run` fetches nothing. `schema.ts` is generated, so it is
   committed as generated and never edited by hand.
4. **Every area that calls a retired route says so instead.** The
   typecheck after step 3 names the call sites. Expect at least hardware,
   map, objective, patterns, sample and sessions, and look at tweezers too:
   trap moves went through `/api/commands`.
   - **Required:** each such area renders, in place of what it did, a plain
     notice. It says what the area was for. It says it is not connected
     here, because the console sends no command to the instrument. And it
     says what replaces it: a plan drafted for the person to approve, or a
     request to a running plan.
   - **Required:** no request goes to a retired route.
   - **Required:** nothing new commands anything.
   - **Your call:** whether the area keeps its place in the navigation.
     Remove nothing the area shows that needs no retired route.
   - Tests asserting the old behaviour are replaced by tests asserting the
     notice and that no retired route is requested.
5. **`docs/screens/`**: the retired areas' documents say they were retired
   at `0cd095c`, and what replaces them. The package name and the
   default-root rule follow card 002. No other rewriting.
6. **One name fix in the server**: `server/app.py`'s
   `version("dino-autofocus")` becomes `version("sma-console")`, the
   distribution the console's environment actually has, so the app stops
   reporting `0+unknown`. The names the app shows itself under stay as
   they are; renaming those is a separate question.
7. **Run everything and report the counts**:
   - `npm run typecheck`;
   - `npm test`;
   - `npm run build`. `dist/` is ignored and is not committed;
   - the Python tests in the console's own environment;
   - the validator, which must show 0 failed.
8. **Commit through `contracts/tools/seat_commit.py`**, paths under
   `console/` only. The message carries:
   - the measured `node_modules` size;
   - the areas changed and the routes they no longer call;
   - every count above.

   Send me the hash.

## What you must not do

- Run `npm install`, `npm update` or any global install.
- Let the lock be rewritten.
- Fetch from anywhere but the npm registry for the lock's packages.
- Commit `node_modules/` or `dist/`.
- Start the server with anything but `--backend placeholder`, or point it at
  a live host. `--dump-openapi` starts nothing.
- Add a route, a command, or a button that commands.
- Write outside `console/`, or edit `console/CLAUDE.md`, `console/README.md`,
  `console/tasks/` or `console/.claude/`.
