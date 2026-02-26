# OpenWebUI Translation Quality Evaluation Pipeline

OpenWebUI를 통해 여러 LLM 모델의 번역 결과를 자동으로 채점하고 HTML 리포트로 비교합니다.

## Pipeline Overview

```
config.yaml
    │
    ▼
[Step 1] src/translate.py           → 각 모델이 POT 파일을 번역 → po/{model}/{lang}/*.po
    │
    ▼
[Step 2] src/po_to_json.py          → PO 파일들을 비교용 JSON으로 변환 → results/arena_translations.json
    │
    ▼
[Step 3] src/arena_score.py         → judge 모델이 각 번역을 0~5점으로 채점 → results/arena_feedback_llm.json
    │                                   + ELO 매칭 생성 → results/elo_matches.json
    ▼
[Step 4] src/arena_report_generator.py → HTML 리포트 생성 → results/arena_report_llm.html
```

## Prerequisites

### 1. OpenWebUI Setup

OpenWebUI는 Docker를 통해 실행합니다:

```bash
docker run -d -p 3000:8080 \
  --add-host=host.docker.internal:host-gateway \
  -v open-webui:/app/backend/data \
  --name open-webui \
  --restart always \
  ghcr.io/open-webui/open-webui:main
```

실행 후 `http://localhost:3000`에 접속하여 계정을 생성합니다.

### 2. Ollama Setup

[Ollama](https://ollama.com/)를 설치하고 사용할 모델을 pull합니다:

```bash
ollama pull llama3.2:3b
ollama pull qwen2.5:7b
```

### 3. Python Environment

**중요**: Python 3.10-3.12를 사용해야 합니다 (Python 3.13은 Babel 호환성 문제 발생).

macOS에서는 venv 사용을 권장합니다 (Homebrew Python PEP 668 제약):

```bash
python3.10 -m venv venv  # 또는 python3.11, python3.12
source venv/bin/activate
pip install -r src/requirements.txt
```

## How to Use

### Step 1. Edit `config.yaml`

```yaml
target_file: "test.pot"    # 번역할 POT 파일 이름 (pot/ 디렉토리에 위치)
languages: "ko_KR"          # 번역 대상 언어

llm:
  mode: "openwebui"
  models:
    - "llama3.2:3b"         # 번역에 사용할 모델 목록
    - "qwen2.5:3b"
    - "gemma3:4b"
  judge_model: "qwen2.5:7b" # 채점에 사용할 모델
```

### Step 2. Set API Key

OpenWebUI API 키를 발급받아 환경변수로 설정합니다:

```bash
export OPENWEBUI_API_KEY=sk-...
# 또는 openwebui/.env 파일에 작성:
echo "OPENWEBUI_API_KEY=sk-..." > .env
```

**API 키 발급 방법**:

1. `http://localhost:3000`에 접속하여 로그인
2. `Settings > Account > API Keys`로 이동
3. "Create new secret key" 클릭

**주의**: API 키 생성 버튼이 작동하지 않는 경우, 아래 Troubleshooting 섹션을 참고하세요.

### Step 3. Place POT File

```
openwebui/
└── pot/
    └── test.pot   ← config.yaml의 target_file에 맞게 배치
```

### Step 4. Run

```bash
cd openwebui/
bash main.sh
```

번역을 건너뛰고 평가부터 실행하려면:

```bash
bash main.sh --skip-translate
```

실행이 완료되면 터미널에 리포트 URL이 출력됩니다.

## Output

| File | Description |
|------|-------------|
| `po/{model}/{lang}/*.po` | 각 모델의 번역 결과 |
| `results/arena_dataset.jsonl` | 모델 쌍 비교용 JSONL |
| `results/arena_results.json` | 모델별 채점 결과 |
| `results/report.html` | 최종 HTML 리포트 (리더보드 + 샘플 비교) |

## Scoring Criteria (0–5)

| Score | Criteria |
|-------|----------|
| 5 | Perfect — 의미 정확, 자연스러운 한국어 |
| 4 | Good — 의미 정확, 약간의 어색함 |
| 3 | Fair — 대체로 정확하나 일부 오류 |
| 2 | Poor — 오역 또는 외래어 혼용 |
| 1 | Very Poor — 대부분 오역 |
| 0 | Failed — 미번역, 반복 출력, 깨진 텍스트 |

## Troubleshooting

### Python 버전 호환성 문제

**증상**: `ModuleNotFoundError: No module named 'cgi'` (Babel 관련)

**원인**: Python 3.13에서 `cgi` 모듈이 제거되었으나 Babel 2.8.0이 이를 사용함

**해결책**: Python 3.10-3.12 버전으로 venv 생성

```bash
# Python 3.10, 3.11, 또는 3.12 사용
python3.10 -m venv venv
source venv/bin/activate
pip install -r src/requirements.txt
```