# 015 — Instruments, on the runtime's mock

Written by `manager-console-office-20261017-1`. You read this; you do not edit it.

**Assigned to `console-office-20261017-1` (Console 1)**, next, ahead of cards
013 and 014. The person said "목 시스템 연결해" (connect the mock system),
on its own (I-20261026-office-01, `aeea9d60`), so the mock connection comes
first. Until card 013 lands, signing on the mock reads "not built yet". If
you are not that seat, take nothing from this card and report up.

**Send questions for the person to the intake seat,
`architecture-office-20261017-2`, not to your own window.**

## Why

The person asked for Instruments to be implemented on a mock system first
(I-20261024-office-02, `5f88eab4`). For the instruments, the mock is **the
runtime on `--backend mock`**, behind the same orchestrator (plan.md 15).
The live views come from it: frames, snapshots and the stop. **The console
builds no stand-in for a runtime piece** (007). Card 012 built the screens.
This card connects them to a mock run the runtime is running.

The runtime holder's list of what is not built yet, each on manager-microscope's
cards for the runtime seat (plan.md 15.1, "Who takes what"):
- the idle status file's writer;
- check now;
- latest frames per camera;
- the mock's additions: two cameras, a moving piezo trace, trap commands
  echoed back, the confocal elements.

Each stays "not built yet" on the screen until its card lands.

## The person's named pages (`1641323a`): this section holds where it differs from below

The person's words, read 2026-10-25 (I-20261025-office-01):

> instrument 페이지는 기존 콘솔을 참고하면 좋겠어. (목 시스템 연결해줘)
> 1. 현재 연결상태를 보여주는 페이지 / 2. 광 경로를 보여주고 제어할 수 있는 페이지 (기존것 참고) / 3. 트위저 / 4. 컨포컬 / 5. 피에조 / 6. 카메라 실시간 뷰 (기존것 참고) / 7.
> 실험 페이지에는 1. 실험 계획서 / 2. 샘플 맵 (기존 것 참고)
> 라이브러리 1. 질문을 작성할 수 있는 창 / 2. 데이터 종류 별 구분 / 3. 데이터 맵 (관계도, 전문성 등) - 인사이트를 얻으려 함.
> 이것들을 구현해줘

**"The existing console" is the pre-reduction console**, read from history and
not restored: `git show 2964d0f27^:console/web/src/features/<area>/`
(`hardware`, `live`, `tweezers`, `map`, `objective`). Take its layout and its
good parts, and re-enter them under the pared-down shell and every recorded
answer. **Never bring back what those pages did to the instrument**: the
old map's click-to-move (`clickMove.ts`), light switching, configuration
drafting, objective changes and pattern runs.

The six pages are the ones card 012 built, in the person's order:
1. **connection state**: Status, laid out after the old `features/hardware`;
2. **optical path, shown and controlled**: Optics and control, after the old
   hardware page's panels;
3. **tweezers**: after the old `features/tweezers`;
4. **confocal**;
5. **piezo**;
6. **camera live view**: Cameras, after the old `features/live`.

The empty seventh line is room for a page, not a page to invent.

**"Controlled" means show, draft and stop, and that is now the person's
decision** (Q-20261025-office-04, `b8beabd7`):

> 손 제어: (1) 보기·초안·정지만으로 한다. 바꾸고 싶은 것은 계획 초안으로 만들어 비밀번호로 서명해 실행한다.

("Hands-on control: (1) show, draft and stop only. What I want changed is
made into a plan draft, signed with the password, and run.")
- No hands-on session, no plan per click, and no live set-point.
- **What a draft may cover** is what has a software path:
  - the Aura LED, the transmitted lamp and the red camera's exposure, each
    refused until the person's limit is in the safety file;
  - **the fine piezo stage**, as an `operation` plan card. The schema's
    operation block, a step or a sine on x, y or z, holds it, and the
    orchestrator exempts the piezo operation.
  - Card 012 left the piezo draft out. This card adds it, validated against
    `plan.schema.json` and saved nowhere, as the other drafts are.
- **Marked "moved by hand"**: the filters, the objectives, the light path,
  the spinning disk, the large XY stage and the trap laser.

From the runtime holder, the same day:
- **On the mock a control is a draft, exactly as on the instrument**,
  because only the backend argument changes. The draftable set is the
  same: the Aura LED, the transmitted lamp, and the red camera's exposure.
- The orchestrator's refusal list loads on every backend. So the filters,
  the objective, the condenser, the light path, the CSU-W1 and the Spectra
  III stay "moved by hand" on the mock pages too. The mock may show their
  state, labelled as the mock's, but the page never offers to change them.
- **Signing on the mock** goes through card 013's writer into the
  configured test folder, never `microscope_runtime/approvals/`. If the
  runtime's mock run cannot yet read approvals from that folder, the page
  says so, and that point goes to manager-microscope.
- **The connection-state page reads the last run's `events.jsonl` now**,
  and card 085's status file once it lands.

## The live optical path (`4582f29d`)

The person's words, read about 09:59 -0700 on 2026-10-26
(I-20261026-office-03):

> 장비 탭 안에 실시간 광경로에 대한 것도 기존것을 참고해서 만들어

("Inside the Instruments tab, also build the real-time optical path,
referring to the existing one.")
- **It goes on page 2, Optics and control.** It is not a new tab.
- **What it shows** is the path's present state, updated as the run's
  events and snapshots arrive:
  - the filter turrets, the two emission wheels, the LightPath and its
    port, and the confocal dichroic, by the registry's names;
  - the lamp and the LED, on or off with intensity, as read back;
  - beside each, the time it was read.
- **Where it comes from** is the running run's read-back, and nothing else.
  - On the mock, that is the state the mock reports (runtime card 086,
    item 6), labelled the mock's.
  - Until 086's item 6 lands, each element the run does not report reads
    "not built yet". Nothing is filled from the console's side.
  - A run that has ended leaves its last path marked "as of <time>, from
    <run>", as on the other tabs.
- **The model.** The old console had no separate optical-path screen. Its
  hardware page's read-back panels are the model:
  `git show 2964d0f27^:console/web/src/features/hardware/panels.tsx`,
  `LightsPanel`, `CurrentStatePanel` and `lightText`.
  - Take the read-back wording, the "not confirmed" warning and the read
    time.
  - Leave its Brightfield, Aura and Lights-off buttons: they sent
    commands.
- **It may be drawn as a path**, in the order the registry gives the
  elements. If the registry gives no order, show a list. Invent no order
  and no element.
- **The registry's known traps stay visible** (086): the turret label that
  names the wrong position, and the splitter states that send no light to
  one camera. A position read back is that element's position, and not
  proof of which element is in the beam. Say so beside the path.
- **Hands-on (1) holds.** The lamp and LED carry this page's draft link.
  Every other element is shown "moved by hand", with no control.
- Tests, each watched failing first, from a recorded events fixture:
  - each element's state and read time come from the fixture;
  - an element the fixture does not report shows "not built yet" and no
    value;
  - no element marked "moved by hand" offers a control;
  - on the mock, every state is labelled the mock's.

## What to do

1. **Attach to a running mock run.**
   - A run started by the runtime seat or the person on `--backend mock`
     appears in the runs folder with its `run_started` event.
   - The Instruments tabs follow the newest running run.
   - **The console starts no run.** It reads `runs/<id>/events.jsonl` as it
     grows, and uses only what the run interface offers: the stop on the
     stop channel (card 004), and the frame tap's `get` for live view.
2. **What each tab takes from the run.**
   - **Piezo**: x, y and z from the run's snapshots, with times, as read
     back.
   - **Tweezers**: trap positions and strengths from apply events, labelled
     "sent".
   - **Cameras, panel 1**: frames from the frame tap while the run acquires,
     offered to `person_login` only. Panels 2 to 4 keep card 012's
     wording.
   - **Status**: still reads the idle status file, "No status yet" while
     its writer is not built.
   - A run that has ended leaves its last values marked "as of <time>, from
     <run>".
3. **Not connected, not built.**
   - With no running run, each live tab says no run is running.
   - A piece the runtime has not built says "not built yet". Neither state
     is ever filled from the console's own side.
4. **Tests, each watched failing first.** Use events files and a recorded
   frame-tap exchange as fixtures inside `tests/`, never in the app:
   - the piezo plot reads snapshots;
   - trap positions are labelled "sent";
   - an ended run shows "as of";
   - no run means no values;
   - the console never starts a run or writes an event;
   - the frame tap is asked only for `person_login`;
   - each runtime piece that is not built shows "not built yet".

## What not to do

- No stand-in engine, frame source or status writer in the app.
- No start, command or set-point. Only the stop and the frame tap's `get`
  leave the console.
- No live-host connection beyond what card 004's and the live view's code
  already make, and that only when the person presses it.
- No write outside `console/`. Install nothing.

## Done when

- `npm run typecheck`, `npm test` and `npm run build` pass from `web/`.
- `uv run pytest` passes.
- The validator ends `0 failed`.
- One commit through `contracts/tools/seat_commit.py`. Report the hash to
  this seat, with which runtime pieces still read "not built yet".
