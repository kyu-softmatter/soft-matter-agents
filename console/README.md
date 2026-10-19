# console

The person's window onto the four agents: it shows what they have on disk
and drafts plans for the person to approve, and it commands nothing.
`CLAUDE.md` here is the session's standing orders; `plan.md` 15 and 11-25
are the specification.

## Layout

| path | what |
|---|---|
| `src/sma_console/` | the server (FastAPI), the data layer that reads this repository's files and writes none (`agents/`), the assistant that only proposes, logins and audit (`auth/`) |
| `src/sma_console/agents/mock_data/` | a copied sample of this repository's tree, shown when the console is not connected. Every card in it is a mock, and the validator does not read it as one |
| `web/` | the React app |
| `tests/` | the Python tests |
| `docs/` | the screens and the interface spec |
| `tasks/` | the console's cards, from its manager |

The code came from dino-autofocus (imported at `8f94789`, cut from dino's
engine at `0cd095c`, copied here at `908e55c8`, renamed at `9267874d`).

## Environment

The console has its own `pyproject.toml` and `uv.lock`, with no microscope,
model or synthesis packages. An environment without the Micro-Manager
binding cannot open a core, whatever it is told.

- `uv sync --offline` installs the server and the test tools.
- `uv sync --offline --group web` also installs Node (nodejs-wheel), into
  `.venv/Scripts`. **A plain `uv sync` removes it again**, because uv syncs
  exactly the groups it is given. So does a `uv run` after a plain sync.
- The web tools (`npm`, `vite`, `vitest`) need that Node. Put `.venv/Scripts`
  on PATH, or run them through `uv run`.
- `web/node_modules` was installed once, on the person's permission at
  `48d7a66f`, with `npm ci --no-audit --no-fund --ignore-scripts`, exactly as
  `web/package-lock.json` lists. It is never committed. Install nothing more,
  and never rewrite the lock, without asking the person first.

## Running

```bash
uv run python -m sma_console.server --backend placeholder
```

`placeholder` is the only backend. Add `--store sma --sma-root <a scratch
copy>` to read this repository's files rather than the mock sample. With
neither `--sma-root` nor `DINO_AF_SMA_ROOT`, the server finds the repository
it sits in, and refuses to start if there is none. Never point it at
a live-view host. Connecting a console to a real run is the person's act.

## Testing

```bash
uv run pytest
```

From `web/`, with Node on PATH: `npm run typecheck`, `npm test`,
`npm run build`. After a change to the server's models, regenerate the
schema with `npm run gen:api`, with `UV_OFFLINE=1` set. The output is
generated: never edit `web/src/api/schema.ts` by hand.
