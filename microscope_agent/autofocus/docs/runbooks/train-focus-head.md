# 런북: DINO 초점 헤드 학습 (현미경 PC 전용)

- 대상 컴퓨터: **현미경 PC** (Windows, RTX A4000). PLAN.md 4절에 따라 이미지 합성과 DINO 학습은
  이 PC 에서만 한다. 개발 데스크톱(GTX 1650 SUPER)에서는 이 런북의 명령을 실행하지 않는다.
- 실행하는 사람: 사용자. 개발 세션은 이 문서를 고치기만 하고 명령을 돌리지 않는다.
- 작성: AF 실행2 (T-003), 2026-10-01. 근거 파일은 각 절 끝에 적었다.
- 결과물: `outputs/heads/head_<data>_<backbone>.npz` (라이브 뷰가 읽는 피클 없는 헤드), `.joblib` (재학습용
  파이프라인, 저장소에 넣지 않는다), `.json`. 검토 후 `.npz` 와 `.json` 만 `models/heads/` 로 옮긴다.

학습된 헤드의 출력은 **모델 숫자**다. 초점 판정(`dino_autofocus.focus.verdict`)에서 grade
`"model"` 로 기록되고, 모션 한계나 안전 판단에는 쓰이지 않는다 (PLAN.md 6절).

## 0. 시작 전에

- 하드웨어 작업 중에는 돌리지 않는다. 데이터셋 생성은 CPU 와 메모리를 다 쓰고, 특징 추출은 GPU 를
  쓴다. 라이브 뷰나 스캔이 같은 PC 에서 돌고 있으면 프레임 지연과 크래시 위험이 있다.
- 작업 폴더는 현미경 PC 의 클론이다. 2026-09-30 기준 `D:\AutoFocus\dino-autofocus`.
- 디스크: 합성 데이터와 특징 캐시는 `data/` 아래에 쌓인다 (git 밖). 수 GB 를 확보한다.

## 1. 환경

```
cd D:\AutoFocus\dino-autofocus
git pull
uv sync
```

`uv sync` 가 torch cu126 을 받는다. DINOv2 코드는 저장소 옆의 고정 커밋 클론에서 읽는다.
다른 위치라면 `DINOV2_REPO` 환경 변수로 지정한다.

```
git clone https://github.com/facebookresearch/dinov2 ..\dinov2
git -C ..\dinov2 checkout 7764ea0f912e53c92e82eb78a2a1631e92725fc8
```

확인:

```
uv run python -c "import torch; print(torch.__version__, torch.cuda.get_device_name(0))"
uv run pytest tests/test_backbone.py -q
```

`DinoExtractor` 는 클론의 HEAD 가 `7764ea0` 이 아니면 실행을 거부한다.
`tests/test_backbone.py` 는 전처리만 시험하고 모델을 읽지 않으므로, 클론과 가중치는 1.2절로 확인한다.

**DINOv2 가중치는 처음 쓸 때 인터넷에서 받는다** (1.1절). 현미경 PC 가 오프라인이면 1.1절 표의
파일을 미리 `~/.cache/torch/hub/checkpoints` (Windows: `%USERPROFILE%\.cache\torch\hub\checkpoints`,
`TORCH_HOME` 이 있으면 그 아래 `hub\checkpoints`) 에 복사해 둔다 (1.2절). 1.2절 4번의 한 줄 확인으로
파일이 그 자리에 있는지 본다.

근거: `docs/setup-new-pc.md` 2–3절, `src/dino_autofocus/backbone.py`.

### 1.1 가중치는 어디서 오는가

`DinoExtractor` 는 `torch.hub.load(<클론>, "dinov2_vits14", source="local")` 로 모델 코드를 클론에서
읽는다. 코드는 인터넷에 가지 않지만, **사전학습 가중치는 처음 만들 때 인터넷에서 받는다**
(클론의 `dinov2/hub/backbones.py`, `dinov2/hub/utils.py`, 커밋 `7764ea0` 기준):

- URL: `https://dl.fbaipublicfiles.com/dinov2/<모델>/<모델>_pretrain.pth`
- 받는 함수: `torch.hub.load_state_dict_from_url`. 해시 검사는 꺼져 있다 (`check_hash=False`).
  파일 이름에 해시가 없어서, 잘린 파일이나 다른 파일이 있어도 torch 가 알아채지 못한다.
- 저장 폴더: `<TORCH_HOME>\hub\checkpoints\`. 파일이 이미 있으면 받지 않는다.
  - `TORCH_HOME` 이 없으면 `%XDG_CACHE_HOME%\torch`, 그것도 없으면 `%USERPROFILE%\.cache\torch`.
  - 현미경 PC 의 실제 폴더는 이 명령으로 본다 (아무것도 받지 않는다):

    ```
    uv run python -c "import torch; print(torch.hub.get_dir())"
    ```

    출력 뒤에 `\checkpoints` 를 붙인 곳이 가중치 폴더다.

이 저장소가 쓰는 파일:

| 모델 | 쓰는 곳 | 파일 이름 | 크기 (바이트) | SHA-256 |
|---|---|---|---|---|
| `dinov2_vits14` | 학습, 평가, 라이브 뷰 헤드 (기본값) | `dinov2_vits14_pretrain.pth` | 88,283,115 | `b938bf1bc15cd2ec0feacfe3a1bb553fe8ea9ca46a7e1d8d00217f29aef60cd9` |
| `dinov2_vitb14` | `bench_latency.py` 만 | `dinov2_vitb14_pretrain.pth` | 346,378,731 | `0b8b82f85de91b424aded121c7e1dcc2b7bc6d0adeea651bf73a13307fad8c73` |

크기와 해시는 개발 데스크톱 캐시(`%USERPROFILE%\.cache\torch\hub\checkpoints`, 2026-09-30 에 받음)의
파일에서 쟀다. 배포처가 공개한 값이 아니라, 이 저장소 결과를 만든 파일의 값이다.

### 1.2 현미경 PC 가 오프라인일 때

인터넷이 되는 PC (예: 개발 데스크톱) 에서 아래 두 가지를 USB 등으로 옮긴다. 개발 세션은 이
복사를 대신하지 않는다. 사용자가 한다.

**가중치 파일**

1. 인터넷 되는 PC 의 캐시 폴더에서 1.1절 표의 파일을 복사한다. 데스크톱에는 이미 있다.
   없으면 그 PC 에서 URL 로 직접 받는다.
2. 현미경 PC 에서 `torch.hub.get_dir()` 출력 아래 `checkpoints` 폴더를 만들고 그 안에 넣는다.
   파일 이름을 바꾸지 않는다. torch 는 URL 끝의 파일 이름으로 캐시를 찾는다.
3. 크기와 해시를 표와 비교한다 (PowerShell):

   ```
   Get-Item <checkpoints 폴더>\dinov2_*_pretrain.pth | Select-Object Name, Length
   Get-FileHash -Algorithm SHA256 <checkpoints 폴더>\dinov2_*_pretrain.pth
   ```

   하나라도 다르면 쓰지 않고 다시 복사한다.

4. 가중치만 한 줄로 확인한다. 네트워크, 클론, GPU 없이 되고, 아무것도 받지 않고 폴더만 읽는다:

   ```
   uv run python -c "import torch, pathlib; d = pathlib.Path(torch.hub.get_dir(), 'checkpoints'); print(d); [print(n, (d / n).stat().st_size if (d / n).exists() else 'MISSING') for n in ('dinov2_vits14_pretrain.pth', 'dinov2_vitb14_pretrain.pth')]"
   ```

   폴더 경로 뒤에 두 파일과 크기가 나온다. 크기가 1.1절 표와 같으면 제자리에 있고, `MISSING` 이면
   그 파일이 없다. `dinov2_vitb14_pretrain.pth` 는 `bench_latency.py` 에만 필요하다.
   개발 데스크톱에서 2026-10-02 에 돌렸을 때 `%USERPROFILE%\.cache\torch\hub\checkpoints` 와
   표의 크기 두 개(88283115, 346378731)가 나왔다.

   파일 이름은 코드가 정한다. 클론의 `dinov2/hub/utils.py` 의 `_make_dinov2_model_name` 이
   `dinov2_<arch 앞 4자><patch>` 를 만들고, `dinov2/hub/backbones.py` 가 그 뒤에 `_pretrain.pth` 를
   붙인다. 이 저장소의 기본 모델은 `src/dino_autofocus/backbone.py` 의 `dinov2_vits14` 다.

**DINOv2 클론** (커밋 `7764ea0`)

1. 인터넷 되는 PC 에서 1절의 `git clone` 과 `git checkout` 을 한다 (데스크톱에는
   `D:\codes\github\dinov2` 에 이미 있다).
2. 폴더를 **`.git` 까지 통째로** 현미경 PC 의 저장소 옆 (`D:\AutoFocus\dinov2`) 으로 복사한다.
   `DinoExtractor` 는 `git rev-parse HEAD` 로 커밋을 확인하므로 `.git` 이 없거나 현미경 PC 에
   `git` 이 없으면 실행을 거부한다. 다른 위치에 두면 `DINOV2_REPO` 로 지정한다.
3. 확인:

   ```
   git -C ..\dinov2 rev-parse HEAD
   ```

   `7764ea0f912e53c92e82eb78a2a1631e92725fc8` 이어야 한다.

**함께 확인** (네트워크를 끈 채로. 가중치가 없으면 받으려다 실패하므로 빠진 것이 드러난다):

```
uv run python -c "from dino_autofocus.backbone import DinoExtractor; print(DinoExtractor().dim)"
```

`768` (ViT-S/14, 마지막 블록 1개의 CLS + 평균 패치) 이 나오면 클론과 가중치가 모두 제자리에 있다.
`bench_latency.py` 를 돌릴 계획이면 `dinov2_vitb14_pretrain.pth` 도 같은 폴더에 있어야 한다.

`uv sync` 의 패키지 내려받기도 인터넷이 필요하다. 이 절은 가중치와 클론만 다룬다.

근거: `src/dino_autofocus/backbone.py`, 클론의 `hubconf.py`, `dinov2/hub/backbones.py`,
`dinov2/hub/utils.py`, `scripts/bench_latency.py`.

## 2. 합성 데이터셋 생성

현재 헤드(`models/heads/head_k100x_dinov2_vits14_L1.npz`)는 100x 오일 형광 합성 세트
`k100x` 로 학습됐다. 같은 조건으로 다시 만들거나 장면 수를 늘릴 때:

```
uv run python scripts/make_dataset.py --out data/k100x --system-config configs/kinetix_100x_oil.yaml --fov 224 --planes 17 --workers 8
```

주요 인자:

| 인자 | 뜻 | 메모 |
|---|---|---|
| `--scenes` | 장면 수 (기본 400) | 장면마다 z 스택 1개 |
| `--seed0` | 첫 장면 시드 | 세트를 늘릴 때 겹치지 않게 바꾼다 |
| `--fov 224` | 시야 픽셀 | 헤드의 타일 크기 224 와 맞춘다 |
| `--planes` | 장면당 평면 수 | `synthetic-results.md` 는 17 |
| `--workers` | 장면 단위 프로세스 수 | 아래 메모리 주의 |
| `--device cuda --gpu-dtype complex64` | PSF 계산을 GPU 로 | 프로세스마다 CUDA 컨텍스트를 잡으니 workers 를 적게 |

**메모리 주의**: 개발 데스크톱(16 논리 코어, 64 GB)에서 15 workers 는 커밋 한도를 넘겨 함께
돌던 torch 프로세스를 죽였다 (Windows `0xc000070a`). 8–10 workers 에서 장면당 약 10 s
(합산) 였다. 현미경 PC 에서는 **8 workers 로 시작**하고 작업 관리자의 커밋 사용량을 보면서 늘린다.

5 µm 입자 세트를 Ti2 대물렌즈 여섯 개 모두로 만들 때는 `farm_p5.py` 를 쓴다. 청크 단위로 나눠
멈췄다 이어 갈 수 있고, `data/p5_farm.STOP` 파일을 만들면 현재 청크를 마치고 멈춘다.

```
uv run python scripts/farm_p5.py --scenes 3000 --dry-run
uv run python scripts/farm_p5.py --scenes 3000
```

`farm_p5.py` 의 기본값(`--gpu-procs 3`, `--cpu-workers 30`)은 큰 PC 기준이다. 현미경 PC 의
코어 수와 메모리에 맞게 줄여서 시작한다.

근거: `scripts/make_dataset.py`, `scripts/farm_p5.py`, `src/dino_autofocus/synth/__init__.py`,
`docs/integration-notes.md` (psf-autofocus 절), `docs/synthetic-results.md`.

## 3. 특징 추출과 평가

```
uv run python scripts/eval_synthetic.py --data data/k100x
```

- DINO 특징을 `data/k100x/feat_dinov2_vits14_L1.npz` 에 캐시하고, 고전 지표와 비교한 결과를
  `outputs/eval_k100x_dinov2_vits14_L1.json` 에 쓴다.
- A4000 에서는 **fp16 기본값 그대로** 쓴다 (텐서 코어가 있다). `--no-fp16` 은 텐서 코어가 없는
  GPU 용이고, 그 특징은 `*_fp32.npz` 로 따로 저장돼 `train_head.py` 가 읽지 않는다. 학습에 쓰는
  특징은 fp16 하나로 통일한다.
- 캐시가 있으면 다시 계산하지 않는다. 백본이나 정밀도를 바꿨으면 캐시 파일을 지우고 돌린다.

근거: `scripts/eval_synthetic.py`, `docs/synthetic-results.md`.

## 4. 헤드 학습

```
uv run python scripts/train_head.py --data data/k100x
```

- 3절의 fp16 특징 캐시가 먼저 있어야 한다.
- 헤드 셋을 만든다. `dz` (부호 있는 디포커스, DoF, dz = stage − best focus), `err` (프레임별
  sigma), `valid` (읽을 수 있는 프레임인지). 성능은 장면 단위 5-fold 교차 검증으로 재고, 저장되는
  헤드는 전체 데이터로 다시 맞춘다.
- 광자 신호 스칼라는 MAE 를 0.25 DoF 넘게 줄일 때만 쓴다. 카메라 이득(e-/ADU)을 아직 재지
  않았기 때문이다. 쓰게 되면 `FocusScorer` 가 거부하므로 사용자에게 알린다.
- 출력: `outputs/heads/head_k100x_dinov2_vits14_L1.npz`, `.joblib`, `.json`.
- `train_head.py` 는 `--data` 폴더 바로 아래의 `shard_*.npz` 만 읽는다. `farm_p5.py` 의 청크
  폴더 구조는 읽지 않으므로 p5 세트는 지금 `learning_curve_p5.py` 로 평가만 한다.

근거: `scripts/train_head.py`, `scripts/learning_curve_p5.py`.

## 5. 확인

배선 확인 (학습에 쓴 장면이라 일반화 성능이 아니라 타일링, 전처리, 융합, 시간을 본다):

```
uv run python scripts/check_scorer.py --head outputs/heads/head_k100x_dinov2_vits14_L1.npz --data data/k100x
```

필요한 장면 수:

```
uv run python scripts/learning_curve.py --data data/k100x
uv run python scripts/learning_curve_p5.py
```

## 6. 지연 측정

```
uv run python scripts/bench_latency.py
```

ViT-S/14 와 ViT-B/14 를 224, 448, 518 px, 배치 1 과 8 에서 fp32 와 fp16 으로 잰다. GTX 1650
SUPER 에서는 fp16 이 약 4 배 느렸다. A4000 은 아직 재지 않았다 (PLAN.md 10절 미해결). 이 표가
fp16 기본값 유지 여부의 근거가 된다.

## 7. 헤드 채택

1. `outputs/heads/*.json` 의 지표를 지금 헤드(`models/heads/head_k100x_dinov2_vits14_L1.json`)와
   비교한다. 볼 것: `mae_dof`, `sign_acc_|dz|>=1`, `near_focus_mae_dof`,
   `sigma.coverage_1sigma` (0.68 근처), `valid_head.accuracy`.
2. 나아졌으면 `.npz` 와 `.json` 을 `models/heads/` 로 복사한다 (`.joblib` 은 피클이라 넣지 않는다). 저장소 반영은 개발 흐름
   (매니저 배정, 실행 세션 커밋, 검토 세션 병합)을 따른다. 현미경 PC 에서 `main` 에 직접 커밋하지
   않는다.
3. 라이브 뷰에는 `--head models/heads/<파일>.npz` 로 넘긴다. 예전 `.joblib` 만 있으면
   `uv run python scripts/export_head_npz.py <파일>.joblib` 로 바꾼다 (직접 학습한 파일만 연다).

## 8. 기록할 것

실행마다 아래를 텍스트로 남겨 매니저에게 전달한다. 같은 결과를 다시 만들 수 있어야 한다.

- 저장소 커밋 해시 (`git rev-parse HEAD`), DINOv2 커밋 (`7764ea0` 확인)
- 가중치 파일 SHA-256 (1.1절 표와 같은지)
- GPU 이름, 드라이버, `torch.__version__`, CUDA 버전
- 데이터셋 명령 전체 (인자, `--seed0`, `--workers`), 걸린 시간, 최대 커밋 메모리, 크래시 여부
- 프레임 수, 장면 수, `valid` 비율 (`eval_synthetic.py` 첫 줄 출력)
- 특징 정밀도 (fp16 / fp32)
- `eval_*.json`, 헤드 `.json` 전체
- `bench_latency.py` 표 전체
- 채택 여부와 이유

## 9. 하지 말 것

- 개발 데스크톱에서 2–6절 실행.
- 하드웨어 스크립트와 동시 실행.
- fp32 특징과 fp16 특징을 섞어 학습.
- 헤드 출력으로 Z 한계, 이동 허가, 게이트를 정하는 일.
- 다른 곳에서 받은 데이터셋 shard (`shard_*.npz`) 를 학습·평가 스크립트로 여는 일. `scene_params` 가 객체
  배열이라 `train_head.py`, `eval_synthetic.py` 등은 `np.load(..., allow_pickle=True)` 로 읽고, 피클은 열 때
  코드를 실행할 수 있다. 이 PC 에서 `make_dataset.py` / `farm_p5.py` 로 만든 shard 만 쓴다 (공개 전 점검 S10).
  엔진과 서버 쪽은 `allow_pickle=False` 이고, 헤드는 `.npz` 만 읽는다.
