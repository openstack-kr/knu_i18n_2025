# OpenWebUI Translation Quality Evaluation Pipeline

OpenWebUI를 통해 여러 LLM 모델의 번역 결과를 자동으로 채점하고 HTML 리포트로 비교합니다.

## Pipeline Overview

```
config.yaml
    │
    ▼
[Step 1] translate.py           → 각 모델이 POT 파일을 번역 → po/{model}/{lang}/*.po
    │
    ▼
[Step 2] po_to_arena.py         → PO 파일들을 비교용 JSONL로 변환 → results/arena_dataset.jsonl
    │
    ▼
[Step 3] arena_evaluator.py     → judge 모델이 각 번역을 0~5점으로 채점 → results/arena_results.json
    │
    ▼
[Step 4] arena_report_generator.py → HTML 리포트 생성 → results/report.html
```

## Prerequisites

- [OpenWebUI](https://github.com/open-webui/open-webui) 실행 중 (`http://localhost:3000`)
- [Ollama](https://ollama.com/) 실행 중, 사용할 모델 pull 완료
- Python 3.10+

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

```bash
export OPENWEBUI_API_KEY=sk-...
# 또는 openwebui/.env 파일에 작성
```

OpenWebUI API 키는 `Settings > Account > API Keys`에서 발급받을 수 있습니다.

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