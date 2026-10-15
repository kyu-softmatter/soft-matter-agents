# 074 — translate the imported dino-autofocus tree into English

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-office-20261015-2`, after card 071 lands.** If you
are not that seat, take nothing from this card and report up.

## Why, and the exception it closes

Everything in this repository is English. `microscope_agent/autofocus/`
arrives carrying Korean in **48 text files, 3,808 lines**, as counted at
`95eee95` by `git grep -I` for Hangul. That count is of record in plan.md
10.2 and `CLAUDE.md`. 3,779 of those lines are under `docs/`, and the other
29 files are code and web files. The person said to translate after the move
("번역해서 들여옴"). So `CLAUDE.md` holds **one dated temporary exception**:
the tree may carry Korean from the import commit until **this card closes**,
and not after.

## Order, so that nothing stops pointing anywhere

1. **First, fix one notation for section pointers.** The Korean in the code
   and web files is almost all pointers into dino's `docs/PLAN.md` and its
   other docs ("PLAN.md 5절", "6절 12항", "operations-spec 3절 2항"). Choose
   one English form, for example `PLAN.md §5`, `§6 item 12` and
   `operations-spec §3 item 2`. Apply it everywhere **before** the headings
   they point at are translated, so pointer and heading stay matched. Write
   the notation at the top of your first commit's message.
2. **Then `docs/`**, file by file. Translate meaning, not word for word. Keep
   every number, unit, path, identifier and code span exactly as it is.
3. **Then the code and web comments.**
   - **Screen strings are already English**, as your survey found, so there
     is no locale file to build.
   - If you meet a Korean screen string after all, move it to a locale file
     inside the tree, and keep the English as the default.
4. **The person's own words stay as they were said, with an English gloss
   beside them**, the way `plan.md` quotes the person. One known case is the
   comment at `src/dino_autofocus/engine/guards.py` line 90 at `95eee95`,
   "2800 제한 해제". Quote it and gloss it; never replace the person's words.
   **A guard value it mentions binds nothing here**: `envelope/safety.json`
   binds. Do not edit the value, and do not reword it into a limit.

## Not mixing with the other seat's work

`microscope-office-20261015-1` holds the same tree for cards 072 and 073,
which touch code files. **Until that seat reports both landed, translate
only `docs/`.** Take the code and web files after. The two seats never edit
one file at once.

## When it closes

When `git grep -I` for Hangul over `microscope_agent/autofocus/` finds only
the person's quoted words, each glossed, the card closes. **Tell
architecture**: the exception bullet in `CLAUDE.md` comes out in a commit
that is architecture's, since `CLAUDE.md` is architecture's file. Report the
final grep count.

## Boundaries

Write inside `microscope_agent/autofocus/` only. Change no number, no unit,
no path and no code behaviour: translation only. Commit in pieces, a
directory or a file family at a time, through the gate, naming each path.
Never `--no-verify`, `--amend` or force.

## What comes back

To this seat, 5 lines at most:

- the pointer notation;
- the commits;
- the Hangul count before and after;
- the quoted words kept, with their glosses;
- any screen string moved to a locale file.
