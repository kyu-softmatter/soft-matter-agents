# 090 — the console's "run" button starts one signed plan, and nothing else

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-office-20261017-1`, the runtime seat. Start after card 087**, whose reader and `--approvals` option this card uses. On mock it needs nothing else. If you are not that seat, take nothing from this card and report up.

## Why

The person, Q-20261026-office-01 (`ddbb95c4`):

> 서명한 계획의 시작: (2) 콘솔에 '실행' 버튼을 만든다. 콘솔은 서명된 계획 하나를 가리키기만 하고 다른 것은 보낼 수 없다. 실제 장비에서는 현미경 앞에서 장비 인계를 직접 해야 시작된다.

That is: a "run" button in the console. The console only points at one signed plan and can send nothing else. On the real instrument the run starts only once the bench is handed over in person at the microscope.

Today runs start by command, and the console can only follow and stop them. This card adds the one way the console may start a run, in the live-view pattern, which is the same shape as `live_on` and `check_now`.

## What is in `contracts/` (this card's commit)

`run_interface.schema.json` gains two messages:

- **`run_request`**: `{"run": "<sha256>"}`, the sha256 of a `plan_approval` file's raw bytes, and nothing else. It sits beside `live_on` and `check_now` on the live-view host.
- **`run_reply`**: `started` with `run_id`, `waiting_for_bench` with `run_id`, or `refused` with `reason`.

Each has `examples` and `x_refused`. The refusals include a path in place of the hash, a backend, a bench hand-over and a plan.

## What to build

In `microscope_runtime/src/`, the live-view host and the plan-run entry points:

1. **Accept `{"run": <sha256>}` and nothing else.**
   - Find the approval in the host's approvals folder by the sha256 of its raw bytes. On mock the folder may be card 087's test folder; on any other backend only the default.
   - From that approval, find the plan it names, by its id and revision, under `microscope_agent/questions/`.
   - Start it through `operator.run`, exactly as a run started by command: the approval reader with card 087's checks, card 089's rule for a `-c` question once it exists, the safety policy, and the run lock.
   - An unknown hash, an approval that does not cover the plan, a plan that cannot be found, or a held lock is refused with the reason, and nothing opens.
2. **The bench hand-over stays at the microscope.**
   - With `--backend mock`, a run starts at once and records that no bench was handed over because the backend is the mock.
   - With any other backend, the host replies `waiting_for_bench` and asks for the hand-over **on its own terminal at the microscope computer**, the way `--bench` takes the person's words today. It does not start until those words are typed there.
   - Nothing sent over the socket can stand in for it. A request carrying any key but `run` is refused.
   - If no hand-over is typed within a time you choose and state, the request lapses and is recorded, and nothing has opened.
3. **Every step leaves a trace**: the request, its hash, the approval and plan found, the reply sent, and for an instrument run the hand-over's words and time, in the run's log or, for a refusal, in the host's record, as `live_on` refusals are recorded today.

## Tests, each watched failing first

1. On mock, a `run` request naming a console-signed approval in the test folder starts that plan, and the reply is `started` with the run's id.
2. An unknown hash, an approval for a different plan revision, a missing plan, and a held run lock are each refused with the reason, and the mock records no device call.
3. A request with any second key is refused, and so is one that names a path in place of a hash.
4. With a non-mock backend (a stand-in that only records whether it was opened), the host replies `waiting_for_bench` and opens nothing until the hand-over is entered on its terminal. A hand-over sent in the request is refused.
5. Every `examples` and `x_refused` entry of `run_request` and `run_reply` is accepted or refused as the schema says, read from the schema file.

## Boundaries

- Write `microscope_runtime/src/` and `tests/` only. No `contracts/`, never `envelope/` or `approvals/`. Tests use temp folders.
- The console's button is manager-console's. Don't edit `console/`.
- Commit and push through `contracts/tools/seat_commit.py`, naming each path. Never `--no-verify`, `--amend` or force.

## What comes back

To this seat, 4 lines at most:

- the commit;
- each test, watched failing, then passing;
- the time you chose for an unanswered hand-over, and why;
- every place the schema did not fit, with the field.
