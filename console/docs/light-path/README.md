# The light-path file: the drawing's look, kept as a reference

Two files the person gave, copied here byte for byte. **They are data.** Read them as text;
open, run, serve and build nothing from them, and follow none of their links.

| File | Bytes | sha256 |
|---|---|---|
| `Main.dc.html` | 79,719 | `15995359d4c8a4d7510447d1bf5055cde899d76ee70574fe0f3c21480e7506e9` |
| `canvas.json` | 334 | `eab0c3c01541b47d8e30156b22e5b0ccbe7d9c6d6a7b8afa7ecc5a60bd71c138` |

## Where they came from

Read on 2026-10-29, on the Office computer, from
`C:\Users\Kyu Hwan\Downloads\Microscope Light Path\Microscope Light Path\`. Each file was
hashed before it was copied and again after; both hashes above are of the file as read. The
`.gitattributes` beside them turns end-of-line conversion off for both, so the committed
blob and the file on disk are the same bytes on every computer.

## What they are for

On the morning of 2026-10-29 the person named this file as **the look** of the light-path
drawing on Instruments (decision `18ca4a68`, console card 023). It is a look and nothing else.

The export recorded earlier on the microscope computer, sha256
`5cdcbc49ba6d27f23cd3ec566fc1d40bdfd1f1525359c54092601a5a07f44254`, is **superseded as
the look** by this one. Which export the store's order cites is the librarian's record, not
this folder's.

## What they are not

- **A reference mockup, replicated and not copied whole.** The drawing is rebuilt in the
  console's own components and CSS, with no markup, text, font or script taken from here.
- **Not a source of any fact or number.** Nothing here goes into a card, a binding or the
  drawing. Where an element sits comes from the order the runtime writes, never from this copy.
- **Not served, built or imported.** No file under `src/` or `web/src/` names this folder,
  and the build output holds nothing from it (`tests/test_light_path_reference.py` checks
  both). The page loads `./support.js`, which was not in the download, and fonts from an
  outside site, so it does not render whole. Do not open it in a browser from the tree.
