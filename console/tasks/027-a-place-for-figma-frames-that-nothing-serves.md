# 027 — a place for Figma frames, that nothing serves

Written by `manager-console-office-20261017-1`. You read this; you do not edit it.

**Assigned to `console-office-20261017-1` (Console 1).** If you are not that
seat, take nothing from this card and report up.

**Start line: build now, to this card's commit.** Send questions to this seat.
Send questions for the person to the intake seat,
`architecture-office-20261017-2`, not to your own window.

## Why

The person decided that the console's interface design is to be tried in
Figma (D-20261103-office-10, `93ab0a9a`): "인터페이스 디자인은 Figma를
이용해보도록 하자." (Let us try Figma for the interface design.) This seat's
method for it is recorded as R-20261103-office-03 (`d9c05de2`):
- **Pin.** A card builds only to an exported frame kept in the tree with its
  sha256. A Figma file changes in place and lives outside the tree, so
  "built to the design" can be checked afterwards only against a fixed copy.
- **Look only.** A frame gives boxes, type, colour, spacing and panels. It
  never gives an element, an order, a branch's area word or a number. If a
  frame draws something other than the record says, the page draws the
  record. plan.md 15.1 items 8 and 11 already say so, and Architecture 3
  confirmed that the plan needs no new line.

The person then answered that exported screen images may be kept in this
repository, which is public on GitHub (D-20261104-office-01, `f35e2c97`):
"올려도 됨" (may be uploaded).

This card builds the place where those frames will be kept, and the tests
that keep them out of everything the console serves or builds, **before any
frame exists**. The first frame then lands with a few lines, and the guard is
already watched failing.

## What this card does not depend on

Three of the person's answers are still open. This card holds under each
answer, because it files no frame and writes no link.
- **Who draws, and in which Figma account** (Q-20261103-office-05). The
  folder does not say who drew a frame.
- **How a design is handed over** (Q-20261103-office-06): an exported
  picture left in Downloads, or Figma connected to the app under the
  person's own login. Either way a frame enters the tree the same way, by a
  later console card that names its source file, its bytes and its sha256.
- **Whether a Figma link may appear in the repository, and whether part
  names may go into a Figma file** (the rest of Q-20261103-office-07). No
  link is written here, and a test keeps it so. Part names in a frame are
  not read in any case, since a frame gives the look only.

## What to build

All of it in `console/docs/figma/` and `console/tests/`. Nothing in `src/`,
`web/`, the server or `contracts/`.

1. **`console/docs/figma/frames.json`**, the one list of filed frames. It
   starts as `{"frames": []}`. Each entry, when a later card adds one, has
   exactly these keys:
   - `file`: the file's name in this folder, lower-case ASCII words joined
     by hyphens, ending `.png`;
   - `bytes`: its size, a positive integer;
   - `sha256`: 64 lower-case hex digits;
   - `card`: the three-digit number of the console card that filed it;
   - `read`: the date the source was read, `YYYY-MM-DD`.
2. **`console/docs/figma/.gitattributes`** has one rule, `*.png binary`, and
   a comment saying why: the bytes on disk are the bytes committed, on every
   computer.
3. **`console/docs/figma/README.md`** says, in plain English:
   - what the folder holds: frames exported from the person's Figma design
     of the console, kept byte for byte as the console's look;
   - the two decisions, with their lines and hashes above;
   - **look only**, in this card's words: boxes, type, colour, spacing and
     panels; never an element, an order, an area word or a number; the page
     draws the record where a frame differs;
   - **PNG only.** An SVG is markup that a browser can run, and a PDF is a
     document. A picture is enough to build to;
   - a frame enters only by a console card naming its source, bytes and
     sha256, and the card that filed it is named in `frames.json`;
   - **no link to a Figma file is written here**, because the person has
     not said one may be;
   - nothing serves, builds or imports a file from here;
   - a table of the filed frames (file, bytes, sha256, card), which says
     "No frame is filed yet." while the list is empty.
4. **`console/tests/test_figma_frames.py`**, modelled on
   `test_light_path_reference.py`. Its checks:
   - `frames.json` parses; its only key is `frames`; `frames` is a list; each
     entry has exactly the five keys, in the forms above; no `file` and no
     `sha256` repeats; each `card` names a file `console/tasks/<card>-*.md`
     that exists;
   - each listed file exists, and its size and sha256 equal its entry's; it
     begins with the eight-byte PNG signature;
   - the folder holds `.gitattributes`, `README.md`, `frames.json` and the
     listed files, and nothing else, with no subfolder;
   - `.gitattributes` holds the one rule. Where git is on the path, `git
     check-attr text` reports `unset` for a `.png` path in the folder, and
     each listed file's committed hash equals its on-disk hash;
   - the README names every listed sha256, and both decision hashes
     (`93ab0a9a`, `f35e2c97`);
   - no text file in the folder contains `figma.com`;
   - no file under `src/` or `web/src/` names the folder, `docs/figma`, with
     either slash;
   - where `web/dist` exists, it holds no file with a listed file's name or
     sha256, and no file named after anything in the folder.
5. **`console/docs/screens/instruments.md`**, near line 75 where it names
   `docs/light-path/`, gains one sentence: the look will come from Figma
   frames filed in `docs/figma/` once the person sends them. Until then it
   is the light-path file's, as card 026 built it.

## Tests, each watched failing first

The list is empty, so most checks have nothing to fail on yet. Watch each one
fail with a temporary change, revert it, and list each in your report:
- a file in the folder that is not listed;
- a listed entry with a wrong sha256 or size. Use a tiny PNG you generate in
  the test run's own temporary folder, not a Figma export;
- a listed file that is not a PNG;
- an entry with a sixth key, or a `card` that names no card;
- `figma.com` in the README;
- a file under `web/src/` naming `docs/figma`;
- a `web/dist` file whose sha256 equals a listed frame's.

Leave no temporary file in the tree.

## What not to do

- File no frame. Open no Figma, sign in nowhere, connect no connector, and
  install nothing.
- Write no Figma link, file id or version id anywhere.
- Change nothing that cards 023 to 026 built. The look stays as it is.

## Done when

- `uv run pytest -p no:cacheprovider` passes, and the new file's count is in
  your report.
- The validator ends `0 failed`. Quote its tree line.
- One commit, made through `contracts/tools/seat_commit.py`. Report its hash
  to this seat.
