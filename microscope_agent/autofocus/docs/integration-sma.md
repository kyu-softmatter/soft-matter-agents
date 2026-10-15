# soft-matter-agents 통합 준비 (M6, 초안 2026-10-02)

PLAN.md 8절 M6 "soft-matter-agents 어댑터 설계" 의 출발점. 근거는 soft-matter-agents `baf6f1e`
(2026-09-29) 를 읽기 전용으로 읽은 결과와 이 저장소 main `d239448`. 그쪽 경로는 그 저장소 기준이다.
이 문서는 설계 초안이고, 결정은 7절의 사람 결정을 거친다.

## 1. 지금 상태 요약

| | dino-autofocus | soft-matter-agents |
|---|---|---|
| 초점 | `focus/` 고전 지표 + 판정 (`in_focus \| step_up \| step_down \| no_sample_here \| unsure`), DINO 는 보조 | 초점 코드 없음. 과제 026 (2단계 첫 초점) **미배정**. 판정 어휘는 `plan.md` §13.2 Trial 2 에 있다 |
| Z 이동 | 엔진 가드 안에서만, 실제 장비는 두 겹 잠금 (`BENCH_MOTION`, `BENCH_APPROACH`) | ZDrive 는 네 곳에서 거부 (`SOFTWARE_MAY_COMMAND` 에 없음, `NAMED_REFUSALS`, `REFUSED_CALLS`, 과제 033) |
| 한계값 | `guards.py` 의 표, 모두 `unmeasured provisional` (40x WI 0.17 mm 는 사용자 값) | `envelope/safety.json` (사람만 씀). **ZDrive 위치·스텝·속도, XY 이동 범위, 초점 탐색 범위 키가 없다.** 스키마가 `additionalProperties:false` |
| 기록 | 실험 세션 폴더, 작업별 기록, 수치에 grade (`measured \| computed \| model`) | `runs/<run_id>/log.json` (run_log 스키마), 등급 E1–E6, 모델 숫자는 E6 이고 카드에 들어가지 않는다 |
| 의존성 | core 에 torch, pymmcore-plus 0.18.1, sklearn, matplotlib 등 | pixi `mic`: pymmcore-plus 0.18.1 / pymmcore 12.5.0.75.0 (같은 고정값). torch, sklearn, skimage, pydantic, pyyaml **없음** |
| 공개 | 비공개 (D5: 통합 때 공개) | 공개 |

## 2. 통합의 기본 방향 (권고)

**soft-matter-agents 의 orchestrator 가 장비를 움직이는 유일한 경로로 남는다.** 이 저장소의 엔진·가드를
그쪽에 두 번째 모션 경로로 들여가지 않는다. 그쪽 규칙상 `devices/` 는 orchestrator 만 부르고, 안전 비교는
결정론적 Python 이며, 모든 이동은 plan 필드에서 `from` 을 달고 나온다.

그래서 넘겨줄 것은 세 가지로 나뉜다.

1. **판정 제공자 (verdict provider)**: 프레임에서 나온 결정론적 지표와 엔코더 Z 를 받아 판정 하나,
   가리킨 프레임, 근거를 돌려주는 순수 함수. Z 를 돌려주지 않고, 무엇도 허용하지 않는다 (거부만 가능).
   `focus/verdict.py` 의 `from_sweep` 이 이미 이 모양이다 (numpy 만, scipy 는 함수 안 import).
2. **화면 (UI)**: 이 저장소의 웹 앱은 그쪽 파일을 읽기만 한다 (`agents/sma_files.py`). 통합 뒤에도
   장비 쪽은 그쪽 run 과 approval 을 보여 주고, 동작은 그쪽 plan 승인 흐름으로 넘긴다.
3. **측정값과 운영 규칙**: 9월 30일·10월 2일 벤치 결과, 렌즈 작동 거리, 방향 규칙은 코드가 아니라
   라이브러리언 항목(최대 E3)과 사람이 쓰는 envelope 로 건너간다. 이 저장소의 숫자를 그쪽 코드에 직접 넣지 않는다.

## 3. 접점 (그쪽 구조에 맞춘 위치)

| 접점 | 그쪽 위치 | 이 저장소에서 오는 것 | 그쪽 규칙 |
|---|---|---|---|
| A 판정 제공자 | `microscope_agent/src/` 의 평평한 파일 하나 (예: `focus_verdict.py`). `operator.run` 의 `observe` 훅 (`operator.py:1186`) 또는 Trial 2 탐색 루프가 부른다 | `focus/classical.py` + `verdict.py` 의 순수 부분 | check 13 (평평한 src), check 16 (devices 를 import 하지 않음), check 82 (외부 import 선언). 기록은 `log.json` 의 이벤트 (`focus_verdict` 또는 §13.1 의 `watcher_flag`) |
| B 프레임 출처 | `devices/micromanager.py` 의 `snap` / `sequence` (이미 가드됨) | 없음. 이 저장소의 `Backend.snap` 을 들여가지 않는다 | 프레임 Z 는 장치 읽기 |
| C Z 구동 | `devices/micromanager.py` 확장 또는 새 `devices/<driver>.py` | 동작 규칙만: 상향 스윕, 매 스텝 읽기 확인, PFS 를 먼저 끔, 후퇴 0 µm, 큰 XY 이동 전 후퇴 | 허용 목록을 푸는 **별도 과제 카드** (`_operation_gate` 방식의 예외), envelope 에 새 Z 한계, 매 스텝 간격 비교 |
| D plan 모양 | `plan.schema` 의 새 절 (focus search: step, range, 이동 횟수 상한, 분기 목록, 성공 기준), `operator.derive_*`, check 86 또는 새 check | `focus_100x` 의 단계 정의와 상한 | manager-microscope 가 스키마와 검사를 고친다 |
| E 작동 거리 | `operator.RESOLVERS["working_distance"]` | 40x WI 0.17 mm (d239448) 는 **그쪽에 숫자로 넣지 않는다**. 측정 → 라이브러리언 항목 → 그쪽 갭 `objective_40x_wd_at_170um` 해소 | 범위면 가까운 끝 (0.16 mm). 첫 대상은 100x Oil 이 권고 |
| F 세션 ↔ run | `runs/<run_id>/` | `session.json` 의 세션 id, 사용자, 백엔드, `bench` | 라이브러리언은 `bench: false` 세션을 건너뛴다 (T-106b, BACKLOG M6) |
| G 도구 노출 | 그쪽 Claude Code 세션 | 어시스턴트의 읽기 도구를 MCP 로 (PLAN 5절 X2) | 과제 026 §9: 외부 서비스 호출은 "사람의 결정, 미승인" |

## 4. 이 저장소에서 지금 할 수 있는 준비 (그쪽을 건드리지 않음)

| # | 일 | 이유 | 소유 |
|---|---|---|---|
| P1 (완료, 802284e) | `pyproject.toml` 을 가벼운 core (numpy, scipy) + 선택 의존성 `ml` (torch, torchvision, sklearn, skimage), `hw` (pymmcore-plus), `server`, `plot` 으로 나눈다 | check 82 와 pixi `mic` 에 선언할 것을 최소로. PLAN 4절 방침과 같다 | pyproject 권한 순서 (BACKLOG) |
| P2 | 판정 제공자 공개 표면 고정: `focus.verdict` 의 입력·출력을 JSON 계약으로 적고, numpy 만으로 import 되는지 계약 테스트 | 접점 A. 그쪽은 파일 하나로 복사하거나 의존성으로 받는다 | WP-E |
| P3 | `FocusVerdict.as_record()` 를 그쪽 run_log 이벤트 모양으로 바꾸는 변환기와, 그쪽 `contracts/schemas/run_log.schema.json` 을 (읽기만) 써서 검증하는 테스트 (그 저장소가 없으면 skip) | 기록 형식을 미리 맞춘다. `model` grade 는 E6 로 대응, 카드에는 안 들어감 | WP-E |
| P4 | `guards.py` 의 모든 숫자 표 (FREE_WD_UM, BENCH_FREE_WD_UM, 큰 XY 문턱, Y 이탈 15 mm 등) 의 출처·등급 목록 | 라이브러리언과 envelope 로 넘길 목록. 그쪽에서는 사람이 값을 쓴다 | 가드 소유자 |
| P5 | 공개 전 점검: 기록에 실제 이메일 없음 (git 전체 이력 검색 결과 0 건, 2026-10-02), 9/30 기록의 operator 이름 (유지 결정), `models/heads/*.joblib` (피클이라 공개 저장소에서 내려받아 여는 쪽이 위험; 형식 또는 해시 고정 검토), 보안 두 항목 (가입 409, 시도 제한) | D5 공개 | 총괄 |
| P6 | T-106b (`session.json` 에 backend kind, bench) | 접점 F | 카드 있음 |

P1–P3 은 서로 독립이라 바로 카드로 만들 수 있다. P5 는 공개 직전에 다시 한 번.

## 5. 의존 방식 선택지 (결정 필요, 7절 Q2)

| 선택지 | 장점 | 문제 |
|---|---|---|
| a. 판정 부분만 그쪽 `src/` 에 파일 하나로 옮긴다 (복사) | 그쪽 detachable 규칙, check 13 에 맞는다. 외부 import 는 numpy 뿐 | 두 사본. 이 저장소가 원본이고 커밋 해시를 그쪽 파일에 적는다 |
| b. 공개된 dino-autofocus 를 git 의존성 (커밋 고정) | 사본 없음 | 아키텍처 좌석이 pixi 를 고친다. 지금 core 가 무거워 P1 이 먼저 |
| c. 경로 의존성 | 쉬움 | `microscope_agent/` + `contracts/` 를 현미경 PC 로 떼어 가는 규칙을 깬다. 비권고 |

결정 (Q2): **a 를 폴더 단위로** (소스를 그쪽 폴더로 옮긴다). 첫 단계는 고전 판정만, DINO 없음. 결정론적 지표 최대값 대체 경로가 먼저라는 과제 026 §9 와 맞는다.
DINO 점수는 그다음에 shadow mode (§13.1) 로, b 방식과 `ml` 선택 의존성으로.

## 6. 바꿀 수 없는 그쪽 규칙 (설계가 지켜야 할 것)

- 모델 숫자는 E6, 카드와 KB 항목에 들어가지 않는다. 판정은 거부만 할 수 있고 허용하지 않는다.
- 찾은 Z 는 엔코더 읽기. 넘겨받은 Z 는 목적지가 아니라 목표 (직접 점프 없음, 매 스텝 간격 비교).
- 안전 비교는 결정론적 Python. 애매하면 멈춘다. `unsure` 는 실패가 아니라 기권.
- 모든 이동은 plan 필드에서 유도되고 `from` 을 단다. Tier 1 위는 승인 (`plan_approval`) 이 먼저.
- 다른 저장소에서 온 숫자는 라이브러리언을 거쳐 최대 E3, 안전 한계는 건너가지 않는다 (`rulings.jsonl`).
- 의존성 파일 (`pyproject.toml`, `uv.lock`, `pixi.lock`) 은 아키텍처 좌석만.
- 이 저장소는 그쪽 저장소에 쓰지 않는다 (PLAN 5절).

## 7. 사람 결정 (사용자, 2026-10-02)

| # | 질문 | 결정 |
|---|---|---|
| Q1 | 초점을 누가 맡나 | **그쪽 하드웨어 엔진이 맡는다.** 하드웨어 오케스트레이션의 일부 (microscope_agent) |
| Q2 | 의존 방식 | **지금은 따로 개발하고, 합칠 것을 생각해 폴더 구조를 미리 고친다.** 개발이 끝나면 소스를 그쪽 해당 폴더로 옮긴다. 그래서 5절의 b (의존성) 는 쓰지 않고, a (옮겨 넣기) 를 폴더 단위로 한다. 대응표와 단계는 9절 |
| Q3 | 이 저장소의 값을 그쪽 출처로 인정할지 | **합칠 때 정한다.** 사람이 쓰거나 잰 값인지는 사용자가 직접 확인한다. 이 저장소는 값마다 카드로 묻는다 (대부분 이미 공유되어 있을 것). 라이브러리언에게 줄 정보는 `docs/librarian-handoff.md` 에 따로 모은다 |
| Q4 | Z 한계 | **액침액이 필요한 대물렌즈 (40x WI, 60x Oil, 100x Oil) 만 한계를 두고, 나머지 (건식) 는 푼다.** soft-matter-agents 규칙을 따른다 (`objective_clearance_min` 이 렌즈 위치별 작동 거리에서 풀리는 방식). 이 저장소의 가드 변경은 별도 카드로 |
| Q5 | 기권 문턱 | **지금의 임시값으로 진행한다** (`MAX_SIGMA_DOF = 3.0`, `MIN_CURVE_CONTRAST = 0.05`, `MIN_DYNAMIC_RANGE_ADU = 20`, 모두 `unmeasured provisional`). 벤치에서 사람이 맞춘 초점과 비교한 기록으로 나중에 정한다 |
| Q6 | Claude 연동의 위치 | **이 저장소는 인터페이스 (프론트엔드 일부) 와 자동 초점 (백엔드) 을 맡는다. 에이전트 자체는 모두 백엔드가 된다.** 화면의 Claude 연동은 통합 뒤 그쪽 에이전트 쪽으로 간다 |
| Q7 | 공개 시점 | **3주 안 (2026-10-23 까지).** P5 를 그 전에 끝낸다 |

Q5 설명: 판정기는 확신이 낮으면 `step_up` / `step_down` 대신 `unsure` (기권) 를 낸다. "얼마나 낮으면 기권하나" 가
기권 문턱이다. 지금 이 저장소의 값은 `focus/verdict.py` 의 `MAX_SIGMA_DOF = 3.0` (모델 불확실도가 피사계 심도의
3 배를 넘으면 기권), `MIN_CURVE_CONTRAST = 0.05`, `MIN_DYNAMIC_RANGE_ADU = 20` 이고 모두 임시값이다. 그쪽 과제 026
§9 는 이 문턱을 "미정" 으로 둔다. 권고: 임시값으로 시작하고, 벤치에서 사람이 맞춘 초점과 비교한 기록으로 정한다.

### 7.1 결정 묶음 A (사용자, 2026-10-05)

사용자가 2026-10-05 에 작업계획(`integration-sma-workplan.md`) 5절의 묶음 A 를 "모두 승인" 했다. 그래서 각 질문의
**권고안을 그대로 결정으로** 적는다. 2026-10-03~04 에 soft-matter-agents 쪽이 먼저 정한 것(키 이름, 정지 채널, 10.2 확장)은
그쪽 커밋을 함께 적었다. 묶음 B(OD-9, 11, 14, 17, 21, 22)는 벤치 방문(B-01) 뒤에 묻는다.

| # | 질문 | 결정 |
|---|---|---|
| OD-1 | SMA 의 autofocus 좌석 이름과 번호 | `microscope-<YYYYMMDD>-<n>` 형식, 기존 `microscope-20261001-1` 행을 코드로 복사, 소유 `['microscope_agent']`; 카드에서 "autofocus 좌석" 이라 부른다. 어느 세션이 그 좌석인지는 사용자가 그 세션 창에서 말한다 |
| OD-2 | dino-autofocus 를 SMA plan.md 10.2 의 출처로 여는가 | 예, 2026-09-17 조건 그대로. **이미 기록됨**: SMA 96db738(10.2 확장, 사용자가 architecture 좌석에게 직접 진술 = OD-31) |
| OD-3 | 복사 뒤 어느 쪽이 원본인가 | (i) 복사 뒤 **SMA 가 원본**, (ii) dino 는 해시로 고정한 **읽기 전용 거울**을 남기고 표류는 `tests/test_sma_shape.py` 가 잡는다, (iii) 갱신은 SMA 의 날짜 카드로만(D-06) |
| OD-5 | 콘솔 plan 초안의 위치와 들여보내는 쪽 | 콘솔 설정 폴더 `<config_dir>/plans/drafts/<draft_id>.json`; autofocus 좌석이 제 이름으로 SMA `questions/<qid>/` 에 복사; SMA 에 새 폴더 없음; 초안 `author` 는 `human` |
| OD-6 | 초안·공개 기록의 사람 id | 승인 이름과 같은 손잡이, 그 밖은 무작위 `p-xxxxxx`; 초안·내보내기에는 id 만, 이메일은 절대 없음; 감사 기록은 지역; 손잡이가 `runs/` 에 나오는 것은 허용 |
| OD-7 | 지역 기록 git 과 SMA `runs/` | `D:\AutoFocus\records` git 이 비공개 전체 원본(푸시 안 함); SMA `runs/` 에는 좌석이 넣는 비식별화 `console.*`; 세션을 닫은 뒤 세션 화면에서 수동 내보내기(R-03 의 bench 전용 규칙) |
| OD-8 | SMA 에서 침지 렌즈의 Z 를 묶는 것 | 봉투의 **렌즈별 명시 키**(사람이 씀)와 실행 시 간극 검사 둘 다. 키 이름은 SMA 가 정한 `focus_z_<objective>_{min,max}`(e079983; 계획 행의 `z_drive_position_*` 안은 쓰지 않음); 상한은 사람이 쓰고 유도하지 않는다(250a138); 건식 렌즈의 "해제" 는 사람이 쓴 넓은 값 |
| OD-10 | 벤치의 패턴 | 표현 가능한 부분집합만(압전 한 축 구간·한 축 사인; 트랩은 `.tpf` 또는 작은 스텝 열거와 보류); 원·나선 스키마(P-04)는 첫 초점 뒤 필요할 때만; 반복과 Z 주기 운동은 언제나 거부 |
| OD-12 | `trap_move/trap_set/pattern_run` 을 mock 데모로 남기나 | 남긴다, operations-spec 에 "mock 데모" 표시 |
| OD-13 | S5 뒤 콘솔의 직접 하드웨어와 벤치 프레임 | 콘솔은 G-14 프레임 탭(SMA 0c6452d)을 쓸 때까지 mm_real 의 cfg 적재·읽기·조명(모션 없음)만; 그 전 벤치 라이브 보기 없음(한 Micro-Manager 에 코어 둘은 알려진 실패); 콘솔 mm_real 은 SMA operator 와 동시에 열지 않는다 |
| OD-15 | 콘솔이 초안을 검증해도 되나 | 콘솔 안 jsonschema 검사만(SMA `plan.schema.json` 의 읽기 전용 사본, 출처 헤더로 고정, "schema-valid (console check)" 라벨); SMA `validate.py` 는 들여보낸 뒤 그쪽에서 |
| OD-16 | `scripts/focus_servo.py` | R-05 에서 삭제(이력에 남음); 유한한 방향 찾기는 SMA G-12 의 일 |
| OD-18 | 콘솔 도구의 MCP 노출 | 이번 계획에서 제외; 뒤에 SMA architecture 가 등록하는 읽기 전용 서버로 다시 본다(C-14) |
| OD-19 | `/api/commands` 뒤의 독립 dino 엔진 | 유지(`LocalEnginePort` 로 mock/replay/mm-demo); 벤치 모션은 D-05 에서 제거 |
| OD-20 | 이번 합병의 XY 이동 | 전부 보류하고 지금 기록(G-17); scan_4x/sample_map/edge_trace/비켜서기는 B-03 뒤 XY 카드까지 mock/replay |
| OD-23 | 정지 통로 전 SMA 모드의 Abort/confirm | 정직한 이유와 함께 비활성("장비 앞 또는 operator 터미널에서"); SMA 의 정지 채널(f6c0996, 11-25 b)이 생겼으므로 C-08 에서 재활성; "Abort 는 항상 켜짐" 약속은 "지역 엔진에 한해" |
| OD-25 | `D:\AutoFocus\data`·`samples`·하드웨어 프로필과 기록 git 의 백업 | 원시 프레임은 지역 보관(SMA `runs/<run_id>/raw/` 복사는 좌석이 run 마다 결정); 샘플 폴더·하드웨어 프로필 내보내기는 보류; 기록 git 은 둘째 디스크 또는 암호화 사본으로 백업(사용자가 한다) |
| OD-26 | 시뮬레이션 화면과 PLAN 10 절 F6/F7 | 화면은 콘솔에 남고 `SmaFilesPort` 가 SMA `simulation_agent/questions`·`runs/` 를 읽음(C-03) |
| OD-27 | 콘솔 제목과 문서의 랩 이름 | 콘솔 제목은 중립("Autofocus Console")으로 바꾼다; 문서의 랩 이름은 결정 P3 대로 유지 |
| OD-28 | 공개 트리의 언어 | 설계 문서는 한국어 그대로; README 에 영어 한 단락과 "설계 문서는 한국어" 표시; SMA 독자용 영어 요약은 이 문서 첫머리 |
| OD-29 | `map_*.py` 를 첫 복사에 넣나 | 빼고 보류(SMA 10.2 도 같은 판정: 샘플 맵 자리가 없다); 첫 복사는 `focus_classical`·`focus_verdict`·`focus_search` 와 그 테스트(SMA 카드 059, dino b802837) |
| OD-30 | D14(뷰어가 끊기면 자동 중단)를 SMA 가 돌리는 plan 에도 | 지금은 **적용하지 않는다**(SMA 의 임시 기본값과 같다: 뷰어가 끊겨도 run 은 계속, f297a28); 정지 채널을 hw_port 가 쓰게 되면 다시 정한다 |

## 8. 측정이 먼저인 것 (현미경 PC)

과제 018 §6 과 이 저장소 BACKLOG 의 벤치 항목이 겹친다. 한 번의 벤치 방문으로 양쪽을 채운다:
픽셀 크기, 방식별 through-focus 곡선, 계면 오프셋, PFS 오프셋 부호, 동초점 잔차 (4x→100x 약 −60 µm, 재측정 필요),
40x WI 0.17 mm 칼라에서의 작동 거리, Q13 (접근 스텝), Q20 (Z 후퇴가 필요한 XY 이동), 재물대 한계, 무명령 Z 표류
(485.16 → 483.62 µm). 결과는 이 저장소 `docs/runs/` 와 그쪽 라이브러리언에 각각 들어간다.

## 9. 폴더 구조 (Q2, 초안 2026-10-02)

추가 결정 (사용자, 2026-10-02, 이 절의 초안을 본 뒤):
- **동작은 plan 으로만.** 합친 뒤 화면은 plan 초안을 만들고, 사람이 승인하면 그쪽 operator/orchestrator 가 실행한다.
  화면이 직접 장비를 움직이지 않는다. S5 의 `hw_port` 는 이 모양 (plan 제출, run 읽기) 을 목표로 한다.
- **화면 (server, web, launcher) 은 이 저장소에 남는다.** 그쪽으로 옮기는 것은 `microscope_agent/` 쪽 (초점·맵 핵심) 뿐이다.
  아래의 `console/` 은 이 저장소 안의 위치이고, 그쪽에 새 최상위 폴더를 만들지 않는다 (ALLOWED_PATHS 승인 불필요).
- **기록은 모두 그쪽 `runs/` 로.** 그쪽 `runs/` 는 공개되므로, 넘기기 전에 이메일·이름 같은 개인 정보를 빼야 한다
  (사용자 id 를 불투명한 값으로 바꾸는 설계가 필요, 새 과제). 관리자 이메일은 지금처럼 git 밖에 둔다.
- **scipy 는 numpy 로 바꾼다** (`separated_peaks`). 초점 핵심은 numpy 만 쓴다.


그쪽 규칙에서 나오는 제약 (soft-matter-agents `baf6f1e`, `contracts/validate.py`):
- check 13: 에이전트 `src/` 는 평평한 파일 또는 `src/devices/<file>` 만. `tests/` 는 평평한 `*.py` 만 (fixture 폴더 없음).
- 그쪽 모듈은 패키지 import 가 아니라 **경로로 형제 파일을 불러온다** (`spec_from_file_location`, 예 `axis_a1_snr.py:44`).
  테스트는 `unittest`, conftest 없음.
- check 82: 함수 안 import 까지 본다. `scipy` 는 `sim` 기능에만 있어 검사는 통과하지만 현미경 PC 의 `mic` 환경에는 없다.
  `focus/classical.py` 의 `separated_peaks` (`scipy.signal.find_peaks`) 는 그 환경에서 실행 중 실패한다.
- 그쪽에는 UI·서버 폴더가 없다. 새 최상위 폴더는 architecture (ALLOWED_PATHS, pixi) 와 manager (AGENT_OF_PATH) 승인이 먼저다.

대응표 (요약):

| 이 저장소 | 그쪽 위치 | 처리 |
|---|---|---|
| `focus/classical.py`, `verdict.py`, `sma_event.py` | `microscope_agent/src/focus_classical.py`, `focus_verdict.py` | 옮김 (경로 로더, scipy 제거) |
| `focus/dino.py`, `live.py`, `backbone.py` | 나중에 `focus_dino.py` (shadow mode, torch 는 `mic` 에) | 2단계 |
| `guards.py` 의 Z 규칙 (상향 스윕, 읽기 확인, PFS 먼저 끔, 후퇴 0, 큰 XY 전 후퇴) | `focus_step_rules.py` (순수 함수, 한계는 envelope 에서 인자로) | 순수 부분만 |
| `focus_100x.py` 의 단계 생성 | `focus_search.py` (단계마다 `from`) | 나눔 |
| `mosaic.py`, `sample.py`·`scan_4x.py`·`sample_map.py` 의 순수 부분, `edge_trace.py` 검출부 | `map_mosaic.py`, `map_geometry.py`, `map_tiles.py`, `map_edge.py` | 나눔 |
| `runner`, `backend`, `events`, `records`, `gates`, 나머지 가드와 숫자 표, `objective_change`, `z_retract`, `light_set` | orchestrator, operator, envelope, `runs/<run_id>/` | 이 저장소에만 남음 (단독 실행용) |
| `mm_real.py`, `mm_demo*.py` | `devices/micromanager.py` 에 흡수 | 합칠 때 버림 |
| `server/`, `auth/`, `assistant/`, `agents/`, `web/`, `tools/launcher/` | 새 최상위 `console/` (`sma_console` 패키지, `console/web`, `console/launcher`) | 옮김 |
| `synth/`, 학습·평가 스크립트, `models/`, `configs/ti2_*.yaml` | 옮기지 않음 (모델 제작용으로 이 저장소에 남음) | 남음 |

이 저장소 안의 중간 배치 (그쪽을 그대로 닮게):

```
microscope_agent/src/        focus_*.py map_*.py   (평평, __init__.py 없음, stdlib + numpy 만)
microscope_agent/src/devices/
microscope_agent/tests/      test_focus_*.py ...   (평평, unittest, 경로 로더)
console/sma_console/         app ws static hw_port api/ schemas/ auth/ assistant/ store/
console/web/  console/launcher/  console/tests/
src/dino_autofocus/          단독 실행용 나머지 (engine, backends, operations, records, synth, live, backbone)
```

배포는 하나로 유지한다 (`uv sync`, editable 설치, pytest 그대로). `dino_autofocus.focus` 는 평평한 파일을 다시 내보내는
얇은 껍데기로 남겨 기존 import 를 살린다. `tests/test_sma_shape.py` 가 옮길 두 폴더에 check 13·16·82 를 미리 적용한다.

단계 (각 단계 끝에 테스트 통과):
- S0 (P1 완료) 의존성 나누기. S3 (P3 완료) 판정 → run_log 이벤트.
- S1 (완료) 초점 핵심을 `microscope_agent/src/` 로 (`focus_classical`, `focus_verdict`, `focus_run_log`), scipy 제거,
  `tests/test_sma_shape.py`. 옛 이름 `dino_autofocus.focus.{classical,verdict,sma_event}` 은 같은 모듈 객체로 남는다.
- S2 순수 핵심 파일을 하나씩 (`focus_step_rules`, `focus_search`, `map_*`). 옛 모듈은 같은 객체를 다시 내보낸다.
  - `map_geometry` (완료): 픽셀 ↔ 스테이지 (`stage + inv(M) @ (centre - p)`), `calibration_of`, `sample.py` 의 geometry 필드·검증·view, `hole_loop`.
  - `map_mosaic` (완료): `mosaic.py` 전부 (scipy 필터 → numpy, scipy 와 비트 단위로 같음). `mosaic_from_scan` 은 guards 의 `registry_key` 를 써서 옛 모듈에 남음.
  - `map_tiles` (완료): 뱀 모양 타일 순서, 스캔 사각형, `fit_plane` / `plane_z`, 카메라 보정 기본값 (`scan_4x.py`, `sample_map.py`). 허용 XY 상자는 guards (`XYBox.around`) 라 남음.
  - `map_edge` (완료): `edge_trace.py` 의 검출부 (`find_edge`, 원 맞춤, `hole_fit`); `remove_small_regions` 의 scipy label → numpy run 묶기 (같은 영역).
  - `focus_search` (완료): `focus_100x.py` 의 인자, 중심, coarse·fine·위로 늘리기 구간, 피크 위치, 경고 규칙, `sweep_z` (한계는 인자, guards 의 `FocusAxis.plan` 과 같은 Z). 실제 계획·검사는 guards 에 남음.
  - `focus_step_rules` (완료 2026-10-03, 순수 파일만; 작업계획 D-01): Z 창·후퇴·복귀·읽기 허용·렌즈별 작동 거리·긴 이동
    문턱·접근 스텝을 모두 **인자로** 받는 규칙 함수(상향 스윕, 읽기 확인, 상승 확인, 접근 단계 열거, 스윕·접근 상한,
    PFS 꺼짐·범위 밖, 터릿 회전 조건, 긴 XY 이동 전 후퇴 — Q4 의 건식 렌즈 해제 포함, 모델 등급 거부)와 평탄 unittest.
    **D-01b (완료 2026-10-03)**: `guards.py` 가 규칙 20 개 중 16 개를 비교 시점에 호출한다 (한계·백엔드 호출·기록·벤치
    잠금은 그대로 guards 에). 위임하지 않은 넷 — `approach_steps`(접근의 다음 목표는 읽기값에서 나온다),
    `needs_retract_before_xy`(D-04 의 렌즈 종류가 필요; 지금은 모든 렌즈를 표의 행으로 묶음), `pfs_quiet`·
    `pfs_out_of_range`(`nosepiece_turn_allowed` 안에서 쓰임). 엄격해진 것 하나: PFS 상태를 읽지 못하면 터릿 회전을
    거부한다 (전에는 켜진 상태만 거부). `tests/engine/test_guards_delegation.py` 가 거부 문장이 평탄 규칙의 문장과
    같음을 고정한다.
  - D-02 (완료 2026-10-03, 작업계획 `integration-sma-workplan.md`): 평탄 파일의 벤치·튜닝 숫자(스윕 중심 2930, 동초점
    −60, 암전 102, 신호 바닥 50, 노출 20, 스팬 40/2/3/0.2, 판정 문턱 20/0.05/3/1.0/3.0, 포화 0.001, 드롭아웃 0.02,
    이중 피크 0.2, 4x 보정 1.625 와 행렬)를 `src/dino_autofocus/bench_values.py` 로 옮기고 함수 인자로 받게 함;
    `tests/test_sma_shape.py` 가 파일별 숫자 리터럴 허용 목록 밖의 숫자를 거부한다.
  - D-03 (완료 2026-10-03): 평탄 src·test 파일마다 출처 헤더 세 줄 — `# origin: dino-autofocus, public since
    2026-10-03:`, 공개 URL `https://github.com/kyu-softmatter/dino-autofocus/blob/<commit>/<path>`,
    `# body-sha256: <헤더 아래 본문의 해시, 줄끝 LF 로 정규화>`. `<commit>` 은 그 본문이 처음 들어간 커밋이라
    본문을 고치면 커밋 둘(본문, 그 커밋을 적는 헤더)이 필요하고 그 사이 `tests/test_sma_shape.py` 가 실패한다
    (`python -m dino_autofocus.flat_origin --check` / `--commit <sha>`). 평탄 파일 안의 `dino_autofocus`·
    `scripts/`·`docs/` 토큰 금지(복사 뒤 다른 뜻이 됨), 거울이 따르는 SMA 커밋 고정(`SMA_SHAPE_COMMIT`), 옆에
    soft-matter-agents 체크아웃이 있으면 읽기만으로 표류 검사(고정 커밋이 이력에 있는지, 검사 13·16·82 가 아직
    있는지, 양쪽에 다 있는 파일의 본문이 같은지). 복사 뒤에는 헤더가 soft-matter-agents 를 가리키게 돌린다(D-06).
- **거울 규칙 (OD-3, 사용자 2026-10-05; 작업계획 G-06·D-06)**: soft-matter-agents 가 카드 059 로
  `focus_classical`·`focus_verdict`·`focus_search` 와 그 테스트 셋(`test_focus_core`·`test_focus_contract`·
  `test_focus_search`)을 dino 5cc5057 에서 바이트 그대로 복사했다(SMA f2c56dc). **이제 이 여섯 파일은 SMA 가
  원본이고, dino 의 `microscope_agent/` 사본은 고정된 읽기 전용 거울이다.** 헤더는
  `# origin: soft-matter-agents, ...` 와 SMA 커밋의 공개 URL 을 적는다(`flat_origin.MIRRORED`,
  `SMA_MIRROR_COMMIT`). 이 파일을 고칠 일은 SMA 에서 먼저(카드로) 하고, dino 는 그 커밋의 본문을 받아
  `python -m dino_autofocus.flat_origin --mirror <sha>` 로 헤더를 다시 가리킨다. `tests/test_sma_shape.py` 가
  SMA 체크아웃에서 그 커밋의 본문과 같은지 본다. 나머지 평탄 파일(`focus_step_rules`, `focus_run_log`,
  `focus_verdict_model`, `map_*`)은 dino 가 원본으로 남는다.
- **XY 보류 (OD-20, 사용자 2026-10-05; 작업계획 G-17 앞 절반)**: 이번 합병에서 XY 는 아무것도 넘어가지 않는다.
  `scan_4x`, `sample_map` 의 `goto_xy`, `edge_trace`, `objective_change` 의 +Y 비켜서기는 합친 뒤에도 dino 의
  mock/replay 전용이다. soft-matter-agents 에 XY plan 모양, 예외, 봉투 키를 요청하지 않는다. 침지 렌즈의 긴 XY
  이동 전 후퇴 표(`guards.OBJECTIVE_LIMITS.long_xy_um`, Q4)는 dino 에 남고, 질문 카드 L-019·L-020 이 그 값을
  사람에게 묻는다. XY 설계(작업계획 G-17 뒤 절반: `motor_stage` 스텝, `motor_stage_{x,y}_position_min/max`,
  후퇴 검증 인터락)는 B-03 뒤 SMA 의 일이다.
- S4 `console/` 로 서버·웹·런처 옮기기 (import 약 100 곳, gen:api, 런처 경로).
- S5 `hw_port.py`: 화면이 엔진을 직접 부르지 않고 포트 하나로 (그 뒤 console 은 `dino_autofocus` 를 import 하지 않는다).
- S6 합치는 주: 그쪽 승인 순서 (사람: 좌석 → architecture: seats.json, pixi, ALLOWED_PATHS 명세 → manager: validate.py →
  manager-microscope: 과제 카드, plan.schema, envelope 스키마) 를 마친 뒤 복사. 승인 사슬이 길어 **2주차에 시작**한다.
