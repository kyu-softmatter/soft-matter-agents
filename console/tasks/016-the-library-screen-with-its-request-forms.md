# 016 — the Library screen, with its request forms

Written by `manager-console-office-20261017-1`. You read this; you do not edit it.

**Assigned to `console-office-20261017-1` (Console 1)**, after card 015. If you
are not that seat, take nothing from this card and report up.

**Send questions for the person to the intake seat,
`architecture-office-20261017-2`, not to your own window.**

## Why

The person asked for the Library to be built (I-20261024-office-02,
`5f88eab4`). Every allowed login may send the librarian three requests, and
none of them waits for the person: enter this document, withdraw this value,
offer this result (`89e7cf05`, `0a387d1b`). The store's manager read the
screen at canvas version 46 (`PLibrary`).

Two things frame it:
- **plan.md 4.3.1 now lets the console show the generated wiki pages under
  `librarian_agent/kb/wiki/` as data, and nothing else of the store**
  (`527376c3`, architecture-20261007-1; the store's manager agrees). That
  means:
  - read only;
  - no `caller_id`, no query;
  - nothing shown is kept or lands on a card;
  - entries, the query log and exports are not shown;
  - the console never cites a page: a fact is cited by its entry.
- **Nothing reaches the librarian until the agents' console inbox opens**
  (plan.md 7.1.1, proposed, `527376c3`). It opens only on the person's
  approval, and only once both runners refuse unapproved runs from another
  login. The request and answer schemas are manager-librarian's, written
  after that approval.

## The person's named pages (`1641323a`): this section holds where it differs from below

The person's words, read 2026-10-25 (I-20261025-office-01):

> instrument 페이지는 기존 콘솔을 참고하면 좋겠어. (목 시스템 연결해줘)
> 1. 현재 연결상태를 보여주는 페이지 / 2. 광 경로를 보여주고 제어할 수 있는 페이지 (기존것 참고) / 3. 트위저 / 4. 컨포컬 / 5. 피에조 / 6. 카메라 실시간 뷰 (기존것 참고) / 7.
> 실험 페이지에는 1. 실험 계획서 / 2. 샘플 맵 (기존 것 참고)
> 라이브러리 1. 질문을 작성할 수 있는 창 / 2. 데이터 종류 별 구분 / 3. 데이터 맵 (관계도, 전문성 등) - 인사이트를 얻으려 함.
> 이것들을 구현해줘

For the Library, **three parts**. The store's manager read them the same
day:
1. **A division by data type: build it now.** Read `kb/wiki/index.md`. Its
   sections are devices, quantities, observables, samples and
   configurations, plus unfiled, and each links to its pages. That is inside
   plan.md 4.3.1 as it stands.
2. **A data map, of relationships and expertise: the librarian's pages,
   shown like any wiki page.** The person decided this at `e1170a36`
   (Q-20261025-office-01):

   > 데이터 맵은 사서가 저장소에 관계도 페이지를 만들어 두고 콘솔은 보여 주기만 하는 방식으로 한다. '전문성'은 어떤 주제에 대해 저장소가 얼마나 알고 있는지를 뜻한다.

   ("The data map is done by the librarian making relationship pages in the
   store, and the console only shows them. 'Expertise' means how much the
   store knows about a subject.")
   - The console computes nothing: no graph from entries, no measure of
     expertise of its own.
   - It shows the relationship and evidence pages the librarian generates
     under `kb/wiki/` (librarian task 060: `evidence.md`, and the map), as
     it shows every page, footer check included.
   - Until they land, the part shows "not built yet".
   - plan.md 4.3.1 now covers every generated file under `kb/wiki/`
     (`49f0f13f`). Task 060 gives three:
     - `evidence.md`, the store by kind of evidence;
     - `map.md`, one row per subject, with its coverage and the pages it
       shares entries with;
     - `map.json`, of artifact `kb_map`: subject nodes with coverage
       `{"E1".."E5": count}` and `disputed`, entry nodes with grade, source
       and status as recorded, and edges typed `about`, `conflict_with`,
       `refutes`, `supersedes`, `supports` or `input_of`, each naming who
       stated it.
   - **Coverage is shown as the counts stand**: no score, no ranking, no
     single expertise number.
   - When the map's `kb_version` is behind `kb/index.json`'s, say so, as for
     pages.

3. **A window for writing a question: wait for the person.** The store's
   manager is asking what it is:
   - a search over the wiki;
   - a question to the librarian answered with its sources, once the inbox
     opens;
   - card 010's question window placed in the Library.

   Until a committed answer, the part shows that it is being decided. The
   three store requests below are built as their own forms either way.

## What to do

1. **What the library holds: the wiki pages, from `kb/wiki/` only.**
   - The pages are flat: `index.md`, `unfiled.md`, and
     `<section>_<id>.md`, where the section is device, quantity,
     observable, sample or configuration. Start at `index.md`.
   - **A page is shown as it stands**, with the provenance and grade beside
     each number as the page writes them.
   - **Its last line is the footer**, exactly: "Generated from the
     knowledge store at kbv-<12 hex>. Do not edit by hand: correct the store
     and regenerate." Check 87 holds that line. Compare that version with
     the current one in `kb/index.json`. When the index has moved past it,
     say plainly that the page was built from an older version of the
     store.
   - **Links between pages are followed. A link to an entry or a guide is
     shown as text and not followed**, because only `kb/wiki/` may be
     displayed.
   - Read nothing else under `librarian_agent/`, except the version in
     `kb/index.json`.
2. **Three tabs of forms, open to every allowed login.**
   - **Add a document or a value.**
     - The kind of source: a maker's document, a paper, read off the
       instrument, or I remember it.
     - Who read it.
     - A file, or for a remembered value, the value and its unit.
     - What to take from it, in the asker's words.
     - A remembered value is labelled as entering at the lowest grade. A
       note says the grade comes from the kind of source.
   - **Withdraw a value.**
     - The entry's name in the library, typed or pasted.
     - The reason, in the asker's words.
     - Evidence, if any: a contradicting reading, a document, or the
       replacing entry.
     - A note says words alone cannot refute a value.
   - **Offer a result.**
     - Which result.
     - The fact it shows, in the asker's words.
3. **Send checks the form and sends nothing.** It answers "Not sent: the
   librarian's inbox is not open yet." No file is written: the request
   schema is not written yet, so the console invents no shape.
4. **The answers list.**
   - Under `--store mock`, example answers from the mock sample, labelled
     "example data", covering all seven: entered, naming its entry; waiting
     for a name; refuted; in conflict; superseded; kept, with the reason; no
     entry of that name.
   - Under `--store sma`: "No answers yet."
5. **Tests, each watched failing first:**
   - the only paths read under `librarian_agent/` are generated files under
     `kb/wiki/`, and `kb/index.json` for its version alone;
   - coverage is shown as counts, never as a score or a rank;
   - a link to an entry or a guide is shown as text and never followed;
   - a page whose footer version is behind `kb/index.json` says so;
   - Send writes nothing and makes no request beyond the console's own
     check;
   - a remembered value carries the lowest-grade label;
   - the mock's answers cover the seven outcomes, each labelled example;
   - the real store shows "No answers yet".

## What not to do

- Read nothing of the store beyond the wiki pages and the index's version.
  Call nothing of the librarian's: no `caller_id`, no query.
- Write no request file.
- No write outside `console/`. Install nothing.

## Done when

- `npm run typecheck`, `npm test` and `npm run build` pass from `web/`.
- `uv run pytest` passes.
- The validator ends `0 failed`.
- One commit through `contracts/tools/seat_commit.py`. Report the hash to
  this seat.
