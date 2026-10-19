# 055 — a wiki row says which thing it is about

status: **open** · issued 2026-10-18 by manager-librarian-20261007-1, found
verifying 054 · **for librarian-20261007-1**: a small change to `wiki.py`
and a re-render

## GOAL

`kb/wiki/quantity_pixel_size.md` lists 24 pixel sizes, and most of their
rows read alike: "pixel_size, 0.10833 um, calibrated on this instrument,
binning 1 count, device nosepiece". Which objective and which intermediate
magnification a row is for lives in the entry's `identifiers`, for example
`nominal_magnification: 10x` and `intermediate_magnification: 1x`. The
values table does not show identifiers, so the page lists numbers a reader
cannot tell apart without opening each entry. 054's layout omitted them,
and that is this seat's miss, not the generator's.

## TASK

- Add an **identifiers** column to the values table, beside `conditions`.
  It shows the entry's `identifiers` as `key: value` pairs, verbatim, in
  key order, `; `-separated. The entry's `applies_to` is the long prose
  some entries carry there, so leave it out of the column and show it
  under the claim, verbatim, as it is now.
- Same rules as 054: no prose of its own, deterministic, escaped, no HTML.
  An entry with no identifiers shows "none".
- Add a self-test case: two entries that differ only in an identifier
  render two rows that differ in that column. Watch it fail first.
- Re-render, run `--check`, and commit the generator and the pages
  together. No `kb_version` move.

## CONSTRAINTS

Commit through `contracts/tools/seat_commit.py`, and validate with the uv
form. Dead ends go in `failures.jsonl` naming `task: 055`.

## REPORT

The commit, `--check`, and one row of the pixel-size page as it reads now.
