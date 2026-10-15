# 기록의 개인 정보 (공개 runs/ 로 넘기기 전, 초안 2026-10-02)

사용자 결정 (2026-10-02, integration-sma.md 9절): **실험 기록은 모두 soft-matter-agents 의
`microscope_agent/runs/<run_id>/` 로 간다.** 그 저장소는 공개이므로 이메일·이름 같은 개인 정보는 넘기기 전에
빼거나 바꾼다. 관리자 이메일은 지금처럼 git 밖 (설정 폴더, 환경 변수) 에만 있다. 이 문서는 무엇이 남고 무엇이
건너가는지, 사람을 어떤 id 로 바꾸는지, 내보내기 단계의 모양을 정한다. 구현:
`src/dino_autofocus/records/redact.py` (바꾸기와 검사) 와 `records/export.py` (내보내기, 6절의 결정대로). 둘 다 표준
라이브러리만 쓰고, 기록을 쓰는 방식은 바꾸지 않았다.
근거: 이 저장소 `1302694`, soft-matter-agents `baf6f1e` (읽기만).

## 1. 지금 쓰는 기록과 개인 정보 (목록)

사용자 id 는 계정 이메일이다 (D9). 아래 "사람" 은 이메일 또는 그것에서 나온 값이다.

| 파일 (위치) | 개인 정보 필드 | 근거 |
|---|---|---|
| `session.json` (세션 폴더) | `user_id` (이메일), `user_name` (실명), `session_id` 안의 이메일 앞부분, `code.repo` (경로, 개발 PC 면 `C:\Users\<이름>` 가능), `hardware_profile.path`, `continues` (앞 세션 id), `close_note` (자유 글) | `records/session.py:69,74,79,90,132`, `records/codeversion.py:15,41` |
| 세션 id 와 폴더 이름 `<YYYYMMDD-HHMM>-<slug(이메일)>-<n>` | 이메일 앞부분 (local part). 모든 줄의 `session_id`, 데이터 폴더 `data/<session_id>/`, manifest 의 data 경로, 커밋 메시지에 퍼진다 | `records/session.py:90,270`, `records/layout.py:113`, `records/manifest.py:68-69` |
| `log/session.jsonl` | 줄마다 `user_id`, `commit failed` 줄의 git 오류 글 (경로가 들어갈 수 있음) | `records/session.py:260,280` |
| `records/<op>.jsonl` (세션 안 작업 기록) | 줄마다 `user_id`, `operation_started` 의 `user_id`·`confirmed_by`, 엔진 이벤트 `data.by` (confirm, update, approve, reject), 끝 요약의 `confirmed_by`, `trigger` (abort 한 사람) | `server/app.py:215`, `engine/runner.py:259,870,891,894,914,953,967` |
| `records/manual_steps.jsonl` | `user_id`, 사람이 쓴 메모 | `records/session.py:206,260` |
| `records/sample_events.jsonl` | `user_id`, flag 이름·메모, `note` 글. 접으면 `history[].by` | `records/events.py:45,75,100,106` |
| `manifest.json` | data 경로 안의 세션 id, 사람이 고른 첨부 파일 이름 | `records/manifest.py:69,73` |
| 기록 저장소의 git 이력 (로컬) | 커밋 작성자 = 실명 + 이메일 | `records/store.py:29-32,113` |
| 세션 밖 작업 기록 `data/engine_records/<op>_<stamp>/` 와 샘플 폴더 `samples/<id>/<op>_<stamp>/` | `summary.json` 의 `user_id`·`result.confirmed_by`, `log.jsonl` 의 Event `user_id`, `started` 이벤트의 `user_id` | `engine/records.py:99`, `engine/runner.py:246,1079,1454`, `engine/operations/sample_ops.py:335,337`, `server/__main__.py:311` |
| 하드웨어 프로필 `microscope/hardware/` | `host` (PC 이름), `confirmed.<항목>.by` | `engine/operations/hardware_scan.py:155,312`, `engine/gates.py:104-106` |
| 가짜 라이브러리언 `librarian/reflected.jsonl`, `samples/<id>.json` | `user_id`, 접은 상태의 `history[].by` | `records/librarian_mock.py:71`, `records/events.py:106` |
| 어시스턴트 기록 `assistant.jsonl` (`DINO_AF_ASSISTANT_RECORDS`) | `user_id`, 질문 글, 화면 문맥, 답 글 | `assistant/records.py:52-65`, `assistant/runner.py:82,290` |
| 계정 `accounts.json` (설정 폴더) | 이메일, 실명, 비밀번호 해시, 승인한 관리자 이메일 | `auth/accounts.py:68-76` |
| 감사 로그 `audit.jsonl` (설정 폴더) | `user_id`, `account`, `name`, `holder`, `login_id`, 어시스턴트 질문·답 글 복사 | `auth/audit.py:92-98`, `auth/accounts.py:212-345`, `auth/logins.py:128-241`, `auth/control.py:103-149`, `server/api/assistant.py:168-181` |
| 앱 로그 `logs/app-*.log` (설정 폴더) | 서버 메시지 (이메일이 섞일 수 있음) | `auth/applog.py` |

IP 주소는 어디에도 쓰지 않는다 (loopback 판정에만 쓰고 버림, `server/api/__init__.py:218`).

## 2. 남는 것과 건너가는 것

- **로컬에만 (건너가지 않음)**: 계정, 감사 로그, 앱 로그, 어시스턴트 대화 (`assistant.jsonl`), 사람 대응표
  (3절), 기록 저장소의 git 이력 (작성자 이메일). 이 파일들은 내보내기 단계가 읽지도 않는다.
- **건너감 (바꾼 뒤)**: 세션 폴더의 JSON / JSONL (`session.json`, `manifest.json`, `log/session.jsonl`,
  `records/*.jsonl`). 사람은 person id 로, 세션 id 의 사용자 부분도 person id 로.
- **빠짐**: `user_name`, `login_id`, `control_grant`, 매핑되지 않은 `host`. JSON 이 아닌 첨부
  (`files/*`) 는 복사하지 않고 목록만 돌려준다 (manifest 에 크기와 해시가 남는다). 큰 데이터 (`data/`) 는 지금처럼
  git 밖이고, 그쪽도 프레임은 저장소 밖에 둔다.

## 3. person id

- 사람마다 **짧은 공개 id** 하나: `^[a-z][a-z0-9-]{1,31}$`. 그쪽은 이미 `approved_by: "kyuhwan"`,
  `who: "kyuhwan"` 처럼 사람이 정한 짧은 이름을 공개로 쓴다 (`microscope_agent/approvals/*`,
  `contracts/examples/plan_approval.json`). 같은 사람은 그쪽 승인 카드와 같은 id 를 쓰는 것이 권고다
  (run 과 승인을 사람으로 이을 수 있다). 정하지 않은 사람은 무작위 `p-xxxx` 를 한 번 만들어 둔다
  (이메일 해시는 쓰지 않는다: 연구실 사람 목록으로 되짚을 수 있다).
- 대응표 `people.json` 은 **설정 폴더** (`accounts.json` 옆, git 밖) 에 둔다:
  `{"persons": [{"person_id", "email", "name", "aliases"}], "hosts": {"<PC 이름>": "<라벨>"}}`.
  `aliases` 는 메모에 쓰이는 별명. 이 파일은 내보내기만 읽는다.
- **바꾸는 때는 내보낼 때다. 쓸 때가 아니다.** 로컬 기록은 계정 id 그대로 남아 화면, 세션 목록, 라이브러리언이
  지금처럼 쓴다. 대응표를 바꾸면 다음 내보내기부터 바뀐다 (이미 내보낸 것은 공개 저장소의 이력에 남는다).

## 4. 바꾸기 규칙 (`records/redact.py`)

모든 문자열 (키와 값) 에 차례로: 매핑된 이메일 → id (대소문자 무시, 전각 `＠` 포함), 홈 폴더
(`C:\Users\<이름>`, `C:/Users/<이름>`, `/mnt/c/Users/<이름>`, `/home/<이름>`) → `~`, 이름과 별명 (단어 단위,
대소문자 무시) → id, 세션 id 의 사용자 부분 → id, 매핑된 PC 이름 → 라벨.

그 뒤 검사해서 **하나라도 남으면 세션 전체를 거부한다** (`RedactionRefused`): 이메일 모양 문자열, 홈 폴더 경로,
매핑된 이름·별명, 사용자 부분이 person id 가 아닌 세션 id, 사람 필드 (`user_id`, `by`, `confirmed_by`,
`approved_by`, `account`, `holder`) 의 값이 person id 도 행위자 (`assistant`, `system`, `engine`) 도 아닌 것.
거부 메시지는 파일과 위치와 종류만 말하고 값은 말하지 않는다.

한계: 대응표에 없는 이름이나 별명이 메모에 있으면 찾지 못한다. 그래서 자유 글을 넘길지가 질문 2 다.

## 5. 내보내기 단계 (`records/export.py`, 2026-10-02 구현)

```
  closed 세션 + people.json --redact_session--> 바뀐 사본 (메모리) --> runs/<run_id>/console.*
```

1. `closed` 이고 모두 커밋된 세션만 (라이브러리언과 같은 조건). `session.json` 의 `bench` 가 **정확히 `true`** 인
   세션만 내보낸다 (R-03): `false` (mock·시뮬레이션) 도, 값이 없는 옛 세션도 거부한다. `bench` 와 `backend_kind` 는
   세션을 열 때 엔진의 백엔드 정보에서 기록한다 (T-106b). run id 는 그쪽 `runs/` 폴더 이름 규칙(소문자·숫자·`-`,
   64 자 이하) 을 따르며, `console.*` 문서에는 `card`/`artifact` 최상위 키가 들어가지 않는다 (그쪽 검증기가 카드로 읽는다).
2. `redact_session(세션 폴더, 대응표)` 가 거부하면 아무것도 쓰지 않고 이유를 화면과 앱 로그에 남긴다.
3. 이름: 그쪽 `contracts/validate.py:1613` 은 `runs/<run_id>/` 아래에 평평한 이름 (`[A-Za-z0-9_.-]+`)
   과 `raw/...` 만 받는다. 그래서 `console.session.json`, `console.manifest.json`, `console.log.session.jsonl`,
   `console.records.<op>.jsonl` 로 편다 (`RedactedSession.flat_files`). `log.json` (run_log 스키마) 은 그쪽
   operator 가 쓰는 파일이라 이 단계가 만들지 않는다.
4. 그쪽 저장소에는 이 저장소가 쓰지 않는다 (PLAN 5절). 통합 뒤 쓰는 쪽은 그쪽 좌석이고, 이 단계는 바뀐 사본을
   넘겨주는 함수까지다. 세션의 `sma_run_id` 에 연결을 남긴다.
5. 샘플 폴더, 하드웨어 프로필, 세션 밖 작업 기록은 같은 규칙으로 따로 넘길 수 있게 하되 지금은 범위 밖이다
   (`scan.json` 의 `light_off.by` 처럼 사람이 아닌 값이 사람 필드에 들어간 곳이 있어 먼저 고쳐야 한다,
   `engine/operations/scan_4x.py:567`).

## 6. 사용자 결정 (2026-10-02, 모두 권고안)

1. **person id**: 사람이 정한 짧은 이름 (그쪽 승인 카드와 같은 것, 예 `kyuhwan`). 정하지 않은 계정은
   `assign_person_ids` 가 무작위 `p-xxxxxx` 를 한 번 만들어 `people.json` 에 저장하고, 이미 준 id 는 바꾸지 않는다.
   실명의 일부를 id 로 쓸지는 사람마다 정한다 (`people.json` 을 고쳐서).
2. **자유 글**: 검사 뒤 넘긴다. 대응표에 없는 이름은 찾지 못한다는 한계를 안고.
3. **어시스턴트 대화 글**: 로컬에만. 세션 폴더에 `assistant.jsonl` 이 있어도 읽지 않는다 (`redact.LOCAL_ONLY`,
   결과의 `kept_local` 에 이름만 남는다).
4. **세션과 run**: 그쪽 run 폴더 (`log.json` 이 있는 곳) 옆에 `console.*` 로 붙인다. `export_session` 은
   `session.json` 의 `sma_run_id` (또는 인자 `run_id`) 를 쓰고, 없으면 거부한다. 이 저장소는 그쪽에 쓰지 않으므로
   로컬 준비 폴더 `<out_dir>/<run_id>/console.*` 와 `console.export.json` (파일별 sha256) 을 만들고, 그쪽이 복사한다.
   열린 세션, `bench` 가 `true` 가 아닌 세션, 규칙에 안 맞는 run id, 이미 파일이 있는 run 은 거부하고, 거부하면 아무것도 쓰지 않는다.

남은 일: `session.json` 에 `bench` 를 넣는 것 (T-106b, 지금은 값이 없으면 내보낸다), 세션에 `sma_run_id` 를 붙이는
때 (통합 뒤, 그쪽 plan 이 실행될 때), 샘플 폴더·하드웨어 프로필·세션 밖 작업 기록 (5절 5).
