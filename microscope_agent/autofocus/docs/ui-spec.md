# UI 화면·동작 명세 (T-004)

작성: AF 실행5 (2026-10-01). 근거 코드는 `main` 6ba1bc1 의 `scripts/launcher.py`,
`scripts/live_focus.py`, `scripts/edge_track.py`, `scripts/focus_servo.py`, `scripts/scan_4x.py`,
`scripts/mm_grab.py` (R-05 에서 삭제; 이력에 있음). 운영 규칙은 `docs/runs/2026-09-30_substrate-scan.md` 2절, 설계 규칙과
기능 요구사항은 `docs/PLAN.md` (1–4절은 v0.2, 3·5·6·7절은 v0.9 기준) 2·5·6·8절. 작업별 세부는
`docs/operations-spec.md` (T-006, main 에 병합됨).

이 문서는 두 가지 용도로 쓴다.

- D1 결정 뒤 UI 구현 (WP-D 와 F1–F5 화면) 의 명세.
- T-002 (실행1) `engine/events.py` 설계의 입력. 4절이 그 입력이다.

D1 은 로컬 웹 앱 (FastAPI 서버 + React 브라우저 화면) 으로 확정됐다 (매니저 전달, PLAN v0.3 예정).
화면 배치는 툴킷과 무관하게 적고, 엔진 대응표 (4절) 에는 전송 방식 (REST / WebSocket) 을 붙인다.
화면 영역 이름은 v0.3 의 `console`, `hardware`, `sample`, `map`, `objective`, `live` 를 쓴다 (1.0).
작업(operation)별 plan / preflight / run / abort 의 세부는 실행4 의 `docs/operations-spec.md` (T-006)
를 따르고, 여기서는 화면이 그 작업을 어떻게 부르고 무엇을 보여 주는지만 적는다.

표기:

- 코드 이름과 UI 문구는 영어 그대로 인용한다. 예: `"Start live view"`.
- 좌표 `sum` = Ti2 XYStage/ZDrive + 피에조, µm (`live_focus.py::sample_xyz`). 피에조 축 부호는
  아직 검증되지 않았다.
- **(제안)** 은 T-002 과제 파일 목록에 없는 명령/이벤트를 이 문서가 새로 제안하는 것이다.

---

## 1. 화면 목록

### 1.0 화면 영역 (v0.3) 과 현재 화면의 대응

각 영역은 `server/api/<영역>.py` 와 `web/src/features/<영역>/` 으로 구현된다 (매니저 전달).
모든 화면에 공통 상태 줄 (조명, 실행 중 작업, 연결 상태, 원격 여부) 이 붙는다.

| 영역 | 담는 것 | 현재 화면에서 오는 것 | 새 기능 |
|---|---|---|---|
| `live` | 라이브 영상, ROI, 초점 판정, 지표 트레이스, 상태 줄, 프레임 저장 | 1.2 (a) (b) (c) (f), 1.3 스캔 미리보기, 1.4 | — |
| `map` | XY 지도, 경계점과 원 피팅, 엣지 추적, 4x 스캔과 결과 | 1.2 (d) (e) 의 지도·hole 줄, 런처 Step 1 의 추적 설정, Step 2 | F4 모자이크, 입자 후보, flag, 클릭 이동 |
| `sample` | 샘플 선택·새로 만들기·폴더, 샘플 기록 요약 | 런처 Sample, 1.2 (e) 의 샘플 줄, `n` | F3 지오메트리, 로딩 확인 |
| `hardware` | 장치 상태 읽기, 조명 켜고 끄기 | 런처 Step 0, `"Lights off"`, Step 1 의 조명 선택 | F2 탐지, 구성 파일, 게이트 |
| `objective` | 렌즈 교체와 100x 초점 | `change_objective.py`, `focus_100x.py` (런처에 없음, 수동 실행) | F5 7단계, 액침액 로딩 |
| `console` | 에이전트 질문과 기록 열람 | 없음 | F1 |

원격 규칙 (매니저 전달): 서버는 127.0.0.1 에만 바인딩한다. 원격 접속은 읽기 전용이고, 움직이거나
기록을 쓰는 명령은 현미경 PC 의 브라우저에서만 받는다. 영역별로 원격일 때 비활성인 항목은 7절에 적는다.
판정은 서버가 요청 출처로 하고, 화면의 비활성 표시는 추가 안내일 뿐이다 (PLAN 6절 2항과 같은 원칙).

### 1.1–1.4 현재 화면

현재 화면은 네 개의 tkinter 창이다. 런처, 라이브 뷰, 4x 스캔 미리보기, 그리고 거의 쓰지 않는
`mm_grab.py` 의 ROI 라이브 창이다. 라이브 뷰는 한 창 안에 여섯 영역을 둔다.
PLAN v0.2 의 새 화면 (F1–F5) 은 1.5 에 목록만 두고 7절에서 명세한다.

### 1.1 런처 (`scripts/launcher.py` (R-05 에서 삭제; 이력에 있음), 창 제목 `"DINO Autofocus"`)

위에서 아래로 따라가는 단계형 창이다. 하드웨어 로직은 없다. 각 작업은 새 콘솔 창에서
`run_logged.py` 로 감싸 실행되고, 출력은 로그 파일에 복사된다.

| 영역 | 보여 주는 것 | 입력 | 갱신 |
|---|---|---|---|
| 머리 | `"DINO Autofocus"`, `"Find the sample, then autofocus-scan it. Work top to bottom."` | — | 고정 |
| Sample | 샘플 ID 콤보박스. `SAMPLES_ROOT` (`D:\AutoFocus\samples`) 의 하위 폴더 이름, 최신순 | 콤보 선택·직접 입력, `"Open folder"`, `"New"` (빈 값 = 라이브 뷰가 시계로 이름을 지음) | 목록은 콤보를 펼칠 때마다 다시 읽음 |
| Step 0 `"Check the microscope"` | `"Read only. The 4x scan needs the 4x objective in place."` | `"Show objective / Z / PFS"` | — |
| Step 1 `"Find the sample: live view + edge trace"` | 조명 라디오, Aura 라인/퍼센트, Exposure, Hole diameter, Trace speed, 키 안내 문구 | 라디오 `"Brightfield (DiaLamp): to find the hole edge"` / `"Aura line"`, 라인 콤보 (`GREEN` 만), `%` (기본 1), Exposure (기본 12 ms), Hole diameter (기본 6 mm), Trace speed (기본 100 µm/s), `"Start live view"` | 조명을 바꾸면 노출 기본값이 12 ms ↔ 500 ms 로 바뀜 (`light_changed`) |
| Step 2 `"Autofocus scan at 4x (Aura GREEN 1 %)"` | Exposure (빈 값 = auto), 안내 문구 | Exposure, 체크 `"Dry run: only print the tile plan"`, `"Start 4x scan"`, `"Show scan result (mosaic + z map)"` | — |
| 기타 | — | `"Lights off (Aura + DiaLamp)"`, `"Try the demo (no hardware)"` | — |
| 상태 줄 | `"Idle."`, `"Checking that the microscope is free ..."`, `"Started <label> (log: <file>)"`, `"Running: <labels>"`, `"Not started."` | — | 1 s 폴링 (`poll`) |

작업 실행 규칙 (`Launcher.run`):

- 하드웨어 작업은 런처가 띄운 다른 하드웨어 작업이 살아 있으면 거부한다.
- 그다음 `hardware_users()` 가 PowerShell 로 프로세스 명령줄을 읽어 현미경 프로그램
  (`HW_MARKERS`: live_focus, scan_4x, Micro-Manager, NIS-Elements 등) 을 찾는다. 찾으면 계속할지 묻는다.
- 로그는 샘플 폴더가 있으면 그 안에, 없으면 `outputs/launcher_logs/` 에
  `launcher_<label>_<stamp>.log` 로 쓴다.
- 중지는 각 콘솔의 Ctrl+C 다. 스크립트 자신의 `finally` 가 소등한다.

### 1.2 라이브 뷰 (`scripts/live_focus.py` (R-05 에서 삭제; 이력에 있음), 창 제목 `"Kinetix_red full sensor -- focus score"`)

가로 세 칸과 아래 상태 줄로 된 한 창이다.

```
+----------------------+------------------------------+----------------------+
| (a) 이미지            | (b) 게이지 | (c) 트레이스 2개 | (d) XY 지도           |
|  전체 프레임 + ROI     |            |                 | (e) 위치·샘플 텍스트   |
+----------------------+------------------------------+----------------------+
| (f) 상태 줄                                                                |
+----------------------------------------------------------------------------+
```

| 영역 | 보여 주는 것 | 갱신 |
|---|---|---|
| (a) 이미지 | 2400 × 2400 전체 프레임을 `--display` (800 px) 이하로 평균 비닝하고 0.5–99.8 백분위로 8-bit 늘림 (`bin_for_display`). 가운데 `--score-roi` (518 px) 주황 사각형 = 지표를 읽는 ROI. 헤드가 있으면 DINO 타일 (224 px) 테두리: 유효 (`p_valid ≥ 0.5`) 는 파란 실선과 `+1.3` 같은 dz 숫자, 무효는 회색 점선과 `?` | 보관되는 프레임마다 (`--fps`, 기본 10 fps) |
| (b) 초점 게이지 (`Gauge`) | `"Focus score"`, `"depths of field"`. −10..+10 DoF 세로 눈금, ±1 DoF 초록 띠, 마커와 sigma 막대, 숫자 (`+1.2`), 메모 (`"box: 3/4 tiles, sign unsure, offset +0.5"`, `"no head loaded (--head)"`, `"no readable sample in view"`, 데모에서 `"demo value, not a measurement"`). 값은 최근 5개 읽기의 중앙값 | 점수 스레드의 읽기가 도착할 때 (비동기, 수십 ms) |
| (c) 트레이스 1 (`Trace`) | `"Sharpness, centre 518 px"`: 주황 ROI 의 Brenner. 자동 스케일, 최소/최대/현재값 글자 | 보관되는 프레임마다. 길이 `--history` (30 s) × fps 점 |
| (c) 트레이스 2 | `"z_sum = ZDrive + piezo z (um)"` | 같음 |
| (d) XY 지도 (`XYMap`) | 제목 `"Sample map (stage um)    b: mark edge   u: undo"`. 방문 필드 사각형 (점수로 색: \|s\| ≤ 1 초록, ≤ 3 파랑, 그 밖 회색), 경계점 (빨간 점), 경계점 3개 이상이면 원 피팅 (8개 이상은 이상치 제거, `robust_circle`) 과 중심 ×, 2개면 선, 현재 시야 (주황 사각형 + 십자), 축척 `"<span> um across   +stage x ←  +y ↓"`. 기본으로 x, y 모두 뒤집어 그림 (조이스틱 방향) | 0.5 s |
| (e) 위치·샘플 텍스트 | Ti2 / piezo / sum 의 x, y, z 표. 샘플 ID와 `"(n: new sample)"`, 대물렌즈 라벨, 시야 µm, 지도 필드 수, 경계 범위, hole 중심·지름·rms·점 수, 현재 위치가 중심에서 몇 µm, 가장자리 안쪽 몇 µm, `"(piezo not read)"`. 키 안내와 진행 상태: `"edge track: <status>"`, 헤드가 있으면 tare offset, `"piezo: <status>"` (서보), `"piezo focus: <status>"` (스윕), 읽기 영역 | 0.5 s |
| (f) 상태 줄 | `" shown 9.8 fps (camera 33.1)   mean 812  max 4095  sat 0.02%   x … y … z … um   REC"` | 보관되는 프레임마다 |
| 콘솔 (stdout) | 키 거부 사유, 시작/중지, 경계점 좌표, tare 결과, 추적기 이벤트 JSON 등 25곳의 `print` | 발생 시 |

진행 상태 문자열은 각 루틴의 `.status` 다. 예: 엣지 추적 `"calibrating"`, `"tracking 400 um/s  path 3.20 mm  …"`,
`"coasting on fitted circle (1/3)"`, `"stopped: <why>"`. 서보 `"probing +0.5 um"`,
`"step 3: score +1.20 -> moving -0.240 um"`. 자동 초점 `"fine scan around 9.94 um"`,
`"peak beyond the scan: extending"`, `"Vollath flat: probing with DINO at -2 / +2 um"`.

화면 밖에서 라이브 뷰가 쓰는 기록 (화면 항목은 아니지만 4절 이벤트의 근거):

| 기록 | 내용 | 주기 |
|---|---|---|
| `track_<stamp>.jsonl` | 머리 (`header`, `sample`), 이후 프레임마다 위치, `sample_um`, score, score_raw, score_offset, sharpness, mean, max, sat_pct. 추적기·서보·스윕 이벤트도 같은 파일 | 보관되는 프레임마다 + 이벤트 |
| `map.json` | `visits` (최근 20000), `boundary` | 경계점 변경 시, 그리고 `sample.json` 저장 때 |
| `sample.json` | hole 피팅, 경계 범위, 방문 필드 수, 사용한 대물렌즈, 스테이지-카메라 보정, 렌즈별 tare offset, config, camera | 10 s, 그리고 tare 와 창 닫기 때 |
| `--record` | `video_<stamp>_uint16_<h>x<w>.raw` (11.5 MB/프레임) + `_meta.jsonl` | 보관되는 프레임마다 |
| `autofocus_*.json`, `zsweep_*.json` | 피에조 자동 초점·스윕 결과 | 루틴이 끝날 때 |

### 1.3 4x 스캔 미리보기 (`scripts/scan_4x.py::Preview` (R-05 에서 삭제; 이력에 있음), 창 제목 `"scan_4x preview"`)

스캔 루프가 직접 갱신하는 창이다. `--no-preview` 로 끈다. 창을 닫으면 미리보기만 사라지고
스캔은 계속된다.

| 영역 | 보여 주는 것 | 갱신 |
|---|---|---|
| 이미지 | 잡은 프레임, 700 px 이하 비닝 + 백분위 늘림 | 스냅마다 |
| 곡선 | `"<tile>: Vollath F4 vs ZDrive (um)"`: 현재 타일의 선명도 대 ZDrive 산점도 | 스냅마다 |
| 글자 줄 | `"<tile>  (k/n)   ZDrive 3048.70 um   Vollath 0.1234   max 2043/4095   exp 994 ms"` | 스냅마다 |

### 1.4 ROI 라이브 창 (`scripts/mm_grab.py::live` (R-05 에서 삭제; 이력에 있음), 창 제목 `"Kinetix_red centre ROI -- 's' saves a frame"`)

518 px 중앙 ROI 와 글자 줄 하나. `s` 가 현재 프레임을 `.npy` 와 위치 `.json` 으로 저장한다.
런처에는 연결되어 있지 않다. 새 UI 에서는 라이브 뷰의 프레임 저장 명령 (2.1, 4.2) 으로 흡수한다.

### 1.5 PLAN v0.2 의 새 화면 (현재 코드 없음)

7절에서 명세한다. UI 셸 (WP-D) 은 이 자리를 내비게이션에 둔다.

| 화면 | 기능 | 작업 묶음 |
|---|---|---|
| 에이전트 콘솔 | 질문 입력, 이전 질문, 시뮬레이션·실험 현황/계획/결과 (F1) | WP-F |
| 하드웨어 | 탐지 결과, `hardware_profile.json`, 게이트별 켜짐/꺼짐과 꺼진 이유 (F2) | WP-G |
| 샘플 로딩 | 지오메트리 입력, 로딩 확인 (F3) | WP-H |
| 샘플 맵 | 투과광 모자이크, 입자 후보, flag, 클릭 이동 (F4). 1.2 (d) 의 확장 | WP-I |
| 배율 전환 | XY 이탈, 렌즈 회전, 액침액 로딩, 복귀 (F5) | WP-J |

### 1.6 갱신 주기 요약

| 주기 | 무엇 | 근거 |
|---|---|---|
| 10 ms | 카메라 버퍼 비우기 (`tick`) | `root.after(10, tick)` |
| 1 / `--fps` (100 ms) | 프레임 보관, 이미지, 트레이스, 상태 줄, track 기록 | 카메라 타임스탬프 `ElapsedTime-ms` 기준. 한 주기 넘게 밀리면 몰아서 내지 않고 다시 맞춤 |
| 비동기 | DINO 읽기와 게이지 | 점수 스레드. 최신 프레임만 넘기고 줄을 세우지 않음 |
| 0.5 s | 위치 읽기, 대물렌즈 라벨과 픽셀 크기 다시 읽기, 지도와 텍스트 다시 그리기 | `pos_t`, `map_t` |
| 1 s | 런처 상태 줄 | `poll` |
| 10 s | `sample.json` 저장 | `save_t` |

새 UI 는 이 주기를 엔진 이벤트 주기로 그대로 옮긴다 (4.1). 화면은 이벤트를 받아 그리기만 한다.

---

## 2. 입력 목록

### 2.1 라이브 뷰 키 바인딩 (`live_focus.py`)

창 전체 (`root.bind`) 에 걸린 키 전부다. 대소문자를 구분한다.

| 키 | 동작 | 조건과 거부 문구 | 하드웨어 | 엔진 명령 (4.2) |
|---|---|---|---|---|
| `b` | 현재 `sum` 위치를 경계점으로 추가하고 `map.json` 저장. 콘솔 `"boundary point N: x … y … um"` | x, y 가 유한할 때만 | 없음 (읽기만) | `start("boundary_mark")` |
| `u` | 마지막 경계점 삭제, 저장 | 경계점이 있을 때 | 없음 | `start("boundary_undo")` |
| `n` | 현재 샘플을 닫고 (`sample.json` 저장) 시계로 새 샘플 ID 를 만듦 | 추적 중이면 거부: `"stop edge tracking before starting a new sample"` | 없음 | `start("sample_new")` |
| `t` | 엣지 추적 시작. 실행 중이면 중지 (`"stopped by key"`) | 데모에서 거부: `"edge tracking needs the real stage"` | **XY 상대 이동** (`setRelativeXYPosition`) | `start("edge_trace", …)` / `abort` |
| `+`, `=`, 숫자패드 `+` | 추적 속도 2배 (상한 1000 µm/s) | — | 실행 중이면 다음 걸음부터 | `update(op_id, {"speed_um_s": v})` (T-011) |
| `-`, 숫자패드 `-` | 추적 속도 ½ (하한 10 µm/s) | — | 같음 | 같음 |
| `Esc` | 엣지 추적, 서보, 스윕을 모두 중지 (`"stopped by Esc"`) | — | 스윕과 자동 초점은 시작 z 로 되돌아감 | `abort` (실행 중인 작업 전부, 4.4 의 2) |
| `f` | 피에조 초점 서보 시작/중지 | 피에조와 헤드가 필요: `"focus servo needs the piezo (COM4) and a focus head (--head)"`. 추적 중이면 `"stop edge tracking first"` | **피에조 Z 이동** | `start("piezo_servo")` / `abort` |
| `w` | 피에조 자동 초점 (Vollath 피크, 멀면 DINO 로 방향) 시작/중지 | 피에조와 헤드가 필요: `"piezo focus needs the piezo (COM4) and a focus head (--head)"`. 추적이나 서보 중이면 `"stop edge tracking / focus servo first"`. 생성 실패는 `"<kind> not started: <exc>"` | **피에조 Z 이동** | `start("piezo_autofocus")` / `abort` |
| `W` | 진단 z 스윕: 현재 위치를 가운데 두고 10 µm, 0.25 µm 간격 | `w` 와 같음 | **피에조 Z 이동** | `start("piezo_zsweep")` / `abort` |
| `z` | tare: 지금이 초점이라고 보고 최근 2 s 의 원 점수 중앙값을 현재 렌즈의 offset 으로 저장 | 읽기가 3개 미만이면 `"tare: fewer than 3 readings in the last 2 s; nothing changed"` | 없음 | `start("score_tare")` |
| `Z` | 현재 렌즈의 tare 삭제 | — | 없음 | `start("score_tare_clear")` |
| `o` | DINO 읽기 영역 전환: 주황 박스 먼저 ↔ 전체 프레임 | — | 없음 | `update(live_op_id, {"read_region": "box_first" or "frame"})` (T-011) |

`w`, `W` 실행 중에는 매 프레임 위치를 확인한다. ZDrive 가 0.3 µm, XY 가 2 µm 넘게 움직이면
`"ZDrive moved by hand (+0.42 um) during the run"` 으로 중지한다. 이 검사는 엔진 가드로 옮긴다 (4.3).

라이브 뷰에는 프레임 저장 키가 없다. 저장은 `--record` (연속 녹화) 와 `mm_grab.py` 의 `s` 뿐이다.
새 UI 에는 `"Save frame"` 을 라이브 뷰 명령으로 둔다: `start("frame_save")` **(제안)**.

창 닫기 (`finally` 순서): 엣지 추적 중지 → 서보·스윕 중지 → 연속 획득 중지 → 점수 스레드 중지
→ `--aura` 를 썼고 `--leave-light-on` 이 아니면 Aura off → 샘플 닫기 → 피에조 닫기 → 녹화 파일 닫기.
**DiaLamp 는 끄지 않는다** (운영 기록 4절 4항). 웹 UI 에서는 탭 닫기가 엔진을 멈추지 않으므로,
소등은 작업별 `finally` 와 서버 종료 경로가 맡는다 (4.2 끝, 5절).

### 2.2 마우스

| 화면 | 현재 | 새 UI |
|---|---|---|
| 런처 | 버튼, 콤보박스, 라디오, 입력칸, 체크박스 (1.1 표) | 같은 항목을 폼으로 |
| 라이브 뷰 | **마우스 바인딩 없음** (`<Button…>` 바인딩이 코드에 없다). 모든 조작은 키 | 2.1 의 각 키에 버튼을 같이 둔다. 키는 단축키로 유지 |
| 4x 스캔 미리보기 | 창 닫기 = 미리보기만 숨김 (`WM_DELETE_WINDOW`) | 스캔 화면 안의 패널로 |
| XY 지도 | 클릭 없음 | 클릭 이동 (F4.3) 과 flag (F4.4) 는 새 기능 (7절) |

### 2.3 라이브 뷰 명령행 인자 (`live_focus.py`)

"새 UI 에서" 열의 `live.x` 는 `start("live", args)` 의 인자 이름 제안이다. 화면 쪽 표시 설정은 "UI" 로 적었다.

| 인자 | 기본값 | 하는 일 | 새 UI 에서 |
|---|---|---|---|
| `--exposure` | 30 ms | 카메라 노출 | `live.exposure_ms` |
| `--fps` | 10 | 표시·기록 보관 주기 | `live.fps` |
| `--display` | 800 px | 표시 비닝 크기 | UI (화면 크기에 맞춤) |
| `--score-roi` | 518 px | 가운데 지표 ROI 와 주황 박스 | `live.roi_px` |
| `--history` | 30 s | 트레이스 길이 | UI |
| `--record` | 꺼짐 | 보관 프레임을 raw + meta 로 녹화 | `live.record` |
| `--out` | `D:\AutoFocus\frames` | 녹화 폴더 | `live.record_dir` (기본: 샘플 폴더 아래) |
| `--demo` | 꺼짐 | Micro-Manager 데모 장치 | 엔진 백엔드 선택 (`mock` / `mm-demo` / `mm-real`). 작업 인자가 아님 |
| `--screenshot` | 없음 | 3 s 뒤 창을 PNG 로 저장하고 종료 (배치 확인용) | UI 테스트 도구 (`tests/ui/`) |
| `--config` | `single_cam_red_noDMD_nocom10.cfg` | Micro-Manager config | 엔진 백엔드 설정 |
| `--set DEVICE PROPERTY VALUE` | 없음, 반복 가능 | 조명 전에 속성 쓰고 읽기 확인. 런처는 조명 선택에 씀 | **UI 에서 없앤다.** 조명은 `light_set` 의미 명령 (4.3). 임의 속성 쓰기는 노출하지 않음 |
| `--aura LINE PERCENT` | 없음 | Aura 라인 켜기 (퍼밀 = 퍼센트 × 10), 닫을 때 끔 | `start("light_set", {"mode": "aura", "line", "percent"})` |
| `--leave-light-on` | 꺼짐 | 닫을 때 Aura 를 끄지 않음 | **없앤다.** 모든 종료 경로에서 소등 (PLAN 6절 5항) |
| `--piezo` | `COM4` | 피에조 읽기 주소 (`''` = 열지 않음) | 엔진 백엔드 설정 |
| `--sample` | 새 ID | 이어서 쓸 샘플 | `start("sample_open", {"sample_id"})` |
| `--samples-root` | `D:\AutoFocus\samples` | 샘플 루트 | 엔진 설정 (`sample.py` 의 루트 인자) |
| `--head` | 없음 | DINO 헤드 경로 (torch, uv 환경) | 엔진 초점 설정 (WP-E). 없으면 판정 패널이 `"no head loaded"` |
| `--tiles` | 4 | 프레임당 DINO 타일 수 | 엔진 초점 설정 |
| `--score-offset` | 없음 | tare 를 덮어쓰는 DoF offset | **없앤다.** tare 는 `score_tare` 명령과 샘플 기록으로만 |
| `--hole-diameter` | 없음 | 예상 구멍 지름 mm (짧은 호에서 원을 안정시킴) | `edge_trace.hole_diameter_mm` (operations-spec 8절). 기본값은 샘플 지오메트리 (F3) 에서 |
| `--track-speed` | 100 µm/s | 추적 시작 속도 (최대 1000) | `edge_trace.speed_um_s` |

런처 인자는 `--screenshot` (1.5 s 뒤 저장하고 종료) 하나뿐이다.

### 2.4 런처 버튼이 만드는 명령

| 버튼 | 지금 실행하는 명령 | 검증 | 엔진 명령 |
|---|---|---|---|
| `"Open folder"` | `explorer <샘플 폴더 또는 루트>` | — | UI 로컬 동작 (엔진 없음) |
| `"New"` | 샘플 칸 비우기 | — | `start("sample_new")` |
| `"Show objective / Z / PFS"` | `change_objective.py --status` | 하드웨어 점유 검사 | `start("status")` |
| `"Start live view"` (명시야) | `live_focus.py --exposure E --hole-diameter D --track-speed S [--sample ID] --set Aura State 0 --set DiaLamp State 1` | 숫자 검사 | `start("light_set", {"mode": "brightfield"})` 다음 `start("live", {"exposure_ms": E})` |
| `"Start live view"` (Aura) | 같은 앞부분 + `--set DiaLamp State 0 --aura LINE PCT` | 숫자 검사 | `start("light_set", {"mode": "aura", "line": LINE, "percent": PCT})` 다음 `start("live", …)` |
| `"Start 4x scan"` | `scan_4x.py --sample ID [--exposure E] [--dry-run]` | `sample.json` 필수, 숫자 검사, dry run 이 아니면 확인 대화상자 | `start("scan_4x", {"sample_id", "exposure_ms": E 또는 null, "dry_run"})` |
| `"Show scan result (mosaic + z map)"` | uv 환경으로 `plot_scan.py <최신 scan4x_*>` | `sample.json` 필수, 끝난 스캔 필요 | 엔진 명령 아님. UI 가 기록을 읽어 그림 (4.1) |
| `"Lights off (Aura + DiaLamp)"` | `lights_off.py` | 하드웨어 점유 검사 | `lights_off` 명령 (events.py 의 명령 종류, `start` 가 아님) |
| `"Try the demo (no hardware)"` | `live_focus.py --demo` | — | 백엔드 `mock` 으로 엔진을 열고 `start("live")` |

런처의 오류·확인 문구 (3절에서 대화상자 지점으로 정리한다):

- `"Sample '<id>' has no sample.json yet.\nTrace the hole edge in brightfield live view first (Step 1)."`
- `"<name>: '<value>' is not a number."`
- `"<label> is still running; close it first."`
- `"Another program seems to be using the microscope: … Start anyway?"`
- `"Start 4x scan"` 확인: 4x 렌즈인지, 이번 세션에 명시야로 구멍을 다시 추적했는지
- `"No finished 4x scan in <id> yet."`

---

## 3. 확인 대화상자 지점

### 3.0 원칙

- **언제 묻는지는 엔진이 정한다.** 하드웨어에 닿는 확인은 모두 엔진의 `confirm_required` 이벤트로
  시작하고, 화면은 그것을 그린 뒤 `confirm(op_id, key, answer)` 를 보낸다. 화면이 스스로 하드웨어
  확인을 만들지 않는다. 화면만의 확인 (3.2) 은 하드웨어에 닿지 않는 것만이다.
- **대화상자는 추가 확인이다.** "yes" 를 받아도 엔진의 가드와 게이트는 그대로 돈다 (PLAN 5절).
  거꾸로, 대화상자를 건너뛰는 설정은 두지 않는다.
- **시간 제한이 없다** (T-011). 기다리는 동안 대화상자 안에 `"Abort"` 를 항상 둔다.
- **다시 접속해도 남는다.** 대기 중인 확인은 `/api/state` 에 있으므로, 탭을 새로 열거나 다시
  연결하면 같은 대화상자가 다시 뜬다.
- **원격 화면과 권한 없는 사용자는 보기만 한다.** 대화상자 대신 `"Waiting for the operator at the
  microscope PC: <prompt>"` 띠를 보여 준다. 응답 버튼은 없다.
- **문구는 엔진 이벤트의 `prompt` 를 그대로 쓴다.** 아래 문구는 `docs/operations-spec.md` 의 7항을
  옮겨 적은 것이고, 정본은 그 문서와 엔진이다. 화면은 `context` 의 값 (plan, 현재값) 을 표로 덧붙인다.
- **응답은 기록된다.** 누가, 언제, 무엇을 골랐는지가 작업 기록과 감사 로그에 남는다 (PLAN 6절 12항).

### 3.1 엔진이 묻는 지점

| # | 작업 | 언제 | 문구 (operations-spec) | 선택지 | 화면 | 지금 |
|---|---|---|---|---|---|---|
| C1 | `scan_4x`, `sample_map` | 시작 전 | `"start scan_4x"` + plan | `"Start"` / `"Cancel"` | 모달. 격자 (n × m 타일), 박스, 움직이는 축 (XY, ZDrive), 켜는 조명, 예상 시간 | 런처 `askokcancel` (2.4) |
| C2 | `scan_4x`, `sample_map` | hole 피팅이 이번 세션 것이 아님 | `"hole fit is from <time>; re-trace?"` | `"Re-trace now"` / `"Cancel"`. 엔진이 `"Use anyway"` 를 선택지로 주면 그때만 셋째 버튼 | 모달. 피팅 시각, 이전 중심과 지름. `"Re-trace now"` 는 `map` 영역의 엣지 추적으로 이동 | 런처 문구의 질문뿐 |
| C3 | `scan_4x`, `sample_map` | 첫 이동이 Z 창 밖에서 들어옴 | `"ZDrive <z> -> <z_guess>"` | `"Move"` / `"Cancel"` | 모달. 현재 Z (엔코더), 목표 Z, 차이 µm | 없음 (9/30 은 62.9 µm 에서 시작) |
| C4 | `edge_trace` | 이전 경계가 있음 | `"replace the hole fit from <fitted_at>? (backed up)"` | `"Replace"` / `"Cancel"` | 모달. 백업 파일 이름 | 없음 (9/30 은 손으로 백업) |
| C5 | `edge_trace` | 시작 | `"trace the edge: XY moves only, within 7 mm of here"` | `"Start"` / `"Cancel"` | 모달. 시작 XY, 속도, 예상 지름 | 없음 (`t` 키가 바로 시작) |
| C6 | `objective_change` | 시작 전 | `"rotate <label_now> -> <label_target>: retract Z, move Y <dy>, rotate"` + plan | `"Rotate"` / `"Cancel"` | 모달. 7단계 계획 (7.5) | 9/30 은 채팅으로 명시 승인 |
| C7 | `objective_change` | 5단계 | `manual_step: load_immersion` | `"Loading done"` | **모달이 아니다.** `objective` 영역의 단계 카드에 큰 버튼. 액침 종류 (oil / water), 누가 언제 눌렀는지 기록. 이 응답이 6·7단계의 승인이다 | 사람이 오일 후 `--return-only` 실행 |
| C8 | `objective_change` | 건조 렌즈로 바꿀 때 (`escape=False`) | `"objective rotated; continue to approach Z?"` | `"Approach"` / `"Stop here"` | 단계 카드 | 없음 |
| C9 | `focus_100x` | 피크가 스윕 위 끝 | `"peak at the top end of <lo>-<hi>; extend upward to <new_hi>?"` | `"Extend upward"` / `"Stop"` | 모달. 스윕 곡선, 새 범위, 천장. 새 범위는 천장을 넘지 않는다 | 스크립트가 멈추고 사람이 다시 실행 (`no_climb_without_ok`) |
| C10 | `focus_100x` | 이번 세션에 액침 로딩 기록 없음 | `"no immersion loading recorded this session; oil applied?"` | `"Oil applied"` / `"Cancel"` | 모달 | 없음 |
| C11 | `focus_100x` | 중심이 4x 초점보다 위 | `"centre <c> is above the 4x focus <z4>; 100x focus is usually 60-100 um below"` | `"Use this centre"` / `"Change centre"` | 모달. 4x 초점, 입력한 중심, 천장 | 스크립트 머리말 경고 |
| C12 | `goto_xy` | Z 후퇴가 필요한 이동 | `"retract Z <z> -> <z_safe>, then move to (x, y)"` | `"Retract and move"` / `"Cancel"` | 모달. 지도 위에 목표 표시 (7.4) | 없음 (새 기능) |
| C13 | 엔진 시작 | 다른 프로그램이 현미경을 쓰는 것 같음 | (제안) `"Another program seems to be using the microscope: <list>"` | `"Continue read-only"` / `"Retry"` | 전체 화면 안내. 이 확인은 작업이 아니라 엔진 단위다 (operations-spec 0.3) | 런처 `askyesno` (`"Start anyway?"`) |

C2 의 기본 선택지에 "그대로 쓰기" 를 넣지 않은 이유: 운영 규칙이 "오래된 hole 피팅을 재추적 없이
다시 쓰지 않는다" 이다 (9/30 에 1.5 mm 이동). 엔진이 예외를 허용하기로 하면 그 선택지는 이벤트의
`options` 로 온다.

### 3.2 화면만의 확인 (하드웨어 없음)

| # | 지점 | 문구 | 선택지 | 비고 |
|---|---|---|---|---|
| U1 | 샘플 전환 (`sample_open`, `sample_new`) | `"Close sample <id> and open <new_id>?"` | `"Switch"` / `"Cancel"` | 엔진 쪽 거부가 먼저다. 엣지 추적 중이거나 `awaiting_return` 이면 `preflight_failed` 로 오고, 대화상자는 뜨지 않는다 |
| U2 | 경계점 되돌리기를 여러 번 (`u`) | 없음 | — | 한 번에 하나만 지운다. 확인 없이 바로. `boundary_reset` (전체) 은 C4 를 거친다 |
| U3 | flag 삭제 | `"Retire flag <name>? It stays in the record."` | `"Retire"` / `"Cancel"` | 지우지 않고 `retired_at` 을 붙인다 (operations-spec 6.2) |
| U4 | 지오메트리를 로딩 확인 뒤에 바꿈 | `"Geometry changed after loading was confirmed. Confirm loading again?"` | `"Change and re-check"` / `"Cancel"` | 커버슬립 두께와 방향은 이후 안전 한계에 들어간다 (PLAN F3). 엔진이 다시 확인 상태를 정한다 |
| U5 | 입력 중인 양식이 있는 화면에서 떠남 | `"Discard unsaved changes?"` | `"Discard"` / `"Stay"` | 지오메트리, 하드웨어 사람 확인 항목 |
| U6 | 질문 보내기 (F1.1) | `"Send this question to <agent> (mock store)?"` | `"Send"` / `"Cancel"` | mock 저장소만. 실제 저장소는 읽기 전용이라 버튼이 꺼져 있다 (7.1) |

로그인, 계정 승인, 장비 제어권 넘기기, Claude 제안 카드의 확인은 이 문서 범위 밖이다
(T-018, T-013, T-014). 이 문서의 화면은 그 결과 (역할, 제어권) 를 비활성 이유로만 쓴다 (7.0).

---

## 4. 엔진 대응표

### 4.0 규약

T-002 과제 파일의 명령/이벤트 목록을 그대로 쓰고, 화면에 필요한데 없는 것만 **(제안)** 으로 더한다.
모든 명령과 이벤트는 JSON 직렬화 가능한 dataclass 다 (PLAN 6절 7항). 공통 필드
`kind`, `t`, `op_id` 는 표에서 생략한다.

**전송** (웹 앱 기준). 공통 경로는 T-009 (서버 골격) 가 정한 이름이다. 영역별 `GET` 경로는 제안이다.

| 종류 | 전송 | 경로 | 원격 |
|---|---|---|---|
| 명령 `start` / `abort` / `confirm` / `lights_off` / `update` | REST `POST`, 응답은 접수 결과 (`op_id` 또는 거부 사유). 결과는 이벤트로 온다 | `POST /api/commands` (T-009) | **거부** (403). 예외 (D13): 이 PC (loopback) 에서는 `abort` 와 `lights_off` 를 로그인 없이 받는다. 원격에서는 로그인한 사용자의 `abort` 만 받고, 원격 `lights_off` 를 포함한 나머지는 거부 (PLAN 6절 12항) |
| 이벤트 (아래 표 전부) | WebSocket, JSON 한 줄씩 | `/ws/events` (T-009) | 허용 (구독만) |
| 라이브 영상 | WebSocket, 바이너리 JPEG (약 800 px, 서버에서 비닝, 카메라마다 목표 10 fps) + 그 프레임의 `frame_id` 와 `camera`. 듀얼캠이면 두 카메라가 같은 소켓으로 오고 화면은 나란히·합쳐서(blue 녹색, red 마젠타)·하나씩 보여 준다 | `/ws/frames` (T-009) | 허용 |
| 현재 상태 한 번에 읽기 (접속 직후, 재접속 후) | REST `GET`, 엔진 `snapshot()` | `/api/state` (T-009) | 허용 |
| 기록 읽기 (샘플 목록, `sample.json`, 스캔 결과, 원본 프레임 한 장) | REST `GET` | `/api/<영역>/...` (제안, `server/api/<영역>.py`) | 허용 |

`/api/state` 는 이벤트를 놓친 화면이 다시 맞추는 자리다. 위치, 렌즈, 조명, 실행 중 작업과 그 마지막
`progress`, 열린 샘플, 대기 중인 `confirm_required` 를 담는다.

**명령**

모든 명령은 `origin` (`"human"` / `"assistant"`) 을 가진다 (T-011 v0.4 조정). 이 문서의 입력은 전부
사람의 입력이므로 `origin="human"` 이고 바로 `confirmed` 로 들어간다. Claude 제안 카드 (`proposed` →
사람 확인) 는 T-013 / T-014 의 화면이다.

| 명령 | 인자 | 쓰임 |
|---|---|---|
| `start` | `op` (작업 이름), `args` (dict) | 모든 작업 시작. 하드웨어를 움직이지 않는 기록 작업 (경계점, tare, 샘플 열기) 도 같은 경로로 보내 기록을 남긴다 (PLAN 6절 4항). 소등은 `start` 가 아니라 별도 명령 종류 `lights_off` 다 (아래 행) |
| `abort` | `op_id` (없으면 실행 중인 전부), `why` | `Esc`, 중지 버튼 |
| `confirm` | `op_id`, `key`, `answer` (`"yes"` / `"no"` 또는 선택값) | `confirm_required` 에 대한 사용자 응답. 종류 `manual_step` (F5 `"Loading done"`) 은 수동 단계 기록으로 남는다 (T-011) |
| `lights_off` | 없음 | **선점**: 실행 중 작업을 abort 하고 전체 소등을 readback 으로 확인한다 (T-002 부록 3, `engine/events.py` 의 `COMMAND_KINDS`). 이 PC 에서는 로그인 없이도 받는다. 원격에서는 거부 (D13, PLAN 6절 12항) |
| `update` (T-011) | `op_id`, `args` (바꿀 인자 dict) | 실행 중 작업의 선언된 인자를 바꿈. 지금 쓰는 곳: 추적 속도 (`+`/`-`), 라이브 읽기 영역 (`o`), 라이브 노출. 선언 밖은 거부 이벤트 |

`update` 가 필요한 이유: 추적 속도는 작업을 멈추지 않고 바꾼다. `abort` + `start` 로 흉내 내면
보정 (`cal_result`) 을 다시 해야 한다.

**작업 이름** (`start.op`)

| 작업 | 하드웨어 | 출처 | 세부 |
|---|---|---|---|
| `status` | 읽기 | `change_objective.py --status` | operations-spec |
| `live` | 카메라 연속 획득, 위치 읽기 | `live_focus.py` 의 획득 루프 | 이 문서 4.1, 4.4 |
| `light_set` **(제안)** | 조명 (의미 단위: 명시야 / Aura 라인 / 끔) | 런처의 `--set`, `--aura` | 4.3 |
| (`lights_off`) | 조명 끔 + readback | `lights_off.py` | operations-spec. 작업 이름이 아니라 명령 종류다 (위 명령 표) |
| `edge_trace` | XY 상대 이동 | `edge_track.py::EdgeTracker` | operations-spec |
| `scan_4x` | XY, Z, 조명 | `scan_4x.py` | operations-spec |
| `objective_change` | Z 후퇴, 렌즈 회전, (F5) XY 이탈/복귀 | `change_objective.py` | operations-spec, 7절 F5 |
| `focus_100x` | Z 스윕, 조명 | `focus_100x.py` | operations-spec |
| `piezo_servo`, `piezo_autofocus`, `piezo_zsweep` **(제안)** | 피에조 Z | `focus_servo.py` (`f`, `w`, `W`) | operations-spec 의 `focus_servo` 판단 (M1–M3 범위 밖일 수 있음) |
| `sample_open`, `sample_new` **(제안)** | 없음 | `--sample`, `n`, 런처 Sample | 4.2 |
| `boundary_mark`, `boundary_undo`, `boundary_reset` **(제안)** | 없음 (위치 읽기) | `b`, `u`, 재추적 전 경계 백업 | 4.2, 5절 |
| `score_tare`, `score_tare_clear` **(제안)** | 없음 | `z`, `Z` | 4.2 |
| `frame_save` **(제안)** | 없음 (최신 프레임) | `mm_grab.py` 의 `s` | 4.2 |

**이벤트** (T-002 목록 + 제안). 필드는 화면이 쓰는 것 기준의 최소 집합이다.

| 이벤트 | 필드 | 화면에서 쓰는 곳 |
|---|---|---|
| `planned` | `op`, `plan` (dict: 타일 격자, 스윕 범위, 천장 등), `dry_run` | 스캔·초점 화면의 계획 미리보기, dry run 결과 |
| `preflight_ok` / `preflight_failed` | `op`, `checks`: `[{name, ok, want, read, why}]` | 시작 버튼 옆 확인 목록. 실패 항목과 이유를 그대로 표시 |
| `started` | `op`, `args`, `start_state` (위치, 렌즈, 조명 readback) | 상태 줄 `"Running: …"`, 진행 패널 |
| `progress` | `op`, `status` (사람용 문자열), `step`, `n_steps` (선택), `data` (작업별 dict) | 진행 문자열 (1.2 의 `.status`), 스캔 타일 k/n, 추적 경로 길이 |
| `frame_ready` | `frame_id`, `shape`, `t_camera_ms`, `t_host`, `exposure_ms`, `pos` (x/y/z, 피에조), `stats` (`mean`, `max`, `sat_pct`, `bit_depth`), `source_op` | 이미지 (a), 상태 줄 (f), 스캔 미리보기. **픽셀은 이벤트에 넣지 않는다** (4.4 의 1) |
| `reading` | `source` (`"classical"` / `"model"`), `metric`, `value`, `grade` (모델이면 `"model"`), `verdict` (5개 어휘), `region` (`"box"` / `"frame"` / `"frame (box empty)"`), `frame_id`, `z_encoder_um`, `tiles` (`[{y0, x0, size, valid, verdict}]`) | 게이지 (b), 트레이스 (c), 타일 테두리 (a). 표시 규칙은 5절 |
| `position` (엔진 주기 이벤트, 기록 폴더 없음, T-002 부록 3) | `x_um`, `y_um`, `z_um`, `piezo_x_um`, `piezo_y_um`, `piezo_z_um`, `sum_um` ([x, y, z]), 읽기 실패 필드 (`xy_error`, `z_error`, `piezo_error`) | 위치 표 (e), 지도 현재 시야 (d), 상태 줄 (f), z 트레이스 |
| `light_changed` | `dialamp` (`"on"` / `"off"` / `"unknown"`), `aura` (`state`, `line`, `intensity_permille`), `verified`, `records` (readback 기록 목록) | 상태 줄의 조명 표시 (5절), 런처 조명 선택의 현재값 |
| `property_set` | `device`, `property`, `wanted`, `read`, `verified` | 로그 패널. `verified=false` 는 경고 배너 |
| `confirm_required` | `key`, `prompt` (영어 문구), `options`, `context` (dict) | 대화상자 (3절) |
| `finished` | `op`, `summary` (dict), `end_state` (조명 readback 필수), `record_dir` | 결과 표시, 상태 줄 `"Idle."` |
| `aborted` | `op`, `why`, `end_state` (F5 를 이탈·회전 뒤 멈추면 `awaiting_return`, T-011) | 진행 패널 `"stopped: <why>"`. `awaiting_return` 이면 공통 상태 줄에 복귀 대기 경고 (7절 F5) |
| `error` | `op`, `message`, `where` | 오류 배너, 로그 |
| `log` | `level`, `text` | 로그 패널 (지금 콘솔 `print` 25곳) |
| `objective` **(제안)** | `label`, `nosepiece_state`, `pixel_um`, `fov_um` | 위치 텍스트 (e), 지도 시야 크기. 렌즈가 손으로 바뀌어도 0.5 s 안에 보이게 |
| `sample_opened` **(제안)** | `sample_id`, `dir`, `created`, `hole` (`fitted_at` 포함, T-002 부록 3), `calibration`, `objectives_used`, `score_offset` (grade `"model"`) | Sample 칸, 위치 텍스트의 샘플 줄, hole 피팅 나이 (5절) |
| `map_changed` **(제안)** | `boundary` (점 목록), `circle` (`cx`, `cy`, `r`, `rms`, `n`, `arc_deg`) 또는 null, `limits`, `visits_added` (새 방문 필드들), `n_visits` | 지도 (d), 위치 텍스트의 hole 줄 |
| `calibration` **(제안)** | `um_per_px`, `angle_deg`, `M_px_per_um`, `objective` | 위치 텍스트, 샘플 기록. 지금은 추적기의 `cal_result` 이벤트 |
| `live_stats` **(제안)** | `shown_fps`, `camera_fps`, `kept`, `seen`, `recording` | 상태 줄 (f). `progress(live).data` 로 넣어도 된다 |

### 4.1 화면 항목 → 이벤트

| 화면 항목 | 받는 이벤트 | 주기 (1.6) | 비고 |
|---|---|---|---|
| (a) 이미지 | `frame_ready` + 미리보기 채널 (4.4 의 1) | fps | 비닝과 늘림은 엔진 쪽 미리보기 생성기에서 한다 (웹이면 JPEG) |
| (a) 주황 ROI | `started(live).args.roi_px` | 시작 시 | — |
| (a) 타일 테두리 | `reading(source="model").tiles` | 비동기 | 숫자 대신 판정 표시 (5절) |
| (b) 게이지 | `reading` | 비동기 | 중앙값 5개는 엔진 (WP-E) 이 계산해 한 `reading` 으로 낸다. UI 는 평균을 내지 않는다 |
| (c) 선명도 트레이스 | `reading(source="classical", metric="brenner")` | fps | 지금은 UI 가 Brenner 를 계산한다. 엔진으로 옮김 |
| (c) z 트레이스 | `position.sum_um[2]` | 0.5 s (지금은 프레임마다 같은 값을 다시 찍음) | 엔코더 값 |
| (d) 지도 | `map_changed`, `position`, `objective` | 변경 시, 0.5 s | 방문 필드 추가는 엔진이 0.5 s 마다 한다 (`XYMap.add` 규칙: 같은 렌즈, 시야 ¼ 안이면 갱신) |
| (e) 위치 표 | `position` | 0.5 s | — |
| (e) 샘플·렌즈·hole 줄 | `sample_opened`, `objective`, `map_changed` | 변경 시 | "중심에서 몇 µm", "가장자리 안쪽 몇 µm" 는 UI 가 `position` 과 `circle` 로 계산해도 된다 (표시 계산이지 안전 판단이 아님) |
| (e) 진행 상태 줄 | `progress(op).status` | 변경 시 | 작업별 한 줄 |
| (f) 상태 줄 | `frame_ready.stats`, `live_stats`, `position`, `light_changed` | fps | 조명 상태를 더한다 (5절) |
| 스캔 미리보기 | `frame_ready(source_op="scan_4x")`, `progress(scan_4x).data` (`tile`, `k`, `n`, `z_um`, `vollath`) | 스냅마다 | 곡선 점은 `progress.data` 에서 |
| 스캔 결과 (모자이크 + z 지도) | `finished(scan_4x).record_dir` → UI 가 `scan.json` 과 타일 `.npy` 를 읽음 | 끝날 때 | `plot_scan.py` 를 대신한다. 읽기 전용 |
| 런처 상태 줄 | `started`, `finished`, `aborted`, `error` | 변경 시 | 1 s 폴링이 필요 없어진다 |
| 로그 패널 (새) | `log`, `property_set`, `error` | 발생 시 | 지금의 콘솔 창들 |

### 4.2 입력 → 명령

모든 행은 REST `POST /api/commands` 이고 원격에서는 거부된다 (4.0 전송 표).
결과는 `/ws/events` 로 온다.

| 입력 | 영역 | 명령 | 인자 | 기대 이벤트 |
|---|---|---|---|---|
| 런처 샘플 선택 / `--sample` | `sample` | `start("sample_open")` | `sample_id` | `sample_opened`, `map_changed` |
| `"New"` / `n` | `sample` | `start("sample_new")` | — | 현재 샘플 `finished`, 새 `sample_opened`. 추적 중이면 `preflight_failed` (`"stop edge tracking before starting a new sample"`) |
| `b` | `map` | `start("boundary_mark")` | 없음 (엔진이 지금 위치를 읽음) | `map_changed`. 위치가 유한하지 않으면 `preflight_failed` |
| `u` | `map` | `start("boundary_undo")` | — | `map_changed` |
| 재추적 (새, 5절) | `map` | `start("boundary_reset")` | — | `map.json`·`sample.json` 백업 (`*_before_rescan_<stamp>.json`) 후 경계만 비움, `map_changed` |
| `"Start live view"` | `hardware` → `live` | `start("light_set")` → `start("live")` | 4.0, 2.3 | `light_changed`, `started`, `frame_ready` … |
| `t` | `map` | `start("edge_trace")` / `abort` | `speed_um_s`, `hole_diameter_mm` (2.3) | `started`, `calibration`, `progress`, `map_changed` (가장자리 점마다), `finished` / `aborted` |
| `+` / `-` | `map` | `update(edge_trace, {"speed_um_s": v})` | 엔진이 10..1000 으로 자른다. 걸음은 속도 × 0.5 s, 20..200 µm | `progress` (속도·걸음 표시) |
| `Esc` | 어느 영역이든 | `abort` | `op_id` 없음 = 실행 중 전부 (라이브 획득은 제외: 4.4 의 2) | `aborted` 들 |
| `f` / `w` / `W` | `live` | `start("piezo_servo" / "piezo_autofocus" / "piezo_zsweep")` / `abort` | 4.0 | `progress`, `reading`, `finished` / `aborted` |
| `z` / `Z` | `live` | `start("score_tare")` / `start("score_tare_clear")` | 엔진이 최근 2 s 의 모델 읽기를 쓴다 | `sample_opened` 갱신과 `log`. 3개 미만이면 `preflight_failed` |
| `o` | `live` | `update(live, {"read_region": …})` | `"box_first"` / `"frame"` | 이후 `reading.region` 이 바뀜 |
| `"Save frame"` (새) | `live` | `start("frame_save")` | — | `finished.summary.path` |
| `"Show objective / Z / PFS"` | `hardware` | `start("status")` | — | `finished.summary` (렌즈, Z, PFS) |
| `"Start 4x scan"` | `map` | `start("scan_4x")` | 2.4 | `planned`, `preflight_*`, `confirm_required` (3절), `progress`, `frame_ready`, `finished` |
| `"Lights off"` | `hardware` (공통 상태 줄에도) | `lights_off` 명령 (events.py 의 명령 종류, `start` 가 아님) | — | `light_changed`, `finished.end_state` |
| 브라우저 탭 닫기 / 서버 종료 | — | 탭 닫기는 명령을 보내지 않는다. 서버 종료가 `abort` (전부) → `lights_off` → 백엔드 닫기 | — | `aborted` …, `light_changed`, 닫기 결과 (5절) |

웹에서는 "창 닫기" 가 엔진 종료가 아니다. 탭을 닫아도 서버의 작업은 계속된다. 그래서 소등을 탭 닫기에
걸지 않고, 서버 종료 경로와 작업별 `finally` 에 건다 (5절). 현미경 PC 의 마지막 로컬 탭이 끊긴 채
움직이는 작업이 돌 때의 처리는 4.4 의 6.

### 4.3 UI 안의 직접 하드웨어 호출 → 엔진으로

현재 UI 프로세스가 직접 부르는 하드웨어 호출 전부다. 새 UI 는 이 중 어느 것도 직접 부르지 않는다
(PLAN 6절 1항).

| 지금 (파일: 위치) | 하는 일 | 옮길 곳 |
|---|---|---|
| `live_focus.py`: `open_core(...)` (`mm_grab.open_core`) | config 로드, AutoShutter off, 노출, ROI | 엔진 열기 (백엔드 `open`). 노출은 `live.exposure_ms` |
| `live_focus.py`: `set_and_read` × `--set` (런처가 `Aura State 0`, `DiaLamp State 1/0` 을 넣음) | 조명을 속성 쓰기로 바꿈 | `start("light_set", {"mode": "brightfield" / "aura" / "off", …})`. 백엔드의 의미 단위 메서드 (`lamp_on/off`, `aura_line_on`, `aura_off`, T-002 부록 2) 를 쓰고 readback 은 `light_changed.records` 로. 임의 `--set` 은 UI 에서 없앤다 |
| `live_focus.py`: `aura_on(core, line, pct)`, 종료 시 `aura_off(core)` | Aura 켜기/끄기 | `light_set` / `lights_off`. 종료 소등은 엔진 가드의 `finally` (T-002 guards) |
| `live_focus.py`: `setCircularBufferMemoryFootprint`, `startContinuousSequenceAcquisition`, `getRemainingImageCount`, `popNextImageAndMD`, `stopSequenceAcquisition` | 연속 획득과 프레임 꺼내기, fps 솎기 | `live` 작업. 솎기 규칙 (카메라 타임스탬프 기준, 밀리면 다시 맞춤) 도 엔진으로 |
| `live_focus.py`: `positions(core, piezo)` 0.5 s | XY, Z, 피에조 읽기 | 엔진이 `position` 이벤트로 낸다 |
| `live_focus.py`: `getProperty("Nosepiece", "Label")`, `getPixelSizeUm()` 0.5 s | 렌즈와 시야 크기 | `objective` 이벤트 **(제안)** |
| `live_focus.py`: `getImageBitDepth()` | 포화 천장 (12-bit = 4095) | `frame_ready.stats.bit_depth`. `sat_pct` 는 엔진이 계산 |
| `live_focus.py`: `PiezoReader(...)` 열기·읽기·닫기 | 피에조 읽기 | 백엔드 |
| `edge_track.py`: `EdgeTracker` 의 `setRelativeXYPosition`, `getXYPosition`, `waitForDevice` (`t` 키) | 보정 이동 (축마다 200 µm) 과 추적 이동 (걸음 ≤ 200 µm) | `edge_trace` 작업. `feed(frame)` 은 엔진 안에서 `live` 프레임을 받는다. `on_point` → `map_changed`, `cal_result` → `calibration`, `set_speed` → `update`. 멈춤 조건 (가장자리 3프레임 소실, 시작점에서 7 mm, 한 바퀴, 경로 25 mm, 360 s) 은 작업 안에 그대로 둔다 |
| `focus_servo.py`: `FocusServo` / `AutoFocusZ` / `ZSweep` 의 `piezo.move_z(target, window)` (`f`, `w`, `W`) | 피에조 Z 이동 (시작점 ±5 µm, 0..600 µm) | `piezo_*` 작업. 창 제한은 가드로. 손으로 움직였는지 검사 (ZDrive 0.3 µm, XY 2 µm) 도 가드로 |
| `live_focus.py`: `FocusScorer` 스레드 (`dino_autofocus.live`) | DINO 읽기 | 엔진 초점 계층 (WP-E `focus/dino.py`) 이 `reading(source="model")` 을 낸다. torch 는 사용 지점에서만 |
| `live_focus.py`: `brenner(box)`, `vollath4(box)` | 고전 지표 | 엔진 초점 계층 (WP-E `focus/classical.py`) 이 `reading(source="classical")` 을 낸다 |
| `live_focus.py`: `raw.write`, `meta.write` (`--record`) | 녹화 | `live.record` 인자. 엔진 기록 |
| `live_focus.py`: `Sample`, `XYMap.add/mark_boundary/save`, `track.write` | 샘플·지도·track 기록 | 엔진 `sample.py` (T-002) 와 위 기록 작업들. 그리기 (`XYMap.draw`) 만 UI 에 남는다 |
| `launcher.py`: `hardware_users()` (PowerShell 프로세스 검사) | 다른 프로그램의 현미경 사용 탐지 | 엔진 preflight (코어 단일 소유 가드 + 외부 프로그램 검사). 결과는 `preflight_failed` 또는 `confirm_required` (3절) |
| `launcher.py`: `subprocess.Popen(CREATE_NEW_CONSOLE)` + Ctrl+C | 작업마다 별도 프로세스, 중지 | 엔진 작업은 같은 프로세스 (D3). 중지는 `abort`. 로그 파일은 엔진 기록 |
| `scan_4x.py`: `Preview` 의 `axis.position_um()`, `core.getExposure()` | 미리보기 글자 | `progress.data`, `frame_ready` |

### 4.4 T-002 / T-011 에 넘긴 질문과 처리 결과

매니저 처리 (2026-10-01, main 2742069 의 T-011 과제 파일):

| # | 질문 | 처리 |
|---|---|---|
| 1 | 프레임 픽셀의 경로 | T-009 의 `/ws/frames` 가 맡는다 (서버 비닝 JPEG, 최신만) |
| 2 | 라이브와 "작업 하나" 규칙 | **채택**: 연속 획득은 엔진 소유 획득 스트림이고 단일 소유에 세지 않는다. `scan_4x`, `focus_100x` 는 시작 때 스트림을 멈추고 끝나면 되돌린다 |
| 3 | 기록 작업 | **채택**: 하드웨어를 움직이지 않는 기록 작업 (`b`, `u`, `z`, 샘플 열기) 은 단일 소유에서 뺀다 |
| 4 | 실행 중 인자 변경 | T-011 의 `update` 명령 |
| 5 | 원격 `abort` | **결정 (D13)**: 원격은 `abort` 만 보낼 수 있다. 그 밖의 원격 명령은 거부 |
| 6 | 로컬 탭이 모두 끊긴 채 도는 작업 | **결정 (D14)**: 연결이 모두 끊기면 10 s 뒤 자동 정지 (PLAN 7절) |

아래는 초안에 쓴 질문 원문이다.

1. **프레임 픽셀의 경로.** 2400 × 2400 uint16 은 11.5 MB 다. `frame_ready` 이벤트는 메타만 담고
   픽셀은 별도 채널로 보낸다. 엔진은 최신 프레임 하나만 들고, 서버의 `/ws/frames` 가 그것을 비닝·늘림
   (`bin_for_display` 와 같은 식) 해 JPEG 로 보낸다. 최신만 남기고 줄을 세우지 않는다 (지금의 점수
   스레드 방식). 느린 브라우저는 프레임을 건너뛴다. 원본이 필요하면 `GET` 으로 한 장 받는다.
   엔진 쪽 계약은 `latest_frame() -> (frame_id, ndarray)` 하나면 된다.
2. **`live` 와 "한 번에 작업 하나" 규칙의 충돌 (T-011).** T-011 은 실행 중 새 작업 명령을 거부한다.
   그런데 지금의 라이브 뷰는 연속 획득을 켠 채로 엣지 추적 (`t`), 서보 (`f`), 스윕 (`w`/`W`),
   경계점 (`b`), tare (`z`) 를 받는다. 추적과 서보는 라이브 프레임을 먹으며 돈다. 그대로 옮기면
   라이브 뷰를 켠 동안 `t` 가 거부된다. 권고: 연속 획득을 작업이 아니라 엔진이 소유한 **획득
   스트림**으로 둔다. 스트림은 단일 소유 규칙에 세지 않고, 작업은 스트림 프레임을 구독한다.
   `scan_4x`, `focus_100x` 처럼 스냅을 직접 하는 작업은 시작할 때 스트림을 멈추고 끝나면 되돌린다.
   `Esc` 와 `abort(op_id 없음)` 은 스트림을 멈추지 않는다. 다른 방법은 `live` 를 바탕 작업으로
   두고 함께 돌 수 있는 작업 표를 엔진이 갖는 것이다. 어느 쪽이든 T-011 에서 정해야 한다.
3. **기록 작업도 `start` 로 보낼지.** 이 문서는 경계점·tare·샘플 열기를 `start` 로 보내 기록을
   남기는 쪽을 제안했다. 다만 2 의 규칙대로면 추적 중 `b`, `z` 가 거부된다. 하드웨어를 움직이지 않는
   기록 작업은 단일 소유 규칙에서 빼거나, 별도 `sample` 명령 하나로 묶기를 권한다.
4. **`update` 의 인자 선언.** 추적 속도 (`speed_um_s`), 라이브 읽기 영역 (`read_region`), 라이브
   노출 (`exposure_ms`) 이 이 문서가 쓰는 이름이다. T-006 의 `edge_trace` 와 이름을 맞춘다.
5. **원격의 `abort`.** 원격은 읽기 전용이다. 다만 원격 화면에서 문제를 본 사람이 멈출 수 있게
   `abort` 만 허용할지 정해야 한다. 멈춤은 움직임을 줄이는 방향이라 허용을 권하지만, 사용자 결정이다.
6. **로컬 화면이 사라진 채 도는 작업.** 탭을 닫아도 작업은 계속된다. 확인이 필요한 작업
   (`confirm_required` 대기) 은 응답이 올 때까지 멈춰 있으면 된다. 엣지 추적처럼 사람이 보며
   쓰는 작업은 로컬 WebSocket 이 모두 끊기면 일정 시간 뒤 스스로 `abort` 할지 정한다. 권고는 "끊긴 뒤
   10 s 에 abort", 시간은 엔진 설정.

---

## 5. 운영 규칙의 화면 강제

규칙을 지키는 것은 엔진이다. 화면은 (1) 규칙이 막은 것을 이유와 함께 보여 주고, (2) 지켜야 할 순서를
눈에 보이게 하고, (3) 규칙을 깨는 입력을 애초에 내지 않는다. 화면이 막는 것은 안내이고, 같은 요청이
API 로 직접 와도 엔진이 막아야 한다.

### 5.1 2026-09-30 운영 규칙

| 규칙 | 근거 | 엔진이 막는 곳 | 화면이 하는 것 |
|---|---|---|---|
| **명시야로 가장자리 추적, 그다음 입자 조명** | 운영 기록 2절 머리 (`brightfield_edge_then_particle_light`) | `edge_trace` 는 run 1번에서 Aura off, DiaLamp on. `scan_4x` 는 자기 조명 (Aura GREEN 1 %) 을 켜고 끝에 끈다 | `map` 영역에 순서를 단계로 보여 준다: `"1  Trace the hole edge (brightfield)"` → `"2  Scan (particle light)"`. 2단계 버튼은 이번 세션 hole 피팅이 있을 때만 켜진다. 꺼져 있으면 `"Trace the hole edge in brightfield first"`. 라이브 뷰가 Aura 로 켜져 있을 때 `t` 를 누르면, 추적이 조명을 명시야로 바꾼다는 것을 C5 대화상자에 적는다 |
| **세션마다 재추적, 오래된 hole 피팅 재사용 금지** | 9/30 에 18:49 → 19:57 사이 구멍이 1.5 mm 이동 | `scan_4x`, `sample_map` preflight 가 `hole.fitted_at` 을 본다 (T-002 부록 3). 이번 세션 전이면 C2 | hole 요약에 피팅 시각과 상태를 늘 붙인다: `"Hole fit 19:57 (this session)"` (보통) 또는 `"Hole fit 18:49, previous session: re-trace before scanning"` (경고색). "이번 세션" 의 기준은 열린 실험 세션의 시작 시각 (F7, T-019) 이고, 세션이 없으면 엔진 시작 시각이다 **(제안: T-019 와 맞출 것)**. 재추적 버튼은 C4 의 백업 안내를 먼저 보여 준다 |
| **100x 스윕을 4x 초점에 중심 두지 않기** | 운영 기록 Step 4. 100x 초점은 4x 초점보다 약 60–100 µm 아래 | `focus_100x` preflight: 중심이 4x 초점보다 위면 C11. 천장 `min(3200, centre + 0.4 × 130)` | `objective` 영역의 100x 초점 양식은 중심 칸을 **빈 칸이 아니라 계산값으로** 채운다: 같은 XY 의 4x 초점 평면 값 − 60 µm (값 옆에 `"lab offset, to be re-measured"`). 4x 초점과 천장을 같은 표에 나란히 보여 준다. 스윕 계획 그림에 천장 선을 그린다 |
| **100x 에서 위로 연장은 사람이 승인** | `no_climb_without_ok` | 피크가 위 끝이면 작업이 멈추고 C9 | 위로 연장하는 버튼은 C9 대화상자 안에만 있다. 양식에서 범위를 직접 올리는 것은 새 실행이고, 그때도 천장과 C11 을 지난다 |
| **렌즈 회전 뒤 액침액 로딩 대기** | `confirm_oil` | `objective_change` 5단계가 `manual_step` 으로 멈추고 Z, XY, Nosepiece 명령을 보내지 않는다 | C7 단계 카드. 대기 중에는 공통 상태 줄에 `"Waiting: load immersion oil"` 을 띄워 다른 영역에서도 보이게 한다 |
| **종료 시 소등, 그리고 그 상태를 보여 주기** | 9/30 알려진 문제 4 (DiaLamp 미소등) | 모든 작업의 종료 컨텍스트가 `all_off()` + readback. `lights_off` 는 선점 | 5.2 |
| **모델 판정은 5개 어휘로만, Z 는 엔코더 값만** | PLAN 6절 3항 | 모델 값은 안전 판단에 들어가지 않는다. 예외: Live 의 Z score 게이지는 DoF 숫자를 보인다 (사용자 결정 2026-10-02, 표시만) | 5.3 |

### 5.2 조명 상태 표시

- **공통 상태 줄에 늘 보인다.** `"DiaLamp OFF · Aura OFF"` 와 마지막 readback 시각. 값은
  `light_changed` 이벤트에서만 온다. 화면이 조명 상태를 추측하지 않는다.
- 상태는 셋이다: 꺼짐 (readback 확인), 켜짐 (라인과 퍼센트, 예: `"Aura GREEN 1 %"`), 모름
  (`"unknown"` 또는 `verified=false`). 모름은 경고색이고 `"Lights not confirmed: DiaLamp read 1, wanted 0"`
  처럼 readback 원문을 보여 준다.
- **`"Lights off"` 버튼은 모든 화면의 상태 줄에 있다.** `lights_off` 는 선점이라 실행 중인 작업이 있어도
  누를 수 있다. 누르면 그 작업이 멈춘다는 것을 버튼 옆 한 줄로 적는다 (`"stops <op>"`). 로컬에서는 viewer 를 포함해 로그인한 누구나 누를 수 있고,
  원격에서는 꺼진다 (D13: 원격은 정지만, 7.0).
- **작업이 끝날 때마다** 결과 패널에 `end_state` 의 조명 readback 을 한 줄로 붙인다.
- **서버 종료.** 웹 탭을 닫는 것은 종료가 아니다 (4.2 끝). 데스크톱 런처 (T-016) 가 서버를 끌 때 마지막
  소등 readback 을 런처 창과 앱 로그에 남긴다. 다음에 서버가 뜨면 첫 화면에 `"Last shutdown: lights off
  confirmed at <t>"` 또는 확인 실패를 보여 준다 **(제안)**.

### 5.3 모델 출력과 Z 의 표시

| 지금 (live_focus.py) | 새 화면 |
|---|---|
| 게이지에 DoF 숫자 (`+1.2`), sigma 막대, −10..+10 눈금 | **사용자 결정 (2026-10-02)으로 9/30 게이지를 그대로 둔다**: Live 영역 Focus 패널의 `"Z score"` (`web/src/app/live/FocusGauge.tsx`). −10..+10 DoF 세로 막대, 0 = 초점, +10 위 (`above`), −10 아래 (`below`), ±1 DoF 초록 띠, 마커, sigma 막대, 숫자 (`+1.2`), 메모. 출처 표시는 늘 붙는다: `"mock truth"` (목 세계의 실제 z, 측정 아님) 또는 `"model"` (`--head` 로 읽은 DINO 헤드, 최근 5개 중앙값). 헤드가 없으면 `"No DINO head loaded (--head)"`. 화면 표시일 뿐 어떤 판단에도 들어가지 않는다. 판정 배지 (`in_focus` … `unsure`) 는 작업 결과와 지도에 그대로 쓴다 |
| 메모 `"box: 3/4 tiles, sign unsure, offset +0.5"` | 게이지 메모는 9/30 형식 (`"box: 3/4 tiles, sign unsure"`). tare offset 은 아직 게이지에 적용하지 않는다. 기록에는 `grade: "model"` 로 남는다 |
| 타일 테두리 위 `+1.3` | 타일마다 판정 배지의 작은 표시 (아이콘 또는 약어). 읽을 수 없는 타일은 회색 점선 그대로 |
| tare 결과 `"offset +0.52 DoF"` | `"Tared at this focus (objective <label>)"`. 숫자는 기록에만 |
| 지도의 방문 필드 색 (\|s\| ≤ 1 초록, ≤ 3 파랑) | 판정으로 색: `in_focus` 초록, 나머지는 한 가지 중립색. "얼마나 먼지" 를 색으로 나타내지 않는다 |
| z 트레이스 `z_sum` | 그대로. `position` 의 엔코더 값 |
| 스윕 곡선의 x 축 | 각 점의 `z_readback_um` (명령값이 아님). 고른 초점은 가장 가까운 실제 프레임의 엔코더 z (T-003) |

- **화면 어디에도 "예측된 Z" 나 "목표 Z" 를 모델 값으로 보여 주지 않는다.** Z 숫자는 엔코더 readback,
  사람이 입력한 값, 계획 (스윕 범위, 천장) 셋뿐이고, 각각 이름을 붙인다 (`"read"`, `"entered"`, `"plan"`).
- 고전 지표 (Vollath, Brenner, peak) 의 값은 측정이므로 숫자로 보여도 된다. 트레이스와 스윕 곡선이 그렇다.
- Claude 가 답변에 낸 숫자는 `"model"` 로 표시한다 (PLAN 5절 Claude 연동). 프롬프트 칸 (T-014) 의 몫이다.
- 에이전트 카드의 숫자는 카드가 가진 등급 (E1–E5) 을 그대로 배지로 붙인다 (7.1). E6 은 카드에 들어올 수 없다.

### 5.4 그 밖에 9월 30일에서 온 화면 표시

| 사례 | 화면 |
|---|---|
| Aura 깜박임 (−23 % 프레임) | 스캔 진행과 결과에 버린 프레임 수와 z (`dropout_z_um`) 를 적는다 |
| 사람이 재물대를 움직임 (readback 3037 / 3036) | 가드 중단은 `error` 배너로, 원인을 그대로: `"ZDrive read 3036.0, commanded 3037.0: stopped"`. `"moved by hand?"` 같은 추측은 붙이지 않는다 |
| 이중 피크 (오일 부족) | `focus_100x` 결과에 `"check immersion oil"` 경고 (고전 판정). 재로딩 변형 (operations-spec 4.2) 으로 가는 버튼 |
| 포화 | 상태 줄의 `sat %` 를 0 보다 크면 경고색으로. 스윕 결과에 `"reduce exposure"` |
| 30 ms 에서 암전 수준만 읽음 | 판정 `no_sample_here` 와 함께 `"signal at dark level"` (고전) |

---

## 6. 마일스톤 표시

마일스톤의 정의는 PLAN 8절을 따른다 (여기서 다시 적지 않는다). M1 은 전 기능 mock 이므로 이 문서의 모든 항목은
M1 에서 mock 백엔드와 mock 저장소로 끝까지 돈다. 표의 "실제" 열은 같은 항목이 실제 데이터 (M2), 현미경 PC 읽기
전용 (M3), 동작 (M4), 초점 판정 (M5) 중 어디에서 처음 실제로 도는지를 적는다.

| 영역 | 항목 | M1 | 실제 | 비고 |
|---|---|---|---|---|
| 공통 | 내비게이션, 공통 상태 줄, 비활성 이유 (7.0) | M1 | M3 | 상태 줄의 위치·조명은 M3 에서 실제 readback |
| 공통 | `"Lights off"` (선점) | M1 | M3 **(제안)** | 조명은 모션이 아니다. M3 에서 라이브 영상을 보려면 조명을 켜고 꺼야 하므로 `light_set` 과 함께 M3 에 둔다. 총괄 확인 필요 |
| 공통 | 확인 대화상자 틀 (3.0) | M1 | 각 작업과 같이 | |
| `console` | 질문·카드·버전·숫자 등급·실행·수신함 읽기 | M1 | M2 | soft-matter-agents 파일 읽기 |
| `console` | 질문 넣기 | M1 (mock 저장소) | 미정 | 실제 경로는 통합 단계 (PLAN 10절) |
| `console` | 실행 상세에서 F6 로 가는 링크 | M1 | M2 | F6 자체는 T-012 |
| `hardware` | 탐지, 구성 파일, 게이트 표 | M1 | M3 | |
| `hardware` | 사람 확인 항목 입력 | M1 | M3 | |
| `hardware` | 상태 (Step 0, `status`) | M1 | M3 | |
| `hardware` | 조명 켜기 (`light_set`) | M1 | M3 **(제안)** | 위 `"Lights off"` 와 같은 이유 |
| `sample` | 샘플 목록, 열기, 새로 만들기 | M1 | M2 | 실제 샘플 폴더 읽기 (사용자가 사본을 주기로 함, T-005) |
| `sample` | 지오메트리 양식 | M1 | M3 | 필드 목록은 사용자 확인 필요 (PLAN 10절) |
| `sample` | 로딩 확인 (사람 + 이미지) | M1 | M3 | 이미지 확인은 조명과 카메라만 쓴다 |
| `map` | 지도 그리기, 방문 필드, 경계, hole 요약 | M1 | M2 | 실제 `map.json`, `sample.json` 읽기 |
| `map` | 경계점 `b` / `u` | M1 | M3 | 위치 읽기만 |
| `map` | 엣지 추적 | M1 | M4 | XY 이동 |
| `map` | 4x 스캔, 샘플 맵 (모자이크, 후보) | M1 | M4 | 스캔 결과 보기는 M2 (저장된 `scan4x_*`) |
| `map` | flag, 후보 확인 | M1 | M2 | 기록 작업. 실제 샘플 위에서 |
| `map` | 클릭 이동 | M1 | M4 | |
| `objective` | 렌즈 전환 7단계, `"Loading done"`, 복귀, 재로딩 | M1 | M4 | 이탈 거리와 부호가 미정 (PLAN 5절 방향 기준, 10절) 이라 그 전에는 `escape=False` 만 |
| `objective` | 100x 초점 (고전 판정) | M1 | M4 | |
| `live` | 라이브 영상, 상태 줄, 트레이스 | M1 | M3 | 실제 카메라는 M3 (읽기 전용 + 조명) |
| `live` | 고전 판정 배지 | M1 | M3 | |
| `live` | DINO 판정 배지, tare | M1 (가짜 판정) | M5 | 현미경 PC 학습 헤드 |
| `live` | 피에조 `f` / `w` / `W` | 꺼 둠 | M5 이후 | operations-spec 9.2: 다시 설계해야 함 |
| `live` | `"Save frame"`, 녹화 | M1 | M3 | |
| `live` | replay 백엔드로 저장된 스택 보기 | M1 (`data/smoke`) | M2 | T-005 |

PLAN 8절의 M1 확인 방법 가운데 이 문서가 다루는 F1–F5 부분의 "끝까지" 는 아래 순서다. 로그인, 로그, F6, F7 은
각 과제 (T-018, T-012, T-019) 의 몫이고, 이 순서는 로그인하고 실험 세션을 연 뒤에 시작한다:
console 에서 질문 하나를 mock 저장소에 넣고 → hardware 에서 mock 탐지와 게이트 확인 → sample 에서 새 샘플과
지오메트리, 로딩 확인 → map 에서 명시야 추적, 스캔, flag, 클릭 이동 → objective 에서 4x → 100x 전환 (Loading done 포함)
과 100x 초점 → live 에서 판정 배지 확인 → `"Lights off"` 와 조명 readback 확인이다.

---

## 7. F1–F5 화면

범위 조정: 내부 노트의 `tasks/T-004-ui-spec.md` 의 "v0.2 조정" 절. F6 (시뮬레이션 현황 상세) 은 T-012,
F7 (실험 세션) 은 T-019, 로그인은 T-018, 프롬프트 칸은 T-014 가 명세한다. 여기서는 그 결과를 쓰는
자리만 적는다. 작업의 세부 순서는 `docs/operations-spec.md` 를 참조하고 옮겨 쓰지 않는다.

### 7.0 모든 영역에 공통

**배치**

```
+--------------------------------------------------------------------------------+
| 내비게이션: console  hardware  sample  map  objective  live  (simulation, sessions) |
+--------------------------------------------------------------------------------+
| 영역 화면                                                    | 프롬프트 칸 (X1)  |
|                                                              | T-014             |
+--------------------------------------------------------------------------------+
| 공통 상태 줄: 사용자 · 실험 세션 · 조명 · 실행 중 작업 · 대기 확인 · 위치 · [Abort] [Lights off] |
+--------------------------------------------------------------------------------+
```

- 공통 상태 줄의 값은 `/ws/events` 의 `position`, `light_changed`, `started` / `progress` / `finished`,
  `confirm_required` 와 `/api/state` 에서 온다 (T-010).
- 프롬프트 칸은 영역마다 자기 문맥을 붙여 보낸다 (PLAN 공통 요구). 각 영역 절의 "프롬프트 문맥" 이 그 내용이다.
  D7 에 따라 이미지와 프레임은 문맥에 넣지 않는다.

**비활성 이유** (F2.2 "꺼진 기능은 숨기지 않고 이유와 함께"). 버튼과 양식은 숨기지 않고 끄며, 이유를 바로 옆에
한 줄로 보여 준다. 판정은 서버와 엔진이 하고 화면은 그 결과를 그린다. 여러 이유가 겹치면 위에서부터 첫 번째를 보여 준다.

| 이유 | 문구 | 판정하는 곳 | 영향 |
|---|---|---|---|
| 원격 접속 | `"Read-only: remote view"` | 서버 (요청 출처, 명령 403) | `abort` 를 뺀 모든 명령 (D13) |
| 역할 | `"Needs the operator role"` | 서버 (T-018) | viewer 는 `abort`, `lights_off` 를 뺀 모든 명령. admin/operator 만 장비 명령 |
| 장비 제어권 | `"<name> has control of the microscope"` | 서버 (PLAN "장비 제어권") | 다른 사람이 제어 중이면 장비 명령 |
| 실험 세션 | `"Open an experiment session first"` | 엔진 (PLAN 6절 12항) | 장비를 움직이는 명령 |
| 게이트 | `"<feature> is off: <reason>"` (예: `"no XYStage readback"`) | 엔진 게이트 (F2.2) | 그 기능 전체 |
| 실행 중 작업 | `"<op> is running"` | 엔진 (단일 소유) | 다른 모션 작업. 기록 작업과 `lights_off` 는 제외 (4.4) |
| 복귀 대기 | `"Return to the sample position first"` | 엔진 (`awaiting_return`) | 복귀를 뺀 모든 모션 작업 |
| preflight | `preflight_failed` 의 `why` 원문 | 엔진 | 그 작업 |

**정지**: 공통 상태 줄의 `"Abort"` 는 잠김 상태, viewer, 제어권 없는 사용자에게도 켜져 있다 (PLAN "정지는 누구나").
원격에서도 켜져 있다 (D13). 소등 버튼은 로컬에서 누구나 누를 수 있고 원격에서는 꺼진다.

**원격 화면 요약** (영역별 세부는 각 절)

| 영역 | 원격에서 되는 것 | 원격에서 꺼지는 것 |
|---|---|---|
| `console` | 질문·카드·실행 기록 읽기, 버전 비교 | 질문 보내기 |
| `hardware` | 탐지 결과, 구성 파일, 게이트 상태 읽기 | 탐지 실행, 사람 확인 항목 저장, 조명 켜기/끄기 |
| `sample` | 샘플 목록과 기록, 지오메트리 읽기 | 샘플 열기·새로 만들기, 지오메트리 저장, 로딩 확인, `"Open folder"` |
| `map` | 지도, 모자이크, flag, 후보, 진행 보기 | 추적, 스캔, flag 쓰기, 후보 확인, 클릭 이동, 경계점 |
| `objective` | 현재 렌즈, 진행 단계 보기 | 렌즈 전환, `"Loading done"`, 100x 초점 |
| `live` | 영상, 판정, 트레이스, 위치 보기 | 라이브 시작/멈춤, 노출, 키 명령 전부, 프레임 저장 |

### 7.1 `console` — 에이전트 콘솔 (F1)

데이터는 AgentStore (T-008) 를 거친다: `list_questions(agent)`, `get_question(qid)`, `list_runs(agent)`,
`get_run(agent, run_id)`, `list_inbox()`, `submit_question(...)`. 실제 soft-matter-agents 저장소는 읽기 전용이다.
UI 는 카드를 고치지 않는다 (PLAN 6절 9항). 아래 필드 이름은 soft-matter-agents `baf6f1e` 의 파일을 읽어 확인했다.

**화면**

| 패널 | 보여 주는 것 | 출처 |
|---|---|---|
| 질문 목록 | 두 에이전트의 질문. 열: `qid`, 에이전트, `status` (`DRAFT`, `VALIDATED`, `REFUSED` 등), `purpose`, `intent`, `observable.name`, `created_at`, 최신 버전 (접두 없음 = 1판, 그다음 `v2_`, `v3_`, … 있는 만큼). 거르기: 에이전트, 상태, 날짜 | `*/questions/<qid>/` 의 `goal.json` (최신 버전) |
| 질문 상세 | 카드 탭: `goal`, `axis` (축마다 하나, 예: `bd_pairwise` 의 `a1`…`a7`, `verdict`), `synthesis` (`chosen_config`, `operating_point`, `rejected`), `plan` (`sweep`, `conditions`, `envelope_check`, `cost`, `stop_criteria`, `success_criteria`, `open_risks`), `refusal` (`stage`, `reason_code`, `alternatives`), 그리고 microscope 쪽 `analysis_method_declared` 같은 기타 카드 | 같은 폴더의 `*.json`. JSON 이 정본이다 (soft-matter-agents P3). `.md` 는 "generated" 표시와 함께 보조로만 |
| 버전 | 버전 고르개. 목록은 고정하지 않고 폴더에 있는 `vN_` 접두를 모두 모은다 (baf6f1e 기준 `v6_` 까지 있다). 기본은 가장 큰 N. 두 버전의 필드 차이 보기 | 파일 접두 (T-008 의 버전 규칙) |
| 숫자 표 | 카드의 `numbers`: `name`, `value`, `unit`, `source`, **등급 배지** (`E1`–`E5`), `precision`. 등급은 카드의 값을 그대로 쓰고 화면이 다시 매기지 않는다 | `numbers[]` |
| 가정과 빈칸 | `assumptions` (`statement`, `authorised_by`), `kb_refs`, `kb_gaps`, `degraded`. `degraded` 가 비어 있지 않으면 경고 띠 | 같은 카드 |
| 실행 목록 | 에이전트별 `run_id`, `qid`, `plan_id`, `backend`, 시작 (`t0_wall`), 끝 (`finished_at`), 승인 (`approval.kind`) | `*/runs/<run_id>/log.json`, `config.json` |
| 실행 상세: simulation | `config.json` 의 `parameters_si`, `envelope_check`, `seed`. `log.json` 의 이벤트 (`preflight`, `dispatch`, `progress`, `complete`). `observables.json` 의 `fit` (예: `diffusivity`, `standard_error`), `uncertainty`, `msd_curve` 그래프. 진행률·궤적·내려받기는 F6 (T-012) 화면으로 이어지는 링크 | `simulation_agent/runs/<run_id>/` |
| 실행 상세: microscope | `log.json` 의 이벤트 시간순 (`gate_open`, `apply`, `failed`, `shutdown_failed` 등), `approved_commands`, `no_plan_because`, `not_dispatched` 같은 설명 필드. `commands.json` | `microscope_agent/runs/<run_id>/` |
| 수신함 | 스레드 목록 (`thr-…`), 라운드 (`r1_`, `r2_`), `direction`, `trigger`, `answerability`, `unit_consistency.verdict`, `value_comparison.verdict`, `supersedes` | `microscope_agent/inbox/<thread>/` |
| 이 저장소의 실험 | 샘플 기록과 실험 세션 목록. 샘플을 고르면 `sample` 영역으로 | `D:\AutoFocus\samples`, F7 기록 저장소 |
| 질문 넣기 (F1.1) | 본문, 대상 에이전트 (`microscope` / `simulation`), 보내기 | `submit_question`. mock 저장소에만 쓴다 (`"origin": "dino-autofocus mock"`). 실제 저장소면 버튼이 꺼지고 `"Submitting to soft-matter-agents is not connected yet (read-only)"` |

**전송과 갱신**

| 요청 | 전송 | 갱신 |
|---|---|---|
| 목록, 상세, 실행, 수신함 | REST `GET /api/console/...` (제안: `questions?agent=`, `questions/{qid}?version=`, `runs?agent=`, `runs/{agent}/{run_id}`, `inbox`) | 영역을 열 때와 `"Refresh"` 버튼. 파일 감시는 하지 않는다 **(제안: 주기 폴링이 필요하면 30 s)** |
| 질문 넣기 | REST `POST /api/console/questions` (mock 만) | 응답 뒤 목록 다시 읽기 |

**원격과 역할**: 읽기는 원격과 viewer 모두 된다. 질문 넣기는 로컬 operator/admin 만 **(제안: 하드웨어가 아니므로 viewer
에게도 열지 T-018 에서 정할 것)**.

**프롬프트 문맥**: 고른 `qid`, 버전, 고른 카드 종류, 고른 `run_id`.

### 7.2 `hardware` — 하드웨어 파악과 상태 (F2, 런처 Step 0)

작업: `hardware_scan` (operations-spec 5절), `status`, `light_set`, `lights_off`.

**화면**

| 패널 | 보여 주는 것 | 출처 / 이벤트 |
|---|---|---|
| 탐지 요약 | 마지막 탐지 시각, 백엔드 (`mock` / `mm-demo` / `mm-real`), config 경로, 구성 파일 이름과 해시, 이전 구성 파일과 다른 점 | `hardware_profile.json` (`GET`) |
| 장치 표 | 장치마다: 이름, 종류, 로드됨, 속성 읽기, readback 확인 가능, 메모. 문제 있는 행은 위로 | 같음 |
| 대물렌즈 표 | Nosepiece 위치와 라벨, NA, 배율, 액침, 작동 거리 (없으면 `"not set"`), 픽셀 크기 | 같음 + 렌즈 표 |
| 카메라·피에조 | 비트 깊이 (Kinetix 12-bit, 천장 4095), 센서 크기, 피에조 연결 여부 | 같음 |
| 사람 확인 항목 | 탐지가 아니라 입력: DiaLamp 세기 (스탠드에서 읽은 값, 9/30 은 608/2100), CondenserTurret, 40x WI 보정 링 등. 누가 언제 넣었는지 | `human_confirmed{}` (operations-spec 5절) |
| 게이트 표 | 기능마다: 켜짐/꺼짐, 꺼진 이유 목록 (빠진 장치, readback 불가, 사람 확인 없음, 값 미측정 예: `"escape distance not set"`), 필요한 장치 | 엔진 게이트 판정 (`GET`) |
| 지금 상태 (Step 0) | 렌즈, Z, PFS (`enabled`, `locked`, `in_range`). `"Show objective / Z / PFS"` 로 `status` 를 돌린 결과와, 주기 `position` | `finished(status).summary`, `position` |
| 조명 | 명시야 켜기, Aura 라인과 퍼센트로 켜기, 끄기. 현재 상태는 5.2 | `light_changed` |

**입력**

| 입력 | 명령 | 비고 |
|---|---|---|
| `"Scan hardware"` | `start("hardware_scan")` | 읽기만 한다 |
| 사람 확인 항목 저장 | `start("hardware_confirm", {...})` **(제안, WP-G)** | 구성 파일에 기록. 게이트가 다시 판정된다 |
| `"Show objective / Z / PFS"` | `start("status")` | |
| `"Brightfield on"` / `"Aura <line> <pct> % on"` | `start("light_set", {...})` | 4.0 |
| `"Lights off"` | `lights_off` 명령 (events.py 의 명령 종류, `start` 가 아님) | 선점 |

**원격과 역할**: 원격과 viewer 는 읽기만. 조명 켜기는 장비 명령이므로 operator 와 제어권이 필요하다. 소등 (`lights_off`) 만은 로컬에서 로그인한 누구나 보낼 수 있다.

**프롬프트 문맥**: 고른 장치 이름, 고른 게이트 이름과 그 이유 목록.

### 7.3 `sample` — 샘플과 로딩 확인 (F3, 런처 Sample)

작업: `sample_open`, `sample_new` (4.0), 지오메트리 저장과 로딩 확인 (WP-H, 이름은 제안).

**화면**

| 패널 | 보여 주는 것 | 출처 |
|---|---|---|
| 샘플 목록 | 샘플 ID (`YYYYMMDD_HHMM_n`), 만든 시각, hole 피팅 시각 (`fitted_at`), 사용한 렌즈, 마지막 실험 세션, `awaiting_return` 표시 | `GET /api/sample/list` (제안). 샘플 루트 |
| 열린 샘플 | ID, 폴더, hole 요약, 보정 (`um_per_px`, 렌즈), 스캔·지도·flag 수 | `sample_opened`, `map_changed` |
| 지오메트리 양식 (F3.1) | 샘플 크기 (기본 24 × 50 mm), 챔버 형태와 구멍 지름 (9/30 시료 약 6 mm), 커버슬립 두께 (기본 170 µm), 샘플 두께, 방향 (정상 / 뒤집힘). 칸마다 값의 출처 (`"entered by <user> <t>"`, `"default"`, `"not set"`). **안전 한계에 들어가는 칸** (커버슬립 두께, 샘플 두께, 방향) 에는 표시를 붙인다 | 샘플 기록 (`GET`) |
| 로딩 확인 | 3단계: (1) 지오메트리 입력 (2) 사람이 `"Sample is on the stage"` 확인 (3) 이미지 확인: 4x 명시야 한 장에서 구멍 가장자리가 보이는지 판정 (grade `"computed"`: 측정값에서 계산, 모델 아님). 셋이 다 되면 `"Loading confirmed (person + image)"`. PLAN F3: 선택값 읽기는 상태 확인이 아니다 | 엔진 기록 (제안) |

**입력**

| 입력 | 명령 | 비고 |
|---|---|---|
| 목록에서 고르기 | `start("sample_open", {"sample_id"})` | U1 |
| `"New sample"` | `start("sample_new")` | U1. 지오메트리 양식이 열린다 |
| `"Open folder"` | 서버 PC 에서 탐색기 열기 | 로컬 화면에서만. 원격이면 버튼이 없고 경로만 보여 준다 |
| 지오메트리 저장 | `start("sample_geometry_set", {...})` **(제안, WP-H)** | U4. 기록 작업이라 단일 소유에서 빠진다 |
| `"Sample is on the stage"` | `start("loading_confirm_person")` **(제안)** | 수동 단계 기록 |
| `"Check with an image"` | `start("loading_check_image")` **(제안)** | 명시야를 켜고 한 장 찍고 끈다. 장비 명령이다 (게이트: 카메라, DiaLamp, 4x). 결과의 grade 는 `"computed"` (T-027) |

**원격과 역할**: 원격과 viewer 는 읽기만. 이미지 확인은 장비 명령이므로 operator, 제어권, 실험 세션이 필요하다.

**프롬프트 문맥**: 샘플 ID, 지오메트리 값과 그 출처, 로딩 확인 상태.

### 7.4 `map` — 샘플 맵 (F4, 라이브 뷰의 지도, 런처 Step 1·2)

작업: `edge_trace`, `scan_4x`, `sample_map`, `map_flag`, `goto_xy` (operations-spec 3·6·8절), `boundary_mark`,
`boundary_undo`, `boundary_reset` (4.0). 입자 후보 확인은 이름이 없어 제안한다.

**지도 층** (아래에서 위로, 각 층을 켜고 끌 수 있다)

| 층 | 그리는 것 | 출처 |
|---|---|---|
| 모자이크 | 투과광 4x 모자이크 (명시야 권장). 스캔이 여럿이면 고르개 | `sample_map_<stamp>/mosaic.npy` + `mosaic.json` (`x0, x1, y0, y1, um_per_px, bin`) 을 서버가 이미지로 (`GET`, 제안). 좌우 반전은 보정 `M` 의 부호로 서버가 맞춘다 (operations-spec 6.1). 영상은 재물대와 거울상이고, 픽셀 p 의 재물대 좌표는 `stage + inv(M) @ (centre − p)` 다 (PLAN 5절 방향 기준, v1.2) |
| 스캔 박스 | 마지막 `scan_4x` / `sample_map` 의 박스와 + 1 mm 여유 (클릭 이동 허용 범위) | 스캔 기록 |
| 방문 필드 | 1.2 (d) 와 같음. 색은 판정 (5.3) | `map_changed` |
| 경계와 hole | 경계점, 원 피팅, 중심. 피팅 시각과 세션 상태 (5.1) | `map_changed`, `sample_opened` |
| 입자 후보 | **두 가지를 모양으로 구분**: 고전 처리 후보 (`source: "classical_candidate"`) 는 속이 빈 원, 사람이 확인한 것 (`source: "person_confirmed"`) 은 속이 찬 원. 거부한 후보는 기본으로 숨기고 켜면 회색 × | `features.json` 또는 `map.json` (operations-spec 6.1) |
| flag | 깃발과 이름. 은퇴한 flag 는 기본으로 숨김 | `flags.json` |
| 현재 시야 | 주황 사각형과 십자 (1.2 (d)) | `position`, `objective` |
| 클릭 목표 | 마우스 위치의 stage 좌표, 현재 위치에서 거리, 허용 범위 안/밖 | 화면 계산 (표시만). 모자이크 픽셀에서 stage 좌표로는 PLAN 5절 방향 기준의 식을 쓰고, 화면이 따로 부호를 정하지 않는다. 식과 `M` 은 서버가 `mosaic.json` 과 함께 내려 준다 **(제안)** |

축 방향은 1.2 (d) 처럼 스탠드의 조이스틱 방향으로 뒤집어 그리고, 축척 글자에 방향을 적는다.

**옆 패널**

| 패널 | 보여 주는 것 / 입력 |
|---|---|
| 순서 | 5.1 의 두 단계 (명시야 추적 → 입자 조명 스캔) 와 각 단계의 상태 |
| hole 요약 | 중심, 지름, rms, 점 수, 호 각도, `fitted_at`. 예상 지름과 20 % 넘게 다르면 경고 (operations-spec 8절) |
| 엣지 추적 | 속도 (기본 100 µm/s, 10..1000), 예상 지름 (기본: 샘플 지오메트리), `"Start tracing"` / `"Stop"`, `+` / `-`. 진행: 상태 문자열, 경로 길이, 점 수 |
| 스캔 | 종류 (`"4x scan, particle light"` = `scan_4x`, `"Sample map, brightfield"` = `sample_map`), 노출 (빈 칸 = auto), dry run, 초점 방식 (`per_tile` / `plane`). 진행: 타일 k/n, 현재 타일의 곡선 (1.3), 버린 프레임 |
| 결과 | `scan4x_*`, `sample_map_*` 목록. 고르면 모자이크 층과 z 지도 (타일별 초점, 6 × 6 블록 z) |
| flag | 목록: 이름, 메모, 시각, 렌즈, x, y, z (엔코더). 추가, 메모 고치기는 새 항목으로, 은퇴 (U3) |
| 후보 | 목록과 지도에서 고르기: `"Confirm"` / `"Reject"`. 확인과 거부는 덮어쓰지 않고 새 항목을 더한다 |

**클릭 이동 (F4.3)** — 화면에서 보이는 순서

| 단계 | 화면 | 엔진 |
|---|---|---|
| 1 마우스를 올림 | 목표 좌표, 거리, 허용 범위 밖이면 커서 옆에 `"outside the scanned area"` | 없음 (표시 계산) |
| 2 클릭 | 목표에 핀. `start("goto_xy", {"x_um", "y_um", "sample_id"})` | `planned` (거리, 큰 이동 여부, 후퇴 필요 여부, `z_safe`) |
| 3a 범위 밖 | 핀이 빨간 ×로 바뀌고 `preflight_failed` 의 이유: `"outside the scan box + 1 mm"`. 움직이지 않음 | preflight 거부 |
| 3b 다른 이유로 거부 | 같은 자리에 이유 (`"<op> is running"`, `"Return to the sample position first"`) | preflight 거부 |
| 3c 후퇴가 필요 | C12 대화상자: `"retract Z <z> -> <z_safe>, then move to (x, y)"` | `confirm_required` |
| 4 후퇴 | 진행 줄 `"Retracting Z 3048.7 -> <z_safe>"`. 위치 표의 Z 가 엔코더 값으로 내려가는 것이 보인다 | `progress`, `position` |
| 5 XY 이동 | `"Moving to (x, y)"`. 현재 시야 사각형이 움직인다 | `progress`, `position` |
| 6 끝 | `"Arrived (x, y read back). Z left retracted at <z>: refocus with a scan tile or focus_100x"` 띠 | `finished` (착지 readback) |

Z 는 다시 올리지 않는다 (operations-spec 6.3 의 4번). 화면은 다음 초점 작업으로 가는 버튼만 보여 준다.

**입력 → 명령**

| 입력 | 명령 |
|---|---|
| `"Start tracing"` / `t` | `start("edge_trace", {"speed_um_s", "hole_diameter_mm"})` (C4, C5) |
| `+` / `-` | `update(op_id, {"speed_um_s": v})` |
| `b` / `u` | `start("boundary_mark")` / `start("boundary_undo")` |
| `"Re-trace"` | `start("edge_trace")` 의 C4 (백업 후 비움). 따로 비우는 버튼은 `start("boundary_reset")` |
| `"Start scan"` | `start("scan_4x", …)` 또는 `start("sample_map", …)` (C1–C3) |
| flag 추가 | `start("map_flag", {"sample_id", "x_um", "y_um", "name", "note"})` |
| flag 은퇴 | `start("map_flag_retire", {"flag_id"})` **(제안)** (U3) |
| 후보 확인 / 거부 | `start("candidate_confirm" / "candidate_reject", {"candidate_id"})` **(제안)** |
| 지도 클릭 | `start("goto_xy", …)` (C12) |

**원격과 역할**: 원격과 viewer 는 지도와 진행 보기만. flag 와 후보 확인은 하드웨어가 아니지만 샘플 기록을 쓰므로
로컬 operator 만 **(제안)**.

**프롬프트 문맥**: 샘플 ID, 클릭한 좌표 또는 고른 영역, 고른 flag 와 후보, hole 요약. 모자이크 그림은 넣지 않는다 (D7).

### 7.5 `objective` — 배율 전환과 액침액 로딩, 100x 초점 (F5)

작업: `objective_change` (operations-spec 4.2), `focus_100x` (7절).

**렌즈 전환 화면**

| 패널 | 보여 주는 것 / 입력 |
|---|---|
| 현재 | 렌즈 라벨, 픽셀 크기, Z (엔코더), PFS |
| 고르기 | 렌즈 표의 렌즈. 같은 렌즈, 렌즈 표에 없는 렌즈, 작동 거리가 없는 렌즈 (40x WI) 는 꺼짐과 이유 (`"already on that objective"`, `"no working distance value"`) |
| 선택 | Y 이탈 (`escape`) 켬/끔과 거리. 이탈의 **거리와 부호 (+Y / −Y) 둘 다** 아직 사용자 확인 전이다 (PLAN 5절 방향 기준 v1.2, 10절). 정해지기 전에는 켬이 꺼져 있고 이유는 엔진 문구 그대로 `"escape distance not set"` 이다 (operations-spec 4.2, 3.0 의 원칙). 문구가 거리만 말하지만 부호도 미정이며, 화면은 부호를 기본값으로 고르지 않는다. 건조 렌즈끼리면 끔이 기본 |
| 계획 | 7단계와 각 단계의 목표값 (`planned`) |
| 시작 | `"Rotate"` → C6 |

**7단계 진행 표시** — 단계마다 한 줄: 상태 (대기, 진행, 완료, 실패), 읽은 값, 시각.

| 단계 | 줄의 내용 | 이벤트 |
|---|---|---|
| 1 기록 | 시작 XY, Z, 렌즈 (`return_xy`, `z_before`, `objective_before`) | `started.start_state` |
| (1b) 소등 | 조명 readback | `light_changed` |
| 2 Z 후퇴 | `"PFS off · Z 3048.7 -> 0.0 (read 0.0) · PFS Out of Range"` | `progress(step=2)`, `position` |
| 3 Y 이탈 | `"Y 571.6 -> <y + dy> (read …)"`. Z 후퇴 확인이 이동 직전에 다시 읽혔다는 표시 | `progress(step=3)` |
| 4 회전 | `"Nosepiece <now> -> <target> (read <label>)"` | `progress(step=4)`, `objective` |
| 5 로딩 | **큰 카드**: `"Load <oil / water> on <label>, then press Loading done"`. 버튼 `"Loading done"` (C7). 누가 언제 눌렀는지 | `confirm_required(kind="manual_step")` |
| 6 복귀 | `"XY -> (x, y) (read …)"`. Z 는 여전히 후퇴 | `progress(step=6)` |
| 7 Z 접근 | 진행 막대: 현재 Z (엔코더), 목표 (`approach_target_um`, 기본 2800), 걸음 수, 렌즈 상한. 목표로 점프하지 않고 걸음마다 한 칸 | `progress(step=7, data={z_um, target_um, step, n_steps})` |
| 끝 | 새 렌즈, 픽셀 크기, Z, 조명 꺼짐 | `finished` |

- 중단 위치에 따라 남는 상태가 다르다 (operations-spec 4.2 의 5항 표). 3–6단계에서 멈추면 `awaiting_return` 이고, 공통 상태 줄에
  `"Objective change interrupted: return to the sample position"` 과 `"Return to sample position"` 버튼이 모든 영역에 보인다.
  이 버튼은 6·7단계만 돌리는 복귀 작업이다 **(이름 제안: `start("objective_change", {"resume": true})`, T-011 과 맞출 것)**.
- 재로딩 변형 (같은 렌즈에서 2·3·5·6·7단계만, operations-spec 4.2 의 8항 제안) 은 `"Re-load immersion"` 버튼으로 둔다.
  `focus_100x` 의 이중 피크 경고에서 이 버튼으로 바로 온다.

**100x 초점 화면**

| 패널 | 보여 주는 것 / 입력 |
|---|---|
| 양식 | 중심 (계산값으로 채움, 5.1), 반폭 (기본 40), 걸음 (2), 고운 반폭 (3), 고운 걸음 (0.2), 노출 (9/30 값 20 ms 를 후보로), 지표 (`peak` 기본, `vollath`) |
| 참고값 | 같은 XY 의 4x 초점 평면 값, 천장 `min(3200, centre + 0.4 × 130)`, 이번 세션의 액침 로딩 기록 유무 (없으면 C10) |
| 곡선 | 지표 대 Z. x 는 `z_readback_um`. 천장 선, 피크 표시, 포화 점 표시 |
| 결과 | 판정 배지 (고전), 고른 프레임의 엔코더 Z, 경고 (`"check immersion oil"`, `"reduce exposure"`, `"signal at dark level"`) |

**입력 → 명령**

| 입력 | 명령 |
|---|---|
| `"Rotate"` | `start("objective_change", {"target_state", "escape", "escape_dy_um", "approach_target_um", "approach_step_um"})` (C6) |
| `"Loading done"` | `confirm(op_id, "load_immersion", "done")` (C7) |
| `"Return to sample position"` | 위의 복귀 작업 (제안) |
| `"Re-load immersion"` | `start("objective_change", {"target_state": <현재>, …})` (operations-spec 제안 변형) |
| `"Find 100x focus"` | `start("focus_100x", {"centre_um", "half_um", "step_um", "fine_half_um", "fine_step_um", "exposure_ms", "metric"})` (C9–C11) |

**원격과 역할**: 원격과 viewer 는 진행 보기만. `"Loading done"` 은 현미경 앞에 있는 사람이 누르는 것이므로 원격에서는
설정과 무관하게 항상 꺼진다.

**프롬프트 문맥**: 현재 렌즈, 목표 렌즈, 진행 단계, 마지막 100x 결과의 판정과 엔코더 Z.

### 7.6 `live` — 라이브 뷰

1·2절의 라이브 뷰 그대로이고, 표시 규칙은 5.3 을 따른다. 바뀌는 점만:

- 게이지는 9/30 모양 그대로 (5.3, 사용자 결정 2026-10-02). 트레이스 둘은 그대로.
- 키 바인딩 (2.1) 은 그대로 단축키로 두고, 같은 동작의 버튼을 둔다. 판정과 무관한 키 (`b`, `u`, `t`, `+`, `-`) 는 `map` 영역과 같은 명령이다.
- 피에조 키 (`f`, `w`, `W`) 는 operations-spec 9.2 에 따라 M5 전까지 **꺼 두고** 이유 `"piezo focus is out of scope until M5"` 를 보여 준다.
- `"Save frame"` (새).
- 원격: 영상, 판정, 트레이스, 위치는 보이고 키와 버튼은 모두 꺼진다.
- **프롬프트 문맥**: 실행 중 작업, 최신 판정 (어휘), 위치 (엔코더), 렌즈, 조명. 프레임은 넣지 않는다 (D7).
- **카메라가 둘이면 고정 자막** (P-01): 나란히 보기와 합성 보기는 프레임을 호스트 도착 시각으로 짝지은
  것이지 동시 촬영이 아니다 (`WsFrame.time_base: "software"`). 표시 전용이며 타이밍·상관·공존 분석에
  쓰지 않는다. 동시 촬영은 하드웨어 트리거가 있는 soft-matter-agents plan 의 일이다 (그쪽 plan.md 4.6.9).
