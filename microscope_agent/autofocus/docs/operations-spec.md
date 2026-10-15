# 엔진 작업(operation) 명세 (T-006, 초안)

- 작성: AF 실행4 · 개발 (2026-10-01). 소유: 이 파일 하나 (T-006).
- 목적: 벤치 스크립트가 하는 일을 엔진 작업의 `plan → preflight → run → abort` 로 풀어,
  WP-C 이식을 기계적으로 만든다. T-002 (가드, 백엔드 계약) 와 T-004 (UI 명세) 의 입력이다.
- 근거 코드: `scripts/*.py` (main `6ba1bc1`) (R-05 에서 삭제; 이력에 있음). 운영 기록: `docs/runs/2026-09-30_substrate-scan.md`
  (이하 "9/30 기록"), 같은 이름의 `.yaml`. 계획: `docs/PLAN.md` v0.2.
- **추론** 표시: `C:\agentic_microscope\hardware\focus.py` (FocusAxis) 는 이 PC 에 없다.
  스크립트의 사용 방식에서 짐작한 동작은 "**추론**" 으로 적고, 확인할 질문은 마지막 절에 모은다.

진행 상태 (작성 순서는 매니저 지시, T-006 "v0.2 조정")

| 절 | 작업 | 상태 |
|---|---|---|
| 1 | `lights_off` | 초안 |
| 2 | `status` | 초안 |
| 3 | `scan_4x` | 초안 |
| 4 | `objective_change` (PLAN 2절 F5 7단계 포함) | 초안 |
| 5 | `hardware_scan` (F2) | 초안 |
| 6 | `sample_map`, `map_flag`, `goto_xy` (F4) | 초안 |
| 7 | `focus_100x` | 초안 |
| 8 | `edge_trace` | 초안 |
| 9 | 보류와 범위 밖: `find_particle_z`, `focus_servo` | 초안 |
| 10 | 현미경 PC 에서 확인할 질문 | Q1–Q21 |

매니저 결정 반영 (T-002 부록 3, main `69e6ba5`): `scan4x_<stamp>/` 폴더 유지 + `scan.json` 병행,
`lights_off` 는 선점 명령, 상태 표시는 `position` 이벤트, `hole.fitted_at`, 원본 빈틈 세 가지.

T-024 (실행17): 0.1 과 각 절의 호출 이름을 main `543c5ee` 의 `backend.py` (T-002-1, T-015), `events.py`, `guards.py` (T-002-2) 에 맞췄다.
방향 기준은 PLAN v1.2 (5절, 9/30 기록): ZDrive 값이 커지면 시료 쪽이고 0 이 후퇴, 스윕은 상향, 영상은 재물대와 거울상,
4x 타일은 serpentine. 이 문서의 서술은 이 기준과 맞는다.

## 0. 공통 약속

### 0.1 호출 이름표

"run" 표의 **엔진 호출** 열은 아래 이름을 쓴다. 백엔드 이름은 main 의
`src/dino_autofocus/engine/backend.py` (T-002-1 프로토콜 + T-015 확장), 가드 이름은 `engine/guards.py` (T-002-2) 를
따른다 (main `543c5ee`). "(T-015)" 는 T-015 가 넣은 메서드 표시다.

| 구분 | 이름 | 스크립트 원본 |
|---|---|---|
| 백엔드 수명 | `open()` → `BackendInfo`, `close()` | `mm_grab.open_core` (config 로드, AutoShutter 0, 노출, ROI) |
| 백엔드 정보 | `info()` → `BackendInfo`: kind, config, camera, sensor, roi, exposure_ms, pixel_um, objective, intermediate_mag, bit_depth, `ceiling_adu` (= 2^bit_depth − 1), `objectives[]` (`ObjectiveInfo`: state, label, magnification, pixel_um, free_wd_um), `stage_limits` (`StageLimits`: x_um, y_um, z_um, 모르면 None), `notes{}` (예: `aura.CYAN` = "unmeasured provisional"), `bench` (실제 현미경 mm-real 이면 True) | `open_core` 의 `info`, `core.getImageBitDepth()` |
| 프레임 | `snap()` → `Frame` (image uint16, t_read, exposure_ms, x_um, y_um, z_um) | `core.snapImage(); core.getImage()` |
| 설정 | `set_exposure(ms)` → 읽은 노출, `set_roi(size)` → 읽은 ROI (0 = 전체 센서) | `core.setExposure`, `core.setROI / clearROI` |
| 위치 | `positions()` → `Positions`: x_um, y_um, z_um, piezo_um{}. 실패는 예외가 아니라 None + `errors{}` | `mm_grab.positions` |
| 속성 | `read_property(dev, prop)` → 문자열, `set_property(dev, prop, v, token=None)` → `Readback` (device, prop, wanted, read, verified, t, notes). 허용 목록 `check_set_property`: 모션 장치는 언제나 거부, 조명 속성은 token 필요, 카메라 속성 몇 개는 token 없이, 나머지는 거부 | `core.getProperty`, `mm_grab.set_and_read` |
| 조명 | 켜기 `lamp_on(token=)`, `aura_line_on(line, percent, token=)` (DiaLamp 를 먼저 끔) 는 token 필요 (PLAN D15). 끄기 `lamp_off()`, `aura_off()`, `all_off()` 는 token 없음 (정지 동작). 모두 `list[Readback]`. 읽기는 `light_state()` → `{"DiaLamp": .., "Aura": ..}`. 작업은 `scope.lamp_on()`, `scope.aura_line_on(line, percent)` 로만 켠다 | `set_and_read(DiaLamp, State, ·)`, `mm_grab.aura_on / aura_off` |
| Z | `move_z(z_um, token=)` → 읽은 z. **가드만 부른다** | `core.setPosition("ZDrive", ·)` (FocusAxis 안) |
| XY | `move_xy(x_um, y_um, token=, timeout_s=None)` → 읽은 (x, y). **가드만 부른다**. 읽기는 `positions()` | `core.setXYPosition; waitForDevice` |
| 렌즈 | `nosepiece()` → label (예: `1-Plan Apo LmbdD20 4x`). State 는 `info().objectives` 에서 label 로 찾는다. `set_nosepiece(state, token=)` → `Readback`. **가드만 부른다** | `getProperty / setProperty("Nosepiece", ...)` |
| PFS | `pfs()` → `PfsState` (enabled, locked, in_range 문자열, `.out_of_range`). `pfs_off(token=)` → `Readback`. **가드만 부른다** | `isContinuousFocusEnabled / Locked`, `PFS in Range` |
| 탐지 (T-015) | `describe_devices(include_properties)`, `nosepiece_labels()`, `piezo_read(port)`, `config_record()` | 5절 |
| XY 상대 이동 (T-015) | `move_xy_rel(dx_um, dy_um, token=, timeout_s=None)` → 읽은 (x, y). 가드 `XYAxis.goto_rel` 은 이것을 부르지 않고 절대 이동으로 바꿔 `goto` 를 탄다 | `setRelativeXYPosition` (8절) |
| 연속 취득 (T-015) | `start_stream(interval_ms)`, `next_frame(timeout_s)`, `stop_stream()`, `streaming()`. 프레임 메타는 `snap()` 과 같다. 스트림 중 `snap()` 은 `StreamActive` 예외. 스트림은 엔진 (T-011) 소유 | `startContinuousSequenceAcquisition`, `popNextImageAndMD` (8절) |
| 가드 Z 축 | `axis = FocusAxis(backend, objective, allow_motion=, dry_run=, sink=, op_id=)`. `objective` 는 label 또는 레지스트리 키 | `FocusAxis(core, key, allow_motion=, dry_run=)` |
| | `axis.plan(c, half, step)`, `.describe()` | 같음 |
| | `axis.sweep(plan, grab, score=, settle_s=)` → `.points[i].{z_um, z_readback_um, score, diagnostics}`, `.argmax_index`, `.peak_z_um`, `.peak_interior`, `.at_top` (피크가 맨 위 평면) | 같음. `at_top` 은 새 이름 |
| | `axis.move_to(z, allow_ascent_um=)` (목표는 창 2800–3200 안), `axis.park_at(z)` (하강만, 0 까지) → 착지 z readback, `axis.position_um()` | 같음 |
| | `axis.require_pfs_quiet(disable=True)` | 같음 |
| | `axis.approach(target_um, step_um=None, clearance=None)`: 2800 µm 아래면 2800 까지 한 번, 그다음 `OBJECTIVE_LIMITS[key].approach_step_um` 이하 걸음. 걸음마다 readback, 상승 확인, `clearance(z)`. `info().bench` 가 True (실제 현미경) 이면 `clearance` 가 있어야 한다 (`backend.py`) | 새 이름 (F5 7단계). 원본에 없음 |
| | `best_z_um(coarse, fine)` → `(z \| None, why)`, `registry_key(label)`, `limits_for(label)` → (`ObjectiveLimits`, 행 이름) | 같음. `limits_for` 는 새 이름 |
| 렌즈 회전 | `rotate_nosepiece(backend, axis, state)` → 새 label. Z ≤ `RETRACTED_MAX_Z_UM` (1 µm), PFS off 이고 Out of Range 일 때만 | `setProperty("Nosepiece", "State", N)` |
| 가드 XY | `xy = XYAxis(backend, XYBox.around(centre, half_um), allow_motion=, dry_run=, timeout_s=)`. 박스는 + 1 mm (`XY_BOX_MARGIN_UM`) | `scan_4x.goto_xy` 안의 `box` 검사 |
| | `xy.goto(x, y)`, `xy.goto_rel(dx, dy)` → 읽은 (x, y). 박스 밖 거부, readback 비교 (`XY_TOL_UM` 5 µm, 임시) | `goto_xy`, `setRelativeXYPosition` |
| | 큰 XY 이동 (`OBJECTIVE_LIMITS[key].long_xy_um` 초과, 렌즈는 이동마다 다시 읽음) 은 Z ≤ `RETRACTED_MAX_Z_UM` 이 읽힐 때만 | 새 가드 (F4 클릭 이동, F5 이탈·복귀). 원본에 없음 |
| 작업 범위 | `with operation(backend, parent, op, sink, args=, prefix=, user_id=, session_id=) as scope:` 기록 폴더, `started`, 모든 종료 경로의 소등과 `finished` / `aborted` / `error`. `scope.result` 가 summary.json 으로 | 스크립트마다 다른 `finally` |
| | `scope.lamp_on()`, `scope.aura_line_on(line, percent)`: 켜고 `light_changed`, `verified` 가 거짓이면 `GuardError` | `set_and_read`, `aura_on` |
| | `scope.ask(key, text, **data)` → bool: `confirm_required` → 같은 `key` 의 `confirm` → `confirmed`. 기다리는 동안 abort 를 받는다 | 런처 대화상자, 사람의 채팅 승인 |
| | `exclusive(backend)` (코어 단일 소유), `lights_off(backend)` (선점 소등, 예외 없이 결과 dict) | `hardware_users()`, `lights_off.py` |
| 순수 함수 | `vollath4`, `parabola_peak`, 4×4 peak, `block_scores` | `mm_grab.vollath4`, `scan_4x.*`, `focus_100x.peak` |

순수 함수(초점 지표, 포물선)는 `focus/` (WP-E, T-003) 소유로 보고, 작업은 import 만 한다.

- **모션과 조명 켜기 메서드** (`move_z`, `move_xy`, `move_xy_rel`, `set_nosepiece`, `pfs_off`, `lamp_on`,
  `aura_line_on`, 조명 속성의 `set_property`) 는 가드의 `MotionToken` 을 `token=` 으로 받고, 없으면 백엔드가
  `UnguardedMotion` 으로 거부한다. 작업은 이 메서드를 직접 부르지 않고 `FocusAxis`, `XYAxis`, `rotate_nosepiece`,
  `scope.lamp_on()` / `scope.aura_line_on()` 을 거친다. `axis.require_pfs_quiet(disable=True)` 는 `pfs()` 로 읽고
  `pfs_off()` 로 끄는 가드 메서드다.
- 임시 가드 값 (`guards.py`, 모두 "unmeasured provisional", 쓰인 모션 기록에도 표시): `Z_SAFE_UM` 0,
  `RETRACTED_MAX_Z_UM` 1, `Z_TOL_UM` 0.25, `XY_TOL_UM` 5.0, `ESCAPE_DY_UM` +15000 (F5 이탈 +Y 15 mm, PLAN v1.3), 렌즈별 `OBJECTIVE_LIMITS`
  (`long_xy_um`: 4x 10 mm, 100x Oil 156 µm, `approach_step_um`: 10 µm). 확인 항목은 `docs/microscope-pc-checklist.md`.
- 백엔드의 z 는 언제나 벤치 좌표 (ZDrive µm, 창 2800–3200) 다. 데모 Z 처럼 원점이 다른 장치는 백엔드 안에서 오프셋한다.
- 조명 메서드와 쓰기는 모두 `Readback` (또는 그 목록) 을 돌려준다. "readback 확인" 은 `verified` 가 모두 참인지 본다.

### 0.2 이벤트와 기록

- 이벤트 종류는 T-002 `events.py` 의 `EVENT_KINDS` 를 쓴다: `planned`, `preflight_ok / preflight_failed`,
  `started`, `progress`, `frame_ready`, `reading`, `finished`, `aborted`, `error`, `position`,
  `light_changed`, `property_set`, `motion`, `confirm_required`, `confirmed`, 명령에 대한
  `proposed`, `approved`, `rejected`, `refused`, `updated`, 화면 상태의 `map_changed`, `sample_opened`,
  `objective`, `session_changed`, 그리고 `log`. 모든 이벤트는 `kind`, `op_id`, `data` (JSON 기본형), `t` 를 가진다.
- 명령 종류는 `COMMAND_KINDS`: `start` (`op`, `args`), `abort` (`op_id`), `confirm` (`op_id`,
  `args = {"key": <confirm_required 의 data["key"]>, "ok": bool}`), `lights_off` (선점), `update`
  (`op_id`, 작업이 선언한 인자만 실행 중에 바꾼다), `approve` / `reject` (assistant 제안의 결정). 모든 명령에
  `origin` (`human` / `assistant`), `user_id`, `session_id` 가 붙는다 (아직 없으면 None).
  `confirm_required` 의 종류는 `CONFIRM_KINDS`: `question` 과 `manual_step` (F5 "Loading done", 요약의
  `manual_steps` 에 남는다). 모두 main 의 `events.py` 에 있다 (T-011).
- 아래 절의 `confirm_required("...")` 는 `scope.ask(key, text)` 의 질문 문구다. 답은 같은 `key` 의 `confirm` 명령으로
  오고, 엔진은 그 답을 `confirmed` 이벤트로 기록한다.
- 기록 폴더는 T-002 대로 `<sample_dir>/<op>_<stamp>/log.jsonl` + `summary.json`.
  샘플이 없는 작업(`status`, `lights_off`)은 T-002 의 기본 기록 위치를 따른다
  (런처의 `outputs/launcher_logs` 에 해당).
- 각 절의 "기록" 항목은 (a) 지금 스크립트가 쓰는 파일과 필드, (b) 엔진 기록에서 어디로 가는지를 적는다.

### 0.3 모든 작업에 공통인 것

| 항목 | 지금 스크립트 | 엔진에서 |
|---|---|---|
| 코어 열기 | 스크립트마다 `open_core()` 로 config 를 다시 로드한다. 로드 시 System/Startup 프리셋 (`LappMainBranch1 State 1`, `mm_grab.py` 머리말) 이 적용되고 노출과 ROI 가 바뀐다 | 엔진이 백엔드를 한 번만 연다 (코어 단일 소유). 작업은 `open()` 을 부르지 않는다 |
| 다른 프로그램 점유 | 런처의 `hardware_users()` 가 프로세스 명령줄로 확인하고 경고만 한다 | 같은 검사를 엔진 시작 시 한 번. 작업 단위가 아니라 엔진 단위 |
| stdout 로그 | 런처가 `run_logged.py` 로 `launcher_<label>_<stamp>.log` 에 복사 | `log` 이벤트로. 파일은 `log.jsonl` 에 함께 |
| Ctrl+C | `KeyboardInterrupt` → 각 스크립트의 `finally` | `abort` 명령. 작업은 프레임과 이동 사이에서 멈추고 가드의 종료 경로를 탄다 |
| 소등 | 스크립트마다 다르다 (각 절의 abort 항목) | `operation()` 범위가 모든 경로에서 `all_off()` + readback (T-002) |

## 1. `lights_off`

원본: `scripts/lights_off.py` (R-05 에서 삭제; 이력에 있음). 런처 버튼 "Lights off (Aura + DiaLamp)" (`hw=True`).

**1) 입력 인자**: 없음. 원본은 코어를 `open_core(10.0, 0)` 으로 연다 (노출 10 ms, 전체 센서). 엔진 인자 없음.

**2) plan**: 계산할 것 없음. 보여 줄 문구: "Aura State → 0, DiaLamp State → 0. Nothing moves."

**3) preflight**: 원본에는 없다. 엔진에서는 현재 조명 상태를 읽어 `reading` 으로 남긴다
(`light_state()`). 읽기가 실패해도 막지 않는다. 소등은 항상 시도한다.

**4) run**

| # | 스크립트 호출 | 엔진 호출 | 비고 |
|---|---|---|---|
| 1 | `open_core(10.0, 0)` | (엔진이 이미 연 백엔드) | 원본은 config 재로드와 노출 변경이 따라온다 |
| 2 | `aura_off(core)` = `set_and_read("Aura", "State", 0)` | `aura_off()` | 마스터 State 만 끈다. 라인(`GREEN 1`)과 세기(`GREEN_Intensity 10`)는 그대로 남는다 |
| 3 | `set_and_read("DiaLamp", "State", 0)` | `lamp_off()` | |
| 4 | `verified` 가 거짓인 항목을 `WARNING` 으로 출력 | 거짓이면 `error` 이벤트, 결과 `finished(ok=False)` | 원본은 그래도 종료 코드 0 |

엔진에서는 2–3 을 `all_off()` 하나로 묶는다. 가드의 종료 경로가 부르는 함수와 같은 것이어야 한다.

**5) abort / finally**: 원본에 `finally` 없음. 엔진의 `lights_off` 는 그 자체가 종료 경로다.

결정: `lights_off` 는 **다른 작업이 실행 중이어도 받는다** (`events.py` 의 `COMMAND_KINDS` 에서 선점 명령). 받으면 실행 중 작업에 `abort` 를 보내고,
그 작업의 종료 경로가 끝난 뒤 `all_off()` 를 한 번 더 확인한다. 지금 런처는 하드웨어 작업이 돌고 있으면
`lights_off` 도 거부한다. 그런데 불이 켜진 채 멈춘 작업이 있을 때가 이 버튼이 가장 필요한 순간이다.

**6) 기록**

| 지금 | 엔진 |
|---|---|
| stdout: `set_and_read` 의 JSON 두 줄 (`device, property, wanted, read, verified`) + 요약 한 줄 | `property_set` 이벤트 (`all_off()` 의 `Readback` 마다: device, prop, wanted, read, verified), `light_changed`, `summary.json`: `{aura_state, dialamp_state, verified}` |

**7) 확인 지점**: 없음 (안전한 방향).

**8) 9/30 기록 대응**: 종료 상태 "Aura OFF, DiaLamp OFF (both read back)". 알려진 문제 4번
(`live_focus.py` 가 창을 닫을 때 DiaLamp 를 끄지 않음) 때문에 이 버튼이 생겼다. 엔진에서는
`edge_trace` 와 라이브 뷰의 종료 경로가 소등을 하므로, 이 버튼은 확인과 비상용이 된다.

## 2. `status`

원본: `scripts/change_objective.py --status` (`state()` 함수) (R-05 에서 삭제; 이력에 있음). 런처 Step 0 "Show objective / Z / PFS".

**1) 입력 인자**: `--status` 하나. 원본은 코어를 `open_core(30.0, 0)` 으로 연다. 엔진 인자 없음.

**2) plan**: 없음. 읽기만 한다.

**3) preflight**: 없음.

**4) run**

| # | 스크립트 호출 | 엔진 호출 | 읽는 값 |
|---|---|---|---|
| 1 | `open_core(30.0, 0)` → `info` 출력 | `info()`, `positions()` | config, camera, autoshutter, exposure_ms, sensor, roi, pixel_um, objective, intermediate_mag, position (x_um, y_um, z_um) |
| 2 | `getProperty("Nosepiece", "State")`, `getProperty("Nosepiece", "Label")` | `nosepiece()`, State 는 `info().objectives` 에서 label 로 | `nosepiece_state`, `nosepiece_label` |
| 3 | `getPosition("ZDrive")` | `positions().z_um` | `z_um` (소수 3자리) |
| 4 | `isContinuousFocusEnabled()`, `isContinuousFocusLocked()` | `pfs()` | `pfs_enabled`, `pfs_locked`. 원본은 실패하면 `"unreadable: <exc>"` 문자열, `PfsState` 는 None |
| 5 | `getProperty("PFS", "PFS in Range")` | `pfs()` | `pfs_in_range` (`"In Range"` 또는 `"Out of Range"`). 실패하면 같은 문자열 |
| 6 | (없음) | `light_state()` | **추가 제안**: 조명 상태. 종료 상태 확인과 상태 표시줄에 필요하다 |
| 7 | (없음) | `info().bit_depth`, `info().ceiling_adu` | **추가 제안**: 카메라 천장. scan_4x 첫 시도의 실패 원인이었다 (3절 8항) |

- Nosepiece 번호: `State` 는 0 부터, `Label` 앞 숫자는 1 부터다. 4x 는 State 0 / `1-Plan Apo LmbdD20 4x`,
  100x Oil 은 State 5 / `6-Plan Apo LmbdD0.13 100x Oil`. UI 는 Label 을 보여 주고 명령은 State 로 보낸다.
- 원본은 "Read only" 라고 하지만, `open_core` 가 config 를 다시 로드하면서 Startup 프리셋, 노출 30 ms,
  ROI 해제를 적용한다. 엔진의 `status` 는 이미 열린 백엔드에서 읽기만 하므로 이 부작용이 없다.

**5) abort / finally**: 없음. 아무것도 켜거나 움직이지 않는다.

**6) 기록**

| 지금 | 엔진 |
|---|---|
| stdout 에 `info` JSON 한 줄과 `state` JSON 한 줄. 파일은 런처 로그뿐 | `reading` 이벤트 하나 (위 표의 필드 전부). 사용자가 명시적으로 실행했을 때만 `status_<stamp>/summary.json` |

제안: 상태 표시줄의 주기적 갱신은 `status` 작업이 아니라 `position` 이벤트로 한다. 그래야 몇 초마다
기록 폴더가 생기지 않는다. 결정은 T-002, T-004 에 맡긴다.

**7) 확인 지점**: 없음.

**8) 9/30 기록 대응**: Step 0. 결과 `Nosepiece 0 = 1-Plan Apo LmbdD20 4x`, ZDrive 62.9 µm,
PFS off / "Out of Range". 실패 사례 없음. ZDrive 62.9 µm 는 Z 창(2800–3200) 밖이다.
이 값을 scan_4x 의 `z_guess` 규칙이 어떻게 다루는지는 3절 3항에 있다.

## 3. `scan_4x`

원본: `scripts/scan_4x.py` (R-05 에서 삭제; 이력에 있음). 런처 Step 2 "Start 4x scan" (확인 대화상자 뒤 실행), "Dry run" 체크.

**1) 입력 인자**

| 명령행 | 기본값 | 엔진 인자 이름 | 비고 |
|---|---|---|---|
| `--sample` | (필수) | `sample_id` | `sample.json` 의 `hole` 이 있어야 한다 |
| `--margin` | 500.0 µm | `margin_um` | 구멍 둘레에 더하는 여유 |
| `--overlap` | 0.15 | `overlap` | 타일 겹침 비율 |
| `--exposure` | None (자동) | `exposure_ms` (None = 자동) | 자동 노출은 run 10번 |
| `--aura LINE PERCENT` | GREEN 1 | `aura_line`, `aura_percent` | 퍼밀 변환(`GREEN_Intensity = 10`)은 백엔드 몫 |
| `--z-guess` | None | `z_guess_um` | None 이면 현재 Z 가 2800–3200 안일 때 현재 Z, 밖이면 2960 |
| `--first-half-range` | 160.0 µm | `first_half_um` | 첫 타일 거친 스윕 반폭 |
| `--tile-half-range` | 50.0 µm | `tile_half_um` | 이후 타일 거친 스윕 반폭 |
| `--dry-run` | False | `dry_run` | 계획만 출력. 원본은 첫 스윕 계획 하나만 보여 준다 |
| `--no-preview` | False | (없음) | 미리보기는 UI 몫. 엔진은 항상 `frame_ready` 를 낸다 |

코드 안의 고정값 (엔진에서는 이름 붙은 상수 또는 숨은 인자로 둔다):

| 값 | 원본 위치 | 이름 제안 |
|---|---|---|
| 거친 스텝 10 µm (첫 타일), 6 µm (이후) | `sweep_pair(z_ref, hr, 10.0 if first else 6.0, 12.0, 2.0)` | `coarse_step_first_um`, `coarse_step_um` |
| 고운 스윕 ±12 µm, 2 µm 간격 | 같음 | `fine_half_um`, `fine_step_um` |
| settle 0.1 s (거친), 0.2 s (고운) | `sweep_pair` | `settle_coarse_s`, `settle_fine_s` |
| 블록 6 × 6 | `BLOCKS` | `blocks_per_side` |
| 드롭아웃 판정 ±2 % (스윕 중앙값 밝기 대비) | 타일 루프 | `dropout_frac` |
| 자동 노출: p99.9 를 천장의 50 % 로. 배율은 0.25–4 로 자르고 0.7–1.4 면 멈춤. 최대 6 회, 노출 1–2000 ms, 시작 30 ms | 자동 노출 루프, `open_core(args.exposure or 30.0, 0)` | `auto_exposure_*` |
| XY 이동 후 0.2 s 대기 | `goto_xy` | `xy_settle_s` |
| XY 박스 여유 1000 µm | `box` | 가드 상수 |
| 주차 상한 3200 µm | `axis.park_at(min(z_img, 3200.0))` | Z 창 상한 (가드) |
| 렌즈 라벨 `1-Plan Apo LmbdD20 4x`, 레지스트리 키 `"4x"` | `OBJECTIVE_4X`, `FocusAxis(core, "4x", ...)` | 렌즈 표 (`info().objectives`, 레지스트리 키는 가드) |

**2) plan** (모션 없이 계산 가능. `planned` 이벤트로 낸다)

- 입력: `sample.json` 의 `hole.centre_um`, `hole.diameter_mm`, `stage_camera_calibration.um_per_px`
  (없으면 1.625), `info().sensor` (또는 ROI).
- `half = diameter_mm × 500 + margin_um`, `fov = min(w, h) × um_per_px`, `pitch = fov × (1 − overlap)`,
  `n = max(1, ceil((2·half − fov) / pitch) + 1)`. 타일 중심은 `(i − (n−1)/2) × pitch` 격자이고, 행마다
  방향을 뒤집는 serpentine 순서다 (`grid()`).
- XY 박스: `centre ± (half + 1000)`.
- 첫 스윕: `axis.plan(z_guess, first_half_um, 10).describe()`. 원본 dry-run 은 여기까지만 보여 준다.
  엔진의 plan 은 이후 타일의 스윕 폭(±50 @6, 고운 ±12 @2)과 "실패하면 첫 타일 폭으로 한 번 넓힘" 규칙도 적는다.
- 검산 값 (WP-C 테스트 벡터로 쓸 수 있다): 9/30 의 `diameter_mm 6.1438`, margin 500, overlap 0.15,
  2400 px × 1.6252 µm 에서 fov 3901, pitch 3315, n = 2 (2 × 2 타일). 9/30 기록과 일치한다.

**3) preflight**

| 확인 | 원본 | 엔진 제안 |
|---|---|---|
| `sample.json` 존재 | 런처 `sample_id(required=True)` 만 본다. 스크립트는 없으면 예외 | `preflight_failed("no sample.json")` |
| `hole` 피팅 있음 | 없음. `hole` 이 null 이면 `TypeError` | `preflight_failed("hole not fitted: run edge_trace")` |
| 피팅이 이번 세션 것인가 | 런처 대화상자의 질문뿐 ("Hole traced in brightfield this session?") | `sample.json` 에는 피팅 시각이 없고 `updated` 만 있다. T-002 `sample.py` 에 `hole.fitted_at` 을 두고, 엔진 시작 이후가 아니면 `confirm_required` (운영 규칙: 세션마다 재추적) |
| 렌즈 라벨 = 4x | 있음. 단 그리드를 출력한 **뒤**에 확인한다 | 맨 앞으로 옮긴다. 아니면 `preflight_failed` |
| PFS | run 의 `require_pfs_quiet(disable=True)` 가 끈다 | 읽어서 `reading` 으로 남긴다. 끄는 것은 run 7번 |
| 현재 Z | `z_guess` 계산에만 쓴다 | 현재 Z 가 창 밖이면 (9/30 시작 시 62.9 µm) 첫 이동이 2960 µm 까지 약 2.9 mm 상승한다. `confirm_required` 로 묻는 것을 제안. 원본은 묻지 않는다 |
| 카메라 비트 깊이 | run 중 `getImageBitDepth()` | preflight 에서 읽어 천장을 정한다. 4095 (12-bit) 여야 9/30 설정과 같다 |
| 다른 작업 실행 중 | 런처 `hardware_users()` | 엔진 단일 소유 (0.3) |

**4) run**

| # | 스크립트 호출 | 엔진 호출 | 비고 |
|---|---|---|---|
| 1 | `open_core(args.exposure or 30.0, 0)` | `set_exposure(exposure_ms or 30)`, `set_roi(0)`, `info()` | |
| 2 | `getProperty("Nosepiece", "Label")` | `nosepiece()` | preflight 로 옮긴다 |
| 3 | `FocusAxis(core, "4x", allow_motion=True, dry_run=)` | 가드 Z 축 생성. 원본은 `registry_key` 대신 `"4x"` 고정 | |
| 4 | `axis.position_um()` | 같음 | `z_guess` 계산 |
| 5 | dry-run 이면 `axis.plan(...).describe()` 출력 후 종료 | plan 단계에서 끝. `finished(dry_run=True)` | 기록 폴더를 만들지 않는다 |
| 6 | `out.mkdir`, `getImageBitDepth()` | 기록 폴더 생성, `info().ceiling_adu` | |
| 7 | `axis.require_pfs_quiet(disable=True)` | 같음 | **추론**: PFS 서보를 끄고 꺼졌는지 읽는다 |
| 8 | `aura_on(core, line, pct)` = DiaLamp State 0 → `{LINE}_Intensity` (퍼밀) → `{LINE} 1` → Aura State 1, 각각 readback | `scope.aura_line_on(line, percent)` | 원본은 `verified=False` 여도 계속한다. 엔진은 멈춘다 (`GuardError`) |
| 9 | `goto_xy(x0, y0)`: 박스 검사 → `setXYPosition` → `waitForDevice` → 0.2 s → `getXYPosition` | `xy.goto(x, y)` (박스, 큰 이동, readback 비교) | 원본은 XY readback 을 명령값과 비교하지 않는다 |
| 10 | 자동 노출이면 `axis.move_to(min(z_guess, 3200), allow_ascent_um=max(0, z_guess − z) + 0.5)` 후 최대 6 회 `snap` → p99.9 → `setExposure` | `axis.move_to(...)`, `snap()`, `set_exposure()` | 원본은 p99.9 를 출력만 한다 |
| 11 | 타일마다 `goto_xy(x, y)` | 9번과 같음 | `progress(tile k/n)` |
| 12 | `sweep_pair`: `axis.sweep(axis.plan(z_ref, hr, step), grab, score=, settle_s=0.1)`. `coarse.peak_interior` 이면 `axis.sweep(axis.plan(coarse.peak_z_um, 12, 2), grab, score=, settle_s=0.2)` | 같음 | `grab` = `snap()`. 원본은 미리보기용으로 `axis.position_um()`, `vollath4` 도 부른다. 엔진은 점마다 `frame_ready` + `progress` |
| 13 | `best_z_um(coarse, fine)` | 같음 | 결과 `(zf, why)` |
| 14 | 첫 타일이 아니고 `zf` 가 None 이면 첫 타일 폭(±160 @10)으로 `sweep_pair` 한 번 더 | 같음 | |
| 15 | 드롭아웃 필터: 거친+고운 점의 `diagnostics.mean` 중앙값에서 2 % 넘게 벗어난 점을 뺀다. 빠진 점이 있고 고운 스윕이 있으면 남은 고운 점(3개 이상)으로 `parabola_peak` 다시 | 순수 함수 (`focus/`) | `why` 가 `"fine pass without light-dropout frames at [...]"` 로 바뀐다 |
| 16 | 블록 36 개마다 `parabola_peak(zs, blocks[b])` | 순수 함수 | `block_z_um` |
| 17 | `axis.park_at(min(zf or z_ref, 3200))` | 같음 | 착지 z 가 `z_image_um` |
| 18 | `grab()` → `tile_rXcY.npy` 저장, `scan.json` 저장 | `snap()`, 기록 | 타일마다 저장한다. 중단돼도 앞 타일은 남는다 |
| 19 | `zf` 가 있으면 `z_ref = zf`, `first = False` | 같음 | 실패한 타일은 다음 타일의 기준을 바꾸지 않는다 |
| 20 | `rec["finished"]` | `finished` | |

`score` 함수 (거친·고운 공통): `sharp = vollath4`, `blocks = block_scores` (6×6 vollath4), `mean`, `p999`,
`saturated_frac = mean(frame ≥ ceiling)`. 판정 지표는 Vollath F4 하나다.

**5) abort / finally**

| 순서 | 원본 `finally` | 엔진 제안 |
|---|---|---|
| 1 | `lights` 가 비어 있지 않으면 `aura_off()` (Aura State 0 만) | 가드 종료 경로의 `all_off()` (Aura + DiaLamp, readback) |
| 2 | `rec["z_end_um"] = axis.position_um()` | `positions()` 전부를 종료 상태로 |
| 3 | `scan.json` 저장 | `summary.json` + `aborted` 또는 `finished` |
| Z | 그 자리에 둔다 (후퇴하지 않음) | 같게 둔다. 4x 는 작동 거리 20 mm 라서 후퇴가 안전에 필요하지 않다 |
| XY | 그 자리 | 그 자리 |

원본의 빈틈 (이식할 때 고칠 것):
- `aura_on()` 이 네 번째 쓰기 전에 예외로 멈추면 `lights` 가 빈 리스트라서 `finally` 가 소등하지 않는다.
  엔진은 조명을 켜기 **전에** `operation()` 범위에 들어가야 한다.
- `aura_on` 의 `verified=False` 를 확인하지 않는다.
- XY readback 을 명령값과 비교하지 않는다. 9/30 에 사람이 실행 중 재물대를 움직인 일이 있다 (기록 4절 3항).
  허용 오차는 10절 질문.
- Ctrl+C 가 `axis.sweep` 의 이동 중에 오면 어떻게 되는지 모른다. **추론**: `KeyboardInterrupt` 가 그대로
  올라와 `finally` 로 간다. 엔진은 이동과 이동 사이에서만 abort 를 확인한다.

**6) 기록**

지금: `<sample>/scan4x_<stamp>/`

| 파일 | 내용 |
|---|---|
| `scan.json` | `sample, started, header (=info), objective, um_per_px, fov_um, pitch_um, grid_n, hole, margin_um, coordinates, camera_ceiling_adu, light (aura_on 기록 4개), exposure_ms, tiles[], finished, light_off, z_end_um` |
| `scan.json` 의 `tiles[]` | `name, row, col, x_cmd_um, y_cmd_um, x_um, y_um, z_focus_um, focus_note, z_image_um, block_z_um[36], blocks_per_side, dropout_z_um[], curve[{z, sharp, mean, sat}], frame_mean, frame_max, seconds` |
| `tile_r{r}c{c}.npy` | 초점 위치에서 찍은 uint16 프레임 |
| `launcher_scan4x_<stamp>.log` (샘플 폴더) | stdout |

`scripts/plot_scan.py` 가 읽는 필드: `um_per_px`, `fov_um`, `hole`, `tiles[].{x_um, y_um, name, z_focus_um,
blocks_per_side, block_z_um}`, 그리고 상위 폴더 `sample.json` 의 `stage_camera_calibration`.

엔진 기록으로의 대응:

| 지금 | 엔진 |
|---|---|
| `scan.json` 상위 필드 | `summary.json` 에 같은 이름으로. plot_scan 호환을 위해 이름을 바꾸지 않는다 |
| `tiles[]` | `summary.json` 의 `tiles[]` (같은 필드). 타일마다 `reading` 이벤트로도 낸다 |
| `curve[]` | `log.jsonl` 의 `progress` 이벤트 (점마다 명령 `z_um`, `z_readback_um`, `score`, `diagnostics`). `summary.json` 에는 지금처럼 요약 곡선 |
| `light`, `light_off` | `property_set` 이벤트와 종료 상태 |
| `header` | `started` 이벤트의 시작 상태 (`info()` + `positions()`) |
| `.npy` | 같은 폴더에 그대로 |

결정이 필요한 것 (매니저에게):
- 폴더 이름: 지금은 `scan4x_<stamp>` 이고, T-002 규칙대로면 `scan_4x_<stamp>` 가 된다. 런처 `plot()` 과
  `plot_scan.py` 는 `scan4x_*/scan.json` 을 찾는다. 제안: 작업 이름은 `scan_4x` 로 두되 폴더는 `scan4x_<stamp>`
  를 유지하고, `summary.json` 과 같은 내용의 `scan.json` 을 함께 쓴다. 이식이 끝나면 하나로 합친다.
- `z_focus_um` 은 고전 지표(Vollath)와 엔코더 readback 에서 나온 값이다. 모델 값이 아니므로
  `grade: model` 표시 대상이 아니다.

**7) 확인 지점** (`confirm_required`)

| 지점 | 원본 | 엔진 |
|---|---|---|
| 시작 전 | 런처 대화상자: "moves the XY stage and ZDrive and switches on Aura GREEN 1 %", "Nosepiece on 4x?", "Hole traced in brightfield this session?" | `confirm_required("start scan_4x", plan)` 한 번. 렌즈 확인은 preflight 가 대신한다 |
| 피팅이 이번 세션 것이 아님 | 위 대화상자의 질문 | `confirm_required("hole fit is from <time>; re-trace?")` |
| 첫 이동이 Z 창 밖에서 들어옴 | 없음 | `confirm_required("ZDrive <z> -> <z_guess>")` (제안) |
| 실행 중 | 없음 | 없음 |

**8) 9/30 기록 대응**: Step 2.

| 사례 | 무엇이 있었나 | 명세에 반영된 곳 |
|---|---|---|
| 첫 시도 `scan4x_20260930-194928/` 가 빈 폴더 | 자동 노출이 16-bit 천장을 목표로 해 12-bit 카메라에서 멈췄다. `getImageBitDepth` 로 고쳤다 | preflight 의 비트 깊이 읽기. mock 테스트는 12-bit 로 |
| 광 드롭아웃 | 두 번째 실행 r1c1 의 고운 스윕에서 −23 % 프레임 두 장이 2.7 배 선명하게 읽혀 피크가 됐다. 3053.99 → 3051.2 µm | run 15번 드롭아웃 필터, `dropout_z_um` |
| 사람이 실행 중 재물대를 움직임 | 기록 사이 XY 가 바뀌었다 | XY readback 비교 (5항 빈틈), 시작 위치는 `started` 이벤트 |
| 노출 | 자동으로 994 ms (p99.9 2043 ADU) | 자동 노출 고정값 |
| 첫 타일 기준 Z | 명시야로 맞춘 현재 Z 3012 µm 근처에서 ±160 | `z_guess` 규칙 |
| 반복성 | 실행 간 0.4–3.4 µm (4x 피사계 심도 약 14 µm) | mock 테스트 허용 오차의 근거 |

결과 (serpentine 순서): r0c0 (6368.3, −1086.0), r0c1 (9683.7, −1086.0), r1c1 (9683.6, 2229.2),
r1c0 (6368.3, 2229.5). 초점 평면: 구멍 중심 3048.7 µm, 기울기 x −1.66, y −3.62 µm/mm.

## 4. `objective_change` (F5 포함)

원본: `scripts/change_objective.py` (R-05 에서 삭제; 이력에 있음). 9/30 에는 `--to 5 --park` → 사람이 오일 → `--return-only` 로 썼다.
런처에는 버튼이 없다 ("The objective change and 100x steps stay manual"). 엔진에서는 PLAN 2절 F5 의
7단계 순서로 다시 짠다. 아래는 원본을 먼저 적고, 그다음 F5 엔진 작업을 적는다.

### 4.1 원본이 하는 일

**입력 인자**

| 명령행 | 기본값 | 뜻 |
|---|---|---|
| `--to N` | None | 목표 Nosepiece **State** (0 = 4x, 5 = 100x Oil) |
| `--status` | False | 읽기만 (2절) |
| `--park` | False | 회전 후 Z 를 0 에 둔다 (오일을 바르기 위해) |
| `--return-only` | False | 회전 없이 Z 0 → 2800 |

고정값: `RETRACT_Z_UM = 0.0`, `RETURN_Z_UM = 2800.0`, 코어는 `open_core(30.0, 0)`.
`--status` 가 있으면 다른 인자보다 먼저 처리되고 끝난다. `--to` 가 없고 `--return-only` 도 없으면 읽기만 한다.

**원본 호출 순서** (`--to N`, `--park` 유무)

| # | 스크립트 호출 | 엔진 호출 | 비고 |
|---|---|---|---|
| 1 | `state(core)` | `nosepiece()`, `positions()`, `pfs()` | 시작 상태 `s0` |
| 2 | `s0.nosepiece_state == N` 이면 "already on that objective" 후 종료 | preflight | 아무것도 움직이지 않는다 |
| 3 | `FocusAxis(core, registry_key(s0.label), allow_motion=True)` | 가드 Z 축 (현재 렌즈 키) | |
| 4 | `axis.require_pfs_quiet(disable=True)` | 같음 | |
| 5 | `axis.move_to(0.0)` | `axis.park_at(0.0)` | 후퇴. 가드의 `move_to` 는 창 (2800–3200) 밖 목표를 거부하고, 창 아래는 하강만 하는 `park_at` 이 간다 |
| 6 | `state(core)` → `pfs_in_range` 가 `"in range"` 이면 거부하고 종료 | `pfs()` | Z 는 0 에 남는다 |
| 7 | `setProperty("Nosepiece", "State", N)`, `waitForDevice("Nosepiece")` | `rotate_nosepiece(backend, axis, N)` | soft-matter-agents 에서는 거부되는 호출 (`NAMED_REFUSALS` 에 Nosepiece) |
| 8 | `state(core)` → State 가 N 이 아니면 종료 ("ZDrive left retracted") | `rotate_nosepiece` 가 거부 (`GuardError`) | |
| 9 | `--park` 이면 종료 | | Z 는 0 |
| 10 | `FocusAxis(core, registry_key(s2.label), allow_motion=True)` | 가드 Z 축 (새 렌즈 키) | |
| 11 | `axis.move_to(2800.0, allow_ascent_um=2800.5)` | 같음 | **한 번에 2800 µm 상승.** F5 7단계는 이것을 단계 접근으로 바꾼다 |
| 12 | `state(core)`, `getPixelSizeUm()` 출력 | `nosepiece()`, `info().pixel_um` | |

`--return-only`: `FocusAxis(현재 렌즈)` → `require_pfs_quiet(disable=True)` → Z 가 1.0 µm 넘으면 거부 →
`axis.move_to(2800, allow_ascent_um=2800 − z + 0.5)` → `state`. 렌즈, PFS, 오일 확인을 다시 하지 않는다.

원본이 하지 않는 것: XY 이동 (9/30 에는 회전 전에 XY 를 구멍 중심으로 따로 옮겼다), 조명, 기록 파일, 오일 확인.

### 4.2 엔진 작업 `objective_change` (F5 7단계)

**1) 입력 인자**

| 엔진 인자 | 기본값 | 비고 |
|---|---|---|
| `target_state` | (필수) | Nosepiece State. UI 는 Label 로 고르고 State 로 보낸다 |
| `escape_dy_um` | +15000 µm | 작업 인자가 아니라 가드 상수 `guards.ESCAPE_DY_UM`. **+Y, 15 mm 로 정해졌다** (사용자, PLAN v1.3: 15–20 mm 중 짧은 쪽). "unmeasured provisional" 이고 기록에도 그렇게 남는다. 이동 전에 재물대 Y 한계를 읽어 넘으면 거부한다 (`step_out_target`) |
| `escape` | True | False 면 3·6 단계를 건너뛴다 (건조 렌즈끼리 바꿀 때) |
| `approach_target_um` | 2800 | 7단계 단계 접근의 목표. 원본 `RETURN_Z_UM` |
| `approach_step_um` | 미정 | 7단계 한 걸음. 10절 질문 |
| `park_only` | False | 원본 `--park`. 5단계 뒤 멈춘다 (6·7 을 나중에 따로) |

**2) plan** (보여 줄 것)

- 시작 상태: 현재 렌즈, XY, Z, PFS.
- 순서와 각 단계의 목표값: Z → 0, Y → `y + ESCAPE_DY_UM` (+15 mm), Nosepiece → `target_state`, 수동 로딩, XY → 시작 XY,
  Z → `approach_target_um` 까지 `approach_step_um` 걸음.
- 새 렌즈의 액침 종류 (렌즈 표: 4x 건조, 100x Oil 오일, 40x WI 물) 와 작동 거리.

**3) preflight**

| 확인 | 결과 |
|---|---|
| `target_state` 가 현재 State 와 같다 | `preflight_failed("already on that objective")` (원본 2번) |
| 목표 렌즈가 렌즈 표에 있다 (`info().objectives` 의 state 와 `free_wd_um`, 레지스트리 키) | 없거나 `free_wd_um` 이 None 이면 `preflight_failed`. **40x WI 는 작동 거리 값이 없어 거부한다** (PLAN 10절, soft-matter-agents 과제 026 5절) |
| `escape=True` | 이탈 거리는 `ESCAPE_DY_UM` (+Y 15 mm, 임시). 이탈 위치는 아래 줄의 Y 한계 검사를 지나야 한다 |
| 이탈 위치가 재물대 한계 안이다 | 한계는 `info().stage_limits.y_um` (F2 구성 파일에서 채움). None 이면 `preflight_failed` |
| 실행 중인 다른 작업, 조명 | 다른 작업이 없어야 한다. 조명은 켜져 있으면 1단계에서 끈다 (`all_off()`) |
| 이전 `objective_change` 가 "복귀 대기" 로 끝났다 | 4.2 의 5항 참고. 새 회전 대신 복귀(6·7)를 먼저 하라고 `preflight_failed` |

**4) run**

| F5 단계 | 엔진 호출 | 가드 / 확인 | 원본 대응 |
|---|---|---|---|
| 1 현재 XY, Z, 렌즈 기록 | `positions()`, `nosepiece()`, `pfs()` | `started` 시작 상태에 `return_xy`, `z_before`, `objective_before` 저장 | 원본 1번 |
| (1b) 소등 | `all_off()` | readback | 원본에 없음 |
| 2 PFS off → Z 후퇴 → PFS Out of Range 확인 | `axis.require_pfs_quiet(disable=True)`, `axis.park_at(0.0)`, `positions()`, `pfs()` | Z readback 이 후퇴값 ± 허용 오차인지 확인. `pfs().out_of_range` 가 아니면 (In Range 또는 읽기 실패) 중단 (Z 는 0) | 원본 4–6번 |
| 3 Y 이탈 | `xy.goto(*step_out_target(backend, x, y)[:2])` (= `y + ESCAPE_DY_UM`) | **큰 XY 이동 가드: Z 후퇴가 readback 으로 확인될 때만.** 이동 직전에 Z 를 다시 읽는다. XY readback 비교 | 원본에 없음 |
| 4 렌즈 회전, 읽기 확인 | `rotate_nosepiece(backend, axis, target_state)` → label, 새 렌즈로 `FocusAxis` 다시 만들기, `info()` | `rotate_nosepiece` 가 Z 후퇴, PFS off·Out of Range, readback 을 확인한다. label 이 목표 렌즈와 다르면 중단. Z 는 0, XY 는 이탈 위치에 둔다 | 원본 7–8, 10번 |
| 5 사용자: 액침액 로딩 → "로딩 완료" | `scope.ask("load_immersion", "Loading done", immersion=<oil\|water>)` 로 기다린다 (종류 `manual_step` 은 T-011) | 기다리는 동안 이 작업은 Z, XY, Nosepiece 에 명령을 보내지 않는다. 응답을 `manual_step` 기록으로 남긴다 | 원본 `--park` 후 사람이 오일 |
| (5b) `park_only` 면 여기서 `finished(state="awaiting_return")` | | | 원본 `--park` 종료 |
| 6 XY 를 1 의 위치로 복귀 | `xy.goto(*return_xy)` (가드가 Z 를 다시 읽는다) | 3단계와 같은 가드. XY readback 비교 | 원본에 없음 |
| 7 Z 단계 접근 | `axis.approach(approach_target_um, approach_step_um)` | 2800 까지 한 번, 그다음 렌즈의 `approach_step_um` 이하 걸음마다 readback 과 상승 확인. 목표로 점프하지 않는다 | 원본 11번 (`move_to(2800)` 한 번) 을 대체 |
| 끝 | `nosepiece()`, `positions()`, `info().pixel_um` | | 원본 12번 |

- 7단계의 목표는 "목적지가 아니라 목표" 다 (soft-matter-agents 과제 026 2절 6번). 접근은 후퇴 위치에서 시작하고
  걸음마다 비교가 살아 있어야 한다. 무엇과 비교하는지는 지금은 Z 창 상한과 렌즈별 상한이다. F3 의 커버슬립 두께와
  샘플 두께가 정해지면 그 값이 들어간다 (PLAN F3).
- **추론**: 원본 11번 `move_to(2800, allow_ascent_um=2800.5)` 는 FocusAxis 가 이 상승을 한 번의 명령으로 보낸다고
  보인다. 2800 µm 는 100x 초점(약 2989)보다 약 190 µm 아래라 9/30 에는 문제가 없었다. 단계 접근은 이 여유가
  없는 렌즈(작동 거리가 짧은 렌즈, 동초점 오차가 큰 경우)를 위한 것이다.
- 2800 µm 는 Z 창 하한이다. 0 → 2800 의 접근 경로는 창 밖이다. 가드는 "후퇴 상태에서 시작한 `approach`" 를
  창 밖 이동의 허용 경로로 둔다 (T-002 의 렌즈 교체 예외와 같은 자리).

**5) abort / finally**

| 중단 시점 | Z | XY | 남기는 상태 |
|---|---|---|---|
| 1–2 사이 | 그 자리 (올리지 않는다) | 그 자리 | `aborted` |
| 2 후퇴 뒤, 3 전 | 후퇴 | 그 자리 | `aborted` |
| 3–5 (이탈, 회전, 로딩 대기) | 후퇴 | 이탈 위치 | `aborted(state="awaiting_return", return_xy=...)` |
| 6 복귀 중 | 후퇴 | 멈춘 곳 | `awaiting_return` |
| 7 접근 중 | 멈춘 곳. **어떤 중단도 Z 를 올리지 않는다** | 시작 XY | `aborted` |

- 모든 경로에서 `all_off()` (켜진 것이 없어도 readback 확인).
- `awaiting_return` 은 샘플 기록에 남겨서, 다음에 엔진이 시작할 때 UI 가 "Return to sample position" 을 보여 줄 수
  있게 한다. 이 상태에서 다른 모션 작업은 preflight 에서 막는다.

**6) 기록**

| 지금 | 엔진 |
|---|---|
| stdout 의 `state` JSON 줄 (`nosepiece_state, nosepiece_label, z_um, pfs_enabled, pfs_locked, pfs_in_range`) 과 안내 문구. 파일 없음 | `<sample>/objective_change_<stamp>/`: `log.jsonl` (단계마다 `progress(step=1..7)`, `property_set`, `position`), `summary.json`: 시작 상태, 단계별 readback, `manual_step: {step: load_immersion, immersion, confirmed_at, by: user}`, 끝 상태, `state` (`done` / `awaiting_return` / `aborted`) |
| `sample.json` 의 `objectives_used` 는 라이브 뷰가 갱신 | 4단계 성공 시 엔진이 갱신 |

**7) 확인 지점**

| 지점 | `confirm_required` |
|---|---|
| 시작 전 | `"rotate <label_now> -> <label_target>: retract Z, move Y <dy>, rotate"` + plan. 9/30 에는 사람이 채팅으로 회전을 명시 승인했다 |
| 5단계 | `manual_step: load_immersion` ("Loading done" 버튼). 이 응답이 6·7 단계 시작의 승인이기도 하다 |
| 건조 렌즈로 바꿀 때 (`escape=False`) | 5단계 대신 `"objective rotated; continue to approach Z?"` (제안). 100x 에서 4x 로 갈 때 오일을 닦을지는 사용자 결정 |

**8) 9/30 기록 대응**: Step 3.

| 사례 | 무엇이 있었나 | 반영 |
|---|---|---|
| 회전 전 XY | 구멍 중심 (8026, 572) 으로 먼저 옮김 (`xy_before_um [8025.7, 571.4]`) | 1단계 `return_xy` |
| 순서 | PFS off → Z 0 → PFS Out of Range 확인 → Nosepiece 5 → park → 오일 → Z 2800 | 2, 4, 5, 7단계 |
| 결과 | `6-Plan Apo LmbdD0.13 100x Oil`, Z 2800.0 | 4단계 readback |
| 오일 부족 | 회전 뒤 첫 100x 곡선에 3005 µm 근처 가짜 상승. 오일을 더 바르자 깨끗한 피크 (7절) | 오일을 다시 바르려면 이 작업의 2·3·5·6·7 단계를 다시 해야 한다. "re-load immersion" 을 `target_state = 현재` 로 허용하는 변형을 제안 |
| 연구실 기록 | 2026-09-07 에 잘못된 중심으로 고 NA 렌즈가 커버슬립에 닿을 뻔했다 (`focus_100x.py` 머리말) | 7단계 단계 접근, 7절의 천장 |

게이트 (F2): Nosepiece 읽기·쓰기, ZDrive, PFS 읽기, XYStage (`escape=True` 일 때), 렌즈 표에 목표 렌즈의 작동 거리.

## 5. `hardware_scan` (F2)

원본 없음 (새 작업). 근거: `mm_grab.open_core` 의 `info`, `mm_grab.positions`, `mm_grab.PiezoReader.read`,
`change_objective.state`, soft-matter-agents `devices/micromanager.py` 의 `load_configuration` 과 `preflight`.
**탐지만 한다. 아무것도 움직이거나 켜지 않는다.**

**1) 입력 인자**

| 엔진 인자 | 기본값 | 비고 |
|---|---|---|
| `include_properties` | True | 장치별 속성 전체를 읽을지. 끄면 장치 목록과 핵심 값만 |
| `piezo_port` | `"COM4"` | `""` 이면 피에조를 열지 않는다 (live_focus `--piezo` 와 같은 약속) |
| `out` | 기본 기록 위치 | `hardware_profile.json` 을 쓸 곳. 샘플 폴더가 아니다 (장비 단위) |

**2) plan**: 읽을 목록만 보여 준다. "Reads devices, properties, objectives, camera, positions, PFS, lights, piezo.
Nothing moves or turns on."

**3) preflight**

| 확인 | 결과 |
|---|---|
| 다른 작업 실행 중 | 막는다. 탐지는 다른 작업과 같이 돌지 않는다 |
| 백엔드가 열려 있다 | 엔진 시작 시 연 것. config 로드는 Startup 프리셋을 적용하므로 (0.3), 그 사실을 기록에 남긴다 |
| 피에조 포트 | NanoBench 프로그램이 포트를 잡고 있으면 `PiezoReader` 가 `OSError`. 실패는 막지 않고 `piezo.error` 로 남긴다 |

**4) run** (전부 읽기)

| # | 읽는 것 | 엔진 호출 | 원본 근거 |
|---|---|---|---|
| 1 | config 경로, sha256, 로드 중 변경 여부, AutoShutter readback | `info()` + `config_record()` (T-015) | soft-matter-agents `load_configuration` 반환값 |
| 2 | 로드된 장치 목록, 장치별 종류·라이브러리·설명 | `describe_devices(include_properties)` (T-015) → `getLoadedDevices`, `getDeviceType`, `getDeviceLibrary`, `getDeviceDescription` | 없음. T-015 가 백엔드에 추가 |
| 3 | 장치별 속성: 값, 읽기 전용 여부, 허용 값, 한계, 읽기 성공 여부 | 같은 메서드 → `getDevicePropertyNames`, `getProperty`, `isPropertyReadOnly`, `getAllowedPropertyValues`, `getPropertyLowerLimit/UpperLimit` | 없음 |
| 4 | 대물렌즈 목록: State, Label, 픽셀 크기 | `nosepiece()`, `info().objectives` (state, label, pixel_um) + `nosepiece_labels()` (T-015) → `getStateLabels("Nosepiece")` | `change_objective.state`, `open_core` 의 `pixel_um` |
| 5 | 카메라: 이름, 센서, ROI, 비트 깊이, 천장, PixelType | `info()` | `open_core`, `getImageBitDepth` |
| 6 | 위치: XY, Z | `positions()` | `mm_grab.positions` |
| 7 | PFS: enabled, locked, in range | `pfs()` | `change_objective.state` |
| 8 | 조명 상태: Aura State 와 라인, DiaLamp State | `light_state()`, 라인은 `read_property("Aura", ...)` | 없음 |
| 9 | 피에조: 연결 여부, x/y/z µm | `piezo_read(port)` (T-015) → `PiezoReader(port).read()` 후 `close()` | `mm_grab.PiezoReader`. `read()` 는 쓰지 않는다. 보안 수준 변경은 `move_z` 에서만 일어나므로 탐지에서는 생기지 않는다 |
| 10 | 렌즈 표와 대조: 레지스트리 키, 작동 거리, 액침 | 순수 함수 | 렌즈 표는 탐지가 아니라 사람이 넣은 값 (10절 Q8) |
| 11 | 게이트 판정 | `gates.py` (WP-G) | PLAN F2.2 |

- "읽기 확인 가능 여부" 는 탐지 단계에서는 **읽기가 되는지** 까지만 안다. 쓰기 후 readback 이 맞는지는 쓰지 않고는
  모른다. 그래서 장치마다 `read_back: true/false` 와 `write_verified: null` (아직 시험 안 함) 을 따로 둔다.
  soft-matter-agents `preflight` 의 `read_back`, `automatable` 필드와 이름을 맞춘다.

**5) abort / finally**: 되돌릴 것이 없다. 피에조 세션을 열었으면 `close()` (보안 수준을 바꾼 적이 없으므로 그대로 닫힘).
`all_off()` 는 부르지 않는다 (읽기만 하는 작업이 조명을 바꾸지 않는다). 다만 읽은 조명 상태가 켜짐이면 `log` 경고.

**6) 기록**

`hardware_profile.json` (가칭, PLAN F2.1) 제안 필드:

| 필드 | 내용 |
|---|---|
| `detected_at`, `backend` (`mock` / `mm-demo` / `mm-real`), `host` | |
| `config` | `path, sha256, changed_during_load, autoshutter_verified, startup_preset_applied` |
| `devices[]` | `label, type, library, description, read_back, write_verified, properties{name: {value, read_only, allowed, limits, read_ok}}` |
| `objectives[]` | `state, label, pixel_um, registry_key, working_distance_um, immersion` (뒤의 셋은 렌즈 표에서) |
| `camera` | `name, sensor, roi, bit_depth, ceiling_adu, pixel_type` |
| `positions`, `pfs`, `lights` | 탐지 시점 값 |
| `piezo` | `port, connected, x_um, y_um, z_um, error` |
| `human_confirmed{}` | 사람이 확인하는 항목. 예: DiaLamp 세기 (스탠드에서 608), CondenserTurret, 40x WI 보정 링. 탐지가 아니라 UI 입력 |
| `gates{}` | 작업별 켜짐/꺼짐과 꺼진 이유 |

엔진 기록: `hardware_scan_<stamp>/log.jsonl` (읽기마다 `reading`), `summary.json` = 위 프로필. 최신 프로필의 위치는
T-002/WP-G 가 정한다.

게이트 표 초안 (WP-G 입력):

| 작업 | 필요한 장치와 조건 |
|---|---|
| `status`, `lights_off` | 카메라 없이도. Aura, DiaLamp 읽기 |
| `edge_trace` | 카메라, XYStage 읽기·쓰기, DiaLamp, 4x 렌즈, 이 렌즈의 stage-camera 보정이 가능한 영상 |
| `scan_4x` | 위 + ZDrive, PFS 읽기, Aura 라인, 카메라 비트 깊이, 샘플의 `hole` |
| `sample_map` | `scan_4x` 와 같음 (조명은 DiaLamp) |
| `objective_change` | Nosepiece 읽기·쓰기, ZDrive, PFS 읽기, XYStage (`escape=True`), 목표 렌즈의 작동 거리 |
| `focus_100x` | 100x Oil 이 Nosepiece 에 있음, ZDrive, PFS, Aura, 이번 세션의 `load_immersion` 기록 |

**7) 확인 지점**: 없음. `human_confirmed` 항목은 확인 대화상자가 아니라 입력 양식이다.

**8) 9/30 기록 대응**: 3절 "Settings reference" 표 (MM config, 카메라 12-bit 천장 4095, 픽셀 크기 4x 1.625 /
100x 0.065, Z 창, DiaLamp 608, CondenserTurret `3-`, LightPath `4-L100`, PFS off, 피에조 읽기 전용 z 9.94 µm) 가
이 프로필의 첫 예다. 관련 실패: 12-bit 를 16-bit 로 가정한 자동 노출 (3절 8항) 은 프로필의 `bit_depth` 로 막는다.

## 6. `sample_map` (F4)

원본 없음 (새 작업). `edge_trace` (8절) 와 `scan_4x` (3절) 를 재사용하고, 모자이크는 `scripts/plot_scan.py` 의
조립 방식을 쓴다. PLAN F4: 투과광(DiaLamp) 권장.

F4 는 작업 하나가 아니라 셋으로 나눈다. 스캔만 모션이 길고, flag 는 모션이 없고, 클릭 이동은 짧다.

| 이름 | 하는 일 | 모션 |
|---|---|---|
| `sample_map` | 투과광 4x 타일 스캔, 모자이크, 입자 후보 | XY, Z |
| `map_flag` | 맵 위 지점에 flag (F4.4) | 없음 (기록만) |
| `goto_xy` | 맵 클릭 위치로 이동 (F4.3) | XY (필요하면 Z 후퇴 먼저) |

### 6.1 `sample_map`

**1) 입력 인자**: `scan_4x` 인자 (3절 1항) 에서 조명만 바뀐다.

| 엔진 인자 | 기본값 | 비고 |
|---|---|---|
| `sample_id`, `margin_um`, `overlap`, `z_guess_um`, `first_half_um`, `tile_half_um`, `dry_run` | `scan_4x` 와 같음 | |
| `light` | `"bf"` | `"bf"` = DiaLamp (Aura State 0, DiaLamp State 1). `"aura"` 면 `scan_4x` 와 같음 |
| `exposure_ms` | 12 | 9/30 명시야 4x 값. 자동 노출을 쓰면 천장의 50 % 목표는 명시야에서 너무 밝을 수 있다 (10절 질문) |
| `focus` | `"per_tile"` | `"per_tile"`: 타일마다 스윕 (`scan_4x` 와 같음). `"plane"`: 최근 `scan_4x` 의 초점 평면을 쓰고 스윕하지 않음 |
| `candidates` | True | 입자 후보 검출 |

**2) plan**: `scan_4x` 의 plan 과 같다 (격자, 박스, 스윕). `focus="plane"` 이면 타일마다 평면에서 계산한 Z 를 보여 준다.

**3) preflight**: `scan_4x` 의 preflight 전부 (렌즈 4x, `hole`, 피팅이 이번 세션 것인지, 비트 깊이, 현재 Z).
추가: `focus="plane"` 이면 같은 샘플의 `scan4x_*/scan.json` 이 있어야 한다.

**4) run**

| # | 엔진 호출 | 원본 근거 |
|---|---|---|
| 1 | `operation()` 범위 진입 → `axis.require_pfs_quiet(disable=True)` | `scan_4x` 7번 |
| 2 | `light="bf"`: `aura_off()`, `scope.lamp_on()` (readback). `"aura"`: `scope.aura_line_on()` | `live_focus --set Aura State 0 --set DiaLamp State 1`, `scan_4x` 8번 |
| 3 | 타일 루프: `scan_4x` 의 9–19번과 같다 (XY 박스 가드, 스윕, `best_z_um`, 드롭아웃 필터, 블록 z, `park_at`, 타일 저장) | `scan_4x` |
| 4 | 모자이크: 타일을 8×8 비닝, stage-camera 보정 `M_px_per_um` 의 부호로 좌우·상하 뒤집기, 타일 중심 `x_um, y_um` 에 배치 | `plot_scan.py` 의 `mosaic` 조립 (`flip_lr = M[0,0] > 0`, `rows_up = M[1,1] < 0`) |
| 5 | 입자 후보: 고전 이미지 처리로 점 찾기 → 픽셀 → stage 좌표 (`stage + inv(M) @ (centre − p)`) | 9/30 기록 Step 1 의 좌표 변환. 검출 방법은 WP-E (T-003) 와 정한다 |
| 6 | `finished`. `operation()` 범위가 `all_off()` | |

- 9/30 의 입자는 약 6.7 µm (FWHM) 이고 4x 픽셀은 1.625 µm 라서 한 입자가 4 픽셀 남짓이다. 명시야 4x 에서
  보이는지는 확인되지 않았다 (10절 질문). 후보는 "후보" 로만 기록하고, 사람이 확인한 것과 구분한다 (PLAN F4).
- 명시야 Vollath 스윕이 4x 에서 초점을 잡는지도 확인되지 않았다. 9/30 의 4x 스캔은 Aura GREEN 1 % 에서 했다.
  그래서 `focus="plane"` 선택지를 둔다.

**5) abort / finally**: `scan_4x` 와 같다. Z, XY 는 그 자리. `operation()` 범위가 DiaLamp 와 Aura 를 끈다.
`live_focus.py` 처럼 DiaLamp 를 켠 채 남기지 않는다.

**6) 기록**

| 파일 | 내용 |
|---|---|
| `<sample>/sample_map_<stamp>/` | `log.jsonl`, `summary.json` (= `scan_4x` 의 `scan.json` 필드 + `light`, `focus`), 타일 `.npy` |
| 같은 폴더 `mosaic.npy` + `mosaic.json` | 비닝한 모자이크와 범위 (`x0, x1, y0, y1, um_per_px, bin`). UI 가 그리는 데 쓴다 |
| `<sample>/map.json` (기존) 또는 새 `features.json` | 입자 후보 `{x_um, y_um, source: "classical_candidate", score, map_id}`. 사람이 확인하면 `source: "person_confirmed"` 로 새 항목을 추가한다 (덮어쓰지 않는다) |

모델 값은 없다. DINO 를 후보 점수에 쓰게 되면 그 숫자는 `grade: model` 로 표시한다 (PLAN 6절 3항).

**7) 확인 지점**: `scan_4x` 와 같다 (시작 전 한 번, 피팅 시각, 창 밖 첫 이동).

**8) 9/30 기록 대응**: Step 1 (명시야 노출 12 ms, 10 ms 에서 중앙값 2766 ADU, 30 ms 이상 포화), Step 2
(격자, 모자이크, `plot_scan.py`). 모자이크의 좌우 반전: 영상이 재물대에 대해 거울상이다 (Step 1 의 보정 결과).

### 6.2 `map_flag`

- 인자: `sample_id`, `x_um`, `y_um`, `name`, `note`. 엔진이 채우는 것: `t`, 현재 렌즈, 현재 Z.
- 모션 없음, preflight 는 샘플 폴더가 있는지뿐. 기록: `<sample>/flags.json` (또는 `features.json` 의 `kind: flag`).
  PLAN F4.4 의 필드: 이름, 메모, 시각, 대물렌즈, 좌표.
- 삭제는 지우지 않고 `retired_at` 을 붙인다 (기록은 남는다).

### 6.3 `goto_xy` (클릭 이동, F4.3)

**1) 인자**: `x_um`, `y_um`, `sample_id`. 선택: `retract_first` (기본 자동).

**2) plan**: 현재 XY → 목표 XY 거리, 큰 이동인지, Z 후퇴가 필요한지, 후퇴할 Z 값.

**3) preflight**

| 확인 | 결과 |
|---|---|
| 목표가 샘플의 맵 범위 + 여유 안 | 밖이면 거부 (PLAN F4 "스캔 박스 밖이면 거부"). 범위는 최근 `sample_map` 또는 `scan_4x` 의 박스 |
| 다른 작업 실행 중 | 막는다 |
| `awaiting_return` 상태 (4.2 5항) | 막는다 |

**4) run**

| # | 엔진 호출 | 가드 |
|---|---|---|
| 1 | `positions()` | |
| 2 | 큰 이동이면: Z 가 후퇴 상태가 아니면 `axis.park_at(Z_SAFE_UM)` 로 먼저 후퇴하고 `positions()` 로 확인 | **큰 XY 이동은 Z 후퇴가 readback 으로 확인될 때만** |
| 3 | `xy.goto(x, y)` | XY 박스, XY readback 비교 |
| 4 | Z 는 후퇴 상태로 둔다. 다시 올리는 것은 사용자가 고르는 다음 작업 (`scan_4x` 의 한 타일 스윕, `objective_change` 의 접근, `focus_100x`) | 목표로 점프하지 않는다 |

정해진 임시 값 (`guards.py`, unmeasured provisional, 0.1 참고):
- "큰 이동" 의 문턱: `OBJECTIVE_LIMITS[key].long_xy_um`. 작동 거리 10 mm 이상 (4x) 은 10 mm, 그 밖은 min(시야, 1 mm)
  (100x Oil 156 µm). 렌즈를 읽지 못하면 가장 엄격한 값 (모든 이동에 후퇴). `edge_trace` 의 한 걸음 (최대 200 µm) 과
  보정 이동 (200 µm) 은 4x 문턱보다 작다.
- `z_safe`: `Z_SAFE_UM` = 0 µm, 모든 렌즈. 렌즈별 값은 현미경 PC 측정 뒤 (Q20).

**5) abort**: 이동 사이에서 멈춘다. Z 는 올리지 않는다. 조명은 이 작업이 켜지 않는다.

**6) 기록**: `<sample>/goto_xy_<stamp>/summary.json` (시작, 후퇴 여부, 목표, 착지 readback). 짧은 작업이므로
T-002 가 허용하면 샘플 단위 `moves.jsonl` 한 줄로 대신해도 된다.

**7) 확인 지점**: Z 후퇴가 필요한 이동이면 `confirm_required("retract Z <z> -> <z_safe>, then move to (x, y)")`.
후퇴가 필요 없는 작은 이동은 확인 없이 (클릭 자체가 명령).

**8) 9/30 기록 대응**: 원본에는 클릭 이동이 없다. 9/30 에 사람이 재물대를 손으로 움직인 사례 (기록 4절 3항) 와,
`find_particle_z` 가 사람의 이동 중에 readback 가드로 멈춘 사례 (3037/3036) 가 같은 문제다. 이동 후 readback 비교가 필요하다.

## 7. `focus_100x`

원본: `scripts/focus_100x.py` (R-05 에서 삭제; 이력에 있음). 런처에 버튼 없음 (수동 단계).

**1) 입력 인자**

| 명령행 | 기본값 | 엔진 인자 | 비고 |
|---|---|---|---|
| `--centre` | 2930.0 µm | `centre_um` | 스윕 중심. **4x 초점에 맞추지 않는다** (아래 8항) |
| `--half` | 40.0 µm | `half_um` | 거친 스윕 반폭 |
| `--step` | 2.0 µm | `step_um` | |
| `--fine-half` | 3.0 µm | `fine_half_um` | |
| `--fine-step` | 0.2 µm | `fine_step_um` | |
| `--exposure` | 30.0 ms | `exposure_ms` | **엔진 기본값은 20 ms** (`focus_100x.DEFAULT_EXPOSURE_MS`, unmeasured provisional: 9/30 실행 한 번, 포화 없음) |
| `--aura LINE PERCENT` | GREEN 1 | `aura_line`, `aura_percent` | |
| `--metric` | `peak` | `metric` (`peak` / `vollath`) | `peak`: 4×4 비닝 최댓값 − 중앙값. 성긴 입자 시야용 |
| `--out` | `D:\AutoFocus\samples\20260930_1849_1` (고정 샘플!) | `sample_id` | 원본 기본값은 9/30 샘플 폴더다. 엔진은 현재 샘플 |

고정값: 렌즈 라벨 `6-Plan Apo LmbdD0.13 100x Oil`, 레지스트리 키 `"100x-Oil"`, settle 0.1 s (거친) / 0.15 s (고운).

**2) plan**

- 거친 스윕 `axis.plan(centre, half, step)`, 고운 스윕은 거친 피크 ± `fine_half` @ `fine_step`.
- 천장: 머리말은 `min(3200, centre + 0.4 × 130 µm)` 라고 적는다. **코드에는 이 계산이 없다.** **추론**: FocusAxis 가
  레지스트리 키 `"100x-Oil"` 의 작동 거리로 계산한다. 엔진의 plan 은 이 천장을 숫자로 보여 준다 (10절 Q8, Q15).
- 중심 제안: 같은 샘플의 4x 초점 평면에서 현재 XY 의 Z 를 구하고, 동초점 오프셋 (9/30 측정 약 −60 µm) 을 더한 값.
  측정값에서 나온 제안이지 모델 값이 아니다. 사람이 고친 값으로 실행한다.

**3) preflight**

| 확인 | 원본 | 엔진 |
|---|---|---|
| 렌즈 라벨 = 100x Oil | 있음 (`refusing`) | `preflight_failed` |
| 오일 로딩 | 없음 | 이번 세션에 `objective_change` 의 `load_immersion` 기록이 있어야 한다. 없으면 `confirm_required` |
| `centre_um` 이 4x 초점 근처 | 없음 (머리말 경고만) | 4x 초점 평면 값보다 위면 경고와 `confirm_required` |
| 천장 안 | **추론**: FocusAxis 가 계획 단계에서 거부 | plan 의 천장을 넘는 스윕은 `preflight_failed` |
| 신호 | 없음 | 시작 Z 에서 한 장 찍어 최댓값이 암전 오프셋 (약 102 ADU) 근처면 경고. 9/30 의 30 ms Vollath 실패 사례 |

**4) run**

| # | 스크립트 호출 | 엔진 호출 | 비고 |
|---|---|---|---|
| 1 | `open_core(exposure, 0)` | `set_exposure()`, `info()` | |
| 2 | `getProperty("Nosepiece", "Label")` | `nosepiece()` | preflight |
| 3 | `FocusAxis(core, "100x-Oil", allow_motion=True)` | 가드 Z 축 | |
| 4 | `ceiling = 2 ** getImageBitDepth() − 1` | `info().ceiling_adu` | 포화 판정용 |
| 5 | `axis.require_pfs_quiet(disable=True)` | 같음 | |
| 6 | `aura_on(core, line, pct)` | `scope.aura_line_on(line, pct)` | `operation()` 범위 안에서 |
| 7 | `axis.sweep(axis.plan(centre, half, step), grab, score=, settle_s=0.1)` | 같음 | `score`: `sharp` (peak 또는 vollath), `vollath`, `mean`, `max`, `sat` |
| 8a | 피크가 **위 끝** (`argmax_index == 마지막`): "PEAK AT THE TOP END", `axis.move_to(coarse.points[0].z_um)` (아래 끝으로 내려감), 고운 스윕 없음 | 같은 이동 후 `confirm_required("peak at the top end; extend upward?")` | 원본은 여기서 끝. 사람이 새 중심으로 다시 실행 |
| 8b | 피크가 **아래 끝** (`argmax_index == 0`): "re-centre lower" 출력, 고운 스윕 없음 | `reading(peak_at="low_end")` | 아래로 다시 거는 것은 안전 방향. 확인 없이 제안 |
| 8c | 내부 피크: `axis.sweep(axis.plan(coarse.peak_z_um, fine_half, fine_step), grab, score=, settle_s=0.15)` | 같음 | |
| 9 | `best_z_um(coarse, fine)` | 같음 | |
| 10 | `zf` 가 있으면 `axis.park_at(zf)` | 같음 | |
| 11 | `positions(core)` | `positions()` | |

**5) abort / finally**

| 원본 `finally` | 엔진 |
|---|---|
| `lights` 가 있으면 `aura_off()` | `operation()` 범위의 `all_off()` |
| `focus100x_<stamp>.json` 저장 (중단돼도) | `summary.json` + `aborted` |
| Z 그 자리 | 그 자리. 위 끝 피크면 원본처럼 아래 끝으로 내려간 상태 |

빈틈: `scan_4x` 와 같은 `aura_on` 부분 실패 문제 (3절 5항).

**6) 기록**

| 지금 `focus100x_<stamp>.json` | 엔진 |
|---|---|
| `started, header (=info), coarse [(z_readback, score, mean, max)], fine [...], z_focus_um, why, z_parked_um, position` | `summary.json` 에 같은 필드 + **원본에 없는 실행 인자** (`centre_um, half_um, step_um, exposure_ms, metric, aura`) 와 `sat`. 9/30 yaml 은 노출과 지표를 메모에서 되살려 적어야 했다 |
| 쓰는 곳이 `--out` (기본 9/30 샘플 고정) | 현재 샘플의 `focus100x_<stamp>/` (`scan4x` 와 같은 방식으로 기존 접두 유지) |

**7) 확인 지점**

| 지점 | `confirm_required` |
|---|---|
| 위 끝 피크 후 상향 연장 | `"peak at the top end of <lo>-<hi>; extend upward to <new_hi>?"`. 새 범위는 천장을 넘지 않는다. 운영 규칙 `no_climb_without_ok` |
| 오일 기록 없음 | `"no immersion loading recorded this session; oil applied?"` |
| 중심이 4x 초점보다 위 | `"centre <c> is above the 4x focus <z4>; 100x focus is usually 60-100 um below"` |

**8) 9/30 기록 대응**: Step 4.

| 파일 | 노출 | 범위 | 결과 | 명세 반영 |
|---|---|---|---|---|
| `focus100x_20260930-201702` | 30 ms, vollath | | 암전 오프셋만 (약 102 ADU) → 초점 없음 | preflight 신호 확인, `metric=peak` 기본 |
| `-202011` | 200 ms | 2890–2980 | 위 끝 피크, 오르지 않음 | 8a, 상향 연장 확인 |
| `-202226` | 50 ms | 2965–3005 | 2982.0, 포화, 3005 근처 가짜 상승 (오일) | `sat` 기록, 이중 피크 경고 (아래) |
| `-202507` | 30 ms | 2955–3015 | 2988.45 at (8164.7, 523.4), 오일 추가 후 깨끗한 피크 | |
| `-202813` | 20 ms | 2968–3008 | 2989.42 at (7811.0, 1529.0), 포화 없음, 최대 3435 ADU | 엔진 기본값 20 ms (임시) |

- 이중 피크: 거친 곡선에 떨어진 극대가 두 개면 "check immersion oil" 경고를 낸다 (고전 판정, 모델 아님).
  이 경고가 나면 4.2 의 재로딩 변형으로 이어진다.
- 포화: `sat > 0` 인 점이 있으면 노출을 줄이라는 경고.
- 100x − 4x ≈ −60 µm (연구실 2026-09-07 메모는 약 −100 µm). 기준 시료 재측정은 PLAN 10절.

## 8. `edge_trace`

원본: `scripts/edge_track.py` 의 `EdgeTracker` 와 `scripts/live_focus.py` 의 `t` 키 (`toggle_track`) (R-05 에서 삭제; 이력에 있음).
런처 Step 1 "Start live view" (명시야) 후 창에서 `t`. 오프라인 시뮬레이션은 `scripts/sim_edge_track.py`.

**1) 입력 인자**

| 원본 | 기본값 | 엔진 인자 | 비고 |
|---|---|---|---|
| live_focus `--exposure` | 30 ms (런처 명시야 기본 12) | `exposure_ms` | 9/30: 12 ms |
| live_focus `--hole-diameter` | None | `hole_diameter_mm` | 추적기의 `expect_diameter_um` |
| live_focus `--track-speed` | 100 µm/s | `speed_um_s` | 10–1000 으로 자름. 실행 중 `+`/`-` 로 2 배/절반 |
| live_focus `--set Aura State 0 --set DiaLamp State 1` | (런처가 넣음) | `light="bf"` | |
| live_focus `--sample` | 새 id | `sample_id` | |
| `EdgeTracker(step_um=50, cal_um=200, point_every_um=250, max_radius_um=7000, max_path_um=25000, max_time_s=360, min_radius_um=1000)` | | 같은 이름 | 걸음은 `speed × 0.5 s` 를 20–200 µm 로 자른 값 |
| `min_blob_um = 500`, settle `2 × exposure + 0.08 s` | | 상수 | |

**2) plan**: 시작 XY, 최대 반경 원 (시작점 7 mm), 최대 경로 25 mm, 최대 시간 360 s, 속도와 걸음.
보정 이동 (+x 200 µm 갔다 오기, +y 200 µm 갔다 오기) 을 미리 보여 준다.

**3) preflight**

| 확인 | 원본 | 엔진 |
|---|---|---|
| 데모 모드 | `"edge tracking needs the real stage"` 로 거부 | mock 백엔드는 추적을 지원해야 한다 (M1 mock 우선). `sim_edge_track.py` 가 근거 |
| 렌즈 | 확인 없음 | 4x 권장. 다른 렌즈면 경고 (보정은 렌즈별로 저장된다: `stage_camera_calibration.objective`) |
| 조명 | 런처가 명시야로 켠다 | `light="bf"` 면 run 1번에서 켠다 |
| 이전 경계 | 없음. 9/30 에는 에이전트가 손으로 백업하고 지웠다 | 샘플에 `boundary` 가 있으면 `map_before_rescan_<stamp>.json`, `sample_before_rescan_<stamp>.json` 으로 백업하고 `boundary` 만 비운다 (방문 필드는 남김). `confirm_required` |
| 다른 작업 | 원본: 서보·스윕이 돌면 거부 | 엔진 단일 작업 |

**4) run**

| # | 원본 호출 | 엔진 호출 | 비고 |
|---|---|---|---|
| 1 | `set_and_read` 로 Aura State 0, DiaLamp State 1 | `operation()` 진입 → `aura_off()`, `scope.lamp_on()` | |
| 2 | `startContinuousSequenceAcquisition`, 틱마다 `popNextImageAndMD` → `tracker.feed(img)` | `start_stream(interval_ms)`, `next_frame(timeout_s)`, `stop_stream()` (T-015). 스트림 중에는 `snap()` 을 쓸 수 없다 (`StreamActive`). T-002 의 `snap()` 만으로도 되지만 라이브 뷰와 같이 쓰려면 연속 취득이 필요하다 | `feed` 는 마지막 이동 후 settle 시간이 지난 프레임만 쓴다 |
| 3 | 보정: `getXYPosition` → `setRelativeXYPosition(+200, 0)` → 프레임 → 위상 상관 → `(−200, 0)` → y 도 같게 | `positions()`, `xy.goto_rel(dx_um, dy_um)` | 피크 선명도 < 8 이면 "too little structure" 로 멈춤. `um_per_px / pixel_um` 이 0.7–1.4 밖이면 멈춤 |
| 4 | 추적 루프: `find_edge` → 원 피팅 (`robust_circle`, 지름 고정 `fixed_radius_centre`) → 한 걸음 `setRelativeXYPosition` → `waitForDevice` | 순수 함수 (`edge_track` 의 영상 함수들) + `xy.goto_rel` + `positions()` | XY 만. Z 는 움직이지 않는다 |
| 5 | 멈춤 조건: 시작점에서 7 mm 넘음, 경로·시간 한도, 경계를 잃음 (원이 있으면 약 2 mm 까지 원을 따라 coast, 없으면 3 프레임), 한 바퀴 (경로 > 3 mm 이고 처음 본 점으로 돌아옴), 키 (`t`, `Esc`), 예외 | 같은 조건. 키는 `abort` 명령 | |
| 6 | `edge_point` (250 µm 마다) → `map.mark_boundary(Ti2 + piezo)` | `progress(edge_point)` + 샘플 `boundary` 에 추가 | 좌표는 Ti2 + 피에조 합 |
| 7 | `cal_result` → `sample.calibration = {um_per_px, angle_deg, M_px_per_um, objective}` | 샘플 `stage_camera_calibration` | `scan_4x` 와 `plot_scan` 이 읽는다 |
| 8 | 라이브 뷰가 10 초마다 `Sample.save()` → `hole` 피팅 (`XYMap.circle`) | 끝날 때 `hole` 피팅을 `sample.json` 에 쓰고 `fitted_at` 을 넣는다 | 피팅은 추적기 내부 원이 아니라 경계점 전체의 원 |
| 9 | 실행 중 속도 변경 `set_speed` | 실행 중 인자 변경 명령 `update` (`COMMAND_KINDS`, T-011). 작업은 바꿀 수 있는 인자를 `updatable` 로 선언한다 | T-011 에서 반영됨 |

이동 한계: 한 걸음은 최대 200 µm, 보정은 200 µm. 이동 범위는 "시작점 7 mm 원" 이 지킨다. `goto_xy` 의 "큰 이동"
문턱 (6.3) 보다 작아서 Z 후퇴 조건에 걸리지 않는다.

**5) abort / finally**

| 원본 | 엔진 |
|---|---|
| 추적기 `stop(why)` → `track_stop` 기록. 이동 중이던 걸음은 끝난다 (`waitForDevice`) | 같음 |
| live_focus `finally`: 추적·서보·스윕 정지, 연속 취득 정지, `--aura` 였으면 `aura_off`, `Sample.close()` (저장), 피에조 닫기 | 같음 + **DiaLamp 도 끈다** (`all_off()`). 원본은 `--set DiaLamp State 1` 로 켠 램프를 끄지 않는다 (9/30 알려진 문제 4) |
| XY 는 멈춘 곳 | 같음. Z 는 건드리지 않음 |

**6) 기록**

| 지금 | 엔진 |
|---|---|
| `<sample>/track_<stamp>.jsonl`: 첫 줄 `{header, sample}`, 이후 `track_start, cal, cal_result, move (why, d_um, at_um), edge_point (um, contrast), track_speed, track_stop (why)` 와 라이브 뷰 이벤트 | `<sample>/edge_trace_<stamp>/log.jsonl` 에 같은 이벤트 이름 (`progress` 의 하위 종류). 라이브 뷰 이벤트와 분리 |
| `<sample>/map.json`: `boundary` (합 좌표), `visits` | 그대로 (T-002 `sample.py`) |
| `<sample>/sample.json`: `hole {centre_um, diameter_mm, fit_rms_um, n_points, arc_deg}`, `boundary_limits_um`, `stage_camera_calibration` | 같음 + `hole.fitted_at` (매니저 답변: T-002 에 반영) |
| 백업 `*_before_rescan_<stamp>.json` | preflight 의 자동 백업 |

**7) 확인 지점**

| 지점 | `confirm_required` |
|---|---|
| 이전 경계가 있음 | `"replace the hole fit from <fitted_at>? (backed up)"` |
| 시작 | `"trace the edge: XY moves only, within 7 mm of here"` |
| 끝난 뒤 | 없음. 결과 (지름, rms, 호 각도) 를 보여 준다. 지름이 `hole_diameter_mm` 와 20 % 넘게 다르면 경고 |

**8) 9/30 기록 대응**: Step 1.

| 항목 | 값 |
|---|---|
| 시작 | (8833.4, −2354.1), 속도 400 µm/s, 걸음 200 µm (사람이 올림), 한 바퀴로 멈춤 |
| 결과 | 중심 (8026.0, 571.6), 지름 6.1438 mm, rms 42.5 µm, 49 점, 352° |
| 이전 피팅 | (9361.1, 1272.2), 5.9919 mm. 18:49 → 19:57 사이 1.5 mm 이동 → "세션마다 재추적" 규칙 |
| 보정 | 1.6252 µm/px, 0.117°, `M = [[0.6160, 0.0024], [0.0013, −0.6146]]`. 영상이 재물대에 대해 거울상 |
| 명시야 | DiaLamp 세기 608/2100 (스탠드), 10 ms 중앙값 2766 ADU, 30 ms 이상 포화, 12 ms 사용 |
| 실패 | 창을 닫아도 DiaLamp 가 켜져 있음 (알려진 문제 4) → 5항 |

## 9. 보류와 범위 밖

### 9.1 `find_particle_z` (보류)

`scripts/find_particle_z.py` (R-05 에서 삭제; 이력에 있음): 100x 시야를 나선형 (150 µm 간격) 으로 옮기며 시야마다 1 µm 간격 상향 Z 스택을 찍고,
밝기가 지정한 Z 띠 **안에서** 최대가 되는 점을 입자로 본다. 9/30 기록 4절 1번에 따라 **사용 불가**다.

- 점 판정이 맞지 않는다. 실제 입자는 약 6.7 µm (FWHM) 인데 9/30 실행 때 판정은 2.5 µm 를 가정했다. 지금 코드의
  기본값은 `--particle-um 7.0` 이다. 7 µm 로는 사람이 찾은 입자 (3010.0 µm) 를 저장된 스택에서 찾지만, 합성한
  디포커스 고리 조각 24 개도 통과시킨다.
- 4 번 실행, 46 시야에서 찾은 것이 없다. 마지막 실행은 사람이 재물대를 움직이는 중에 readback 가드 (3037.0 명령 /
  3036.0 읽음) 로 멈췄다.
- 이식하지 않는다. 판정 문제가 풀리면 다시 명세를 쓴다. F4.2 (잃어버린 입자 찾기) 는 우선 `sample_map` 의 후보와
  flag 로 다룬다.

### 9.2 `focus_servo` (범위 밖)

`scripts/focus_servo.py` (R-05 에서 삭제; 이력에 있음) 는 라이브 뷰 안에서 **피에조 Z** (NanoBench, 0–600 µm) 로 미세 초점을 맞추는 세 루틴이다.
`FocusServo` (`f` 키) 는 DINO 헤드의 부호 있는 점수를 0 으로 보내려고 +0.5 µm 탐침으로 기울기와 부호를 재고,
걸음당 최대 0.5 µm, 시작점 ±5 µm 안에서 움직인다. `AutoFocusZ` (`w`) 는 ±1 µm 를 0.25 µm 간격으로 Vollath 피크를 찾고,
끝에 걸리면 ±5 µm 까지 넓히며, 곡선이 평평하면 DINO 점수로 방향을 고른다. `ZSweep` (`W`) 은 ±5 µm 진단 스윕이다.
모두 `PiezoReader.move_z` 로 쓰고, 첫 쓰기 전에 컨트롤러 보안 수준을 User 로 바꿨다가 닫을 때 되돌린다.

판단: **M1–M3 범위 밖이다** (PLAN v0.2 마일스톤으로는 M5 "초점 판정" 의 후보).
- DINO 점수가 모션 명령의 입력이 된다. PLAN 6절 2·3항 (모델은 판정이지 Z 가 아님) 과 맞추려면, 서보 대신 T-003 판정
  (`step_up` / `step_down`) 을 고전 지표가 확인한 뒤에만 한 걸음 가는 방식으로 다시 설계해야 한다.
- 피에조 쓰기는 컨트롤러 보안 수준을 바꾼다. T-002 프로토콜에는 피에조 쓰기가 없다 (읽기는 `positions().piezo_um`). 피에조 쓰기 메서드와 별도 게이트가 먼저 있어야 한다.
- `AutoFocusZ` 의 Vollath 부분만 떼면 고전 미세 초점으로 쓸 수 있다. 이 부분은 `focus_100x` 의 고운 스윕과 겹친다.

### 9.3 이 문서에 없는 것

- 라이브 뷰 (`live`) 자체: 프레임 표시, 점수 패널, 맵 그리기는 T-004 (UI) 와 T-002 (프레임 이벤트) 의 몫이다.
  이 문서는 라이브 뷰 안에서 모션을 내는 `edge_trace` 만 다룬다.
- `b` / `u` 키 (손으로 경계점 찍기, 지우기): 모션이 없는 기록 명령이다. `map_flag` 와 같은 방식으로 다룰 수 있다.

## 10. 현미경 PC 에서 확인할 질문

FocusAxis (`C:\agentic_microscope\hardware\focus.py`) 를 읽거나 벤치에서 한 번 돌려 보면 답이 나온다.

| # | 질문 | 왜 필요한가 |
|---|---|---|
| Q1 | `sweep(plan, ...)` 은 현재 Z 가 계획 시작점보다 위일 때 어떻게 시작점으로 가는가 (내려간 뒤 올라오는가, 거부하는가) | "상향만" 가드와 `allow_ascent_um` 의 정확한 뜻 |
| Q2 | readback 허용 오차는 얼마인가. 9/30 에 3037.0 명령 / 3036.0 읽음에서 멈췄다 | T-002 가드의 기본값 |
| Q3 | `park_at(z)` 의 접근 방향과 반환값 (착지 readback 인가, 명령값인가) | `z_image_um` 의 뜻 |
| Q4 | `best_z_um(coarse, fine)` 의 규칙과 `why` 문자열 목록 | 이식과 mock 테스트의 기대값 |
| Q5 | `require_pfs_quiet(disable=True)` 가 읽고 쓰는 것 | preflight 와 run 의 경계 |
| Q6 | `dry_run=True` 일 때 `move_to`, `sweep` 은 무엇을 하는가 | 엔진 `dry_run` 의 정의 |
| Q7 | 이동 중 `KeyboardInterrupt` 가 오면 ZDrive 는 멈추는가, 명령한 곳까지 가는가 | abort 시 Z 위치 기록 |
| Q8 | 레지스트리 키(`"4x"`, `"100x-Oil"`)별 상한과 작동 거리 값은 어디에 있는가 | 렌즈 표의 소유 (T-002 또는 F2 구성 파일) |
| Q9 | `open_core` 의 Startup 프리셋 (`LappMainBranch1 State 1`) 은 눈에 보이는 변화가 있는가 | 엔진이 config 를 한 번만 로드해도 되는지 |
| Q10 | Aura 마스터 State 0 만으로 모든 라인이 꺼지는가 | `all_off()` 의 정의 |
| Q11 | XYStage readback 의 정상 오차 범위 | XY readback 비교 허용 오차 |
| Q12 | F5 의 Y 이탈 방향과 거리 (지금은 임시로 +Y 15 mm, PLAN v1.3), 재물대 Y 한계, 샘플의 24 mm 변 방향 | `escape_dy_um` 의 값과 preflight 의 한계 검사 (PLAN 10절) |
| Q13 | 100x Oil 을 0 에서 2800 µm 로 올릴 때 안전한 `approach` 걸음과 걸린 시간. 원본처럼 2800 까지는 한 번에 가도 되는가 | `approach_step_um` 기본값 |
| Q14 | `waitForDevice("Nosepiece")` 는 회전이 기계적으로 끝난 뒤 돌아오는가 | 4단계 readback 의 의미 |
| Q15 | 100x 천장 `min(3200, centre + 0.4 × 130)` 은 어디서 계산되는가 (FocusAxis, 레지스트리). 기준이 plan 의 중심인가 | `focus_100x` plan 의 천장 표시와 상향 연장 범위 |
| Q16 | 명시야 4x 에서 타일별 Vollath 스윕이 초점을 잡는가 (9/30 스캔은 Aura 형광에서 했다) | `sample_map` 의 `focus` 기본값 |
| Q17 | 명시야 자동 노출의 목표 (천장의 50 % 는 형광 기준) | `sample_map` 의 `exposure_ms` |
| Q18 | 약 6.7 µm 입자가 명시야 4x (1.625 µm/px) 모자이크에서 보이는가 | 입자 후보 검출의 가능 여부 |
| Q19 | `PiezoReader` 를 여는 것만으로 컨트롤러에 바뀌는 것이 있는가. NanoBench 프로그램과 포트가 겹치면 어떻게 되는가 | `hardware_scan` 이 "아무것도 바꾸지 않음" 을 지키는지 |
| Q20 | 100x Oil 에서 몇 mm 의 XY 이동 전에 Z 후퇴가 필요한가 (오일 막) | `goto_xy` 의 "큰 이동" 문턱과 `z_safe` |
| Q21 | FocusAxis 에 단계 접근과 비슷한 함수가 이미 있는가 | `approach` 를 새로 만들지, 이식할지 |
