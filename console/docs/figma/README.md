# Frames from the person's Figma design of the console

This folder holds screen images (frames) exported from the person's Figma design of the
console, kept byte for byte as the console's look. It was built by console card 027, **before
any frame exists**, so the guard is in place and watched failing when the first frame lands.

## Why it exists

- **The person decided to try Figma for the console's interface design.** D-20261103-office-10,
  `93ab0a9a`: "인터페이스 디자인은 Figma를 이용해보도록 하자." (Let us try Figma for the interface design.)
- **The person said exported screen images may be kept in this repository**, which is public on
  GitHub. D-20261104-office-01, `f35e2c97`: "올려도 됨" (may be uploaded).

The method is the console manager's, R-20261103-office-03 (`d9c05de2`): pin, and look only.

## Pin

A card builds only to a frame kept in this folder with its sha256. A Figma file changes in place
and lives outside the repository, so "built to the design" can be checked afterwards only against
a fixed copy.

## Look only

A frame gives **boxes, type, colour, spacing and panels**. It never gives an element, an order, an
area word or a number. Where a frame draws something other than the record says, the page draws
the record.

## What may be kept here

- **PNG only.** An SVG is markup that a browser can run, and a PDF is a document. A picture is
  enough to build to.
- A frame enters only by a console card that names its source, its bytes and its sha256. The card
  that filed it is named in `frames.json`, which is the one list of filed frames.
- **No link to a Figma file is written here**, because the person has not said one may be. Nor is
  a file id or a version id.
- **Nothing serves, builds or imports a file from here.** No source file names this folder, and
  the web build holds none of it. `console/tests/test_figma_frames.py` keeps all of that so.

## Filed frames

| File | Bytes | sha256 | Card |
|---|---|---|---|
| No frame is filed yet. | | | |
