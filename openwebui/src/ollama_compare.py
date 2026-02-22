#!/usr/bin/env python3
"""
Ollama 모델(llama3.2:3b, qwen2.5:7b, gemma2:2b) 3개로
POT 파일을 번역하고 결과를 JSON으로 저장 + 간단 프리뷰 출력.

Usage 예시:
    cd ~/knu_i18n/knu_i18n_2025/local
    python3 src/ollama_compare.py \
        --pot pot/test-small.pot \
        --output results/ollama-translations.json \
        --limit 20
"""

import argparse
import json
import os
import sys
from typing import Dict, List

import requests
from babel.messages import pofile

# 기본 OpenWebUI 주소: 같은 인스턴스에서 돌릴 거면 localhost 사용
OPENWEBUI_URL = os.getenv("OPENWEBUI_URL", "http://localhost:3000")


class OpenWebUIClient:
    def __init__(self, base_url: str = OPENWEBUI_URL, api_key: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        # 지금은 API Key 안 쓰니까 Authorization 헤더는 생략
        self.headers = {"Content-Type": "application/json"}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"

    def chat(self, model: str, system_prompt: str, user_content: str) -> str:
        """OpenWebUI /api/chat/completions 호출."""
        url = f"{self.base_url}/api/chat/completions"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0,
        }

        resp = requests.post(url, headers=self.headers, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Unexpected API response: {data}") from e


def load_pot_entries(path: str, limit: int | None = None):
    """POT 파일에서 msgid 있는 entry만 뽑아오기."""
    with open(path, "rb") as f:
        catalog = pofile.read_po(f)

    entries = [e for e in catalog if e.id]

    if limit is not None:
        entries = entries[:limit]

    return entries


def normalize_msgid(entry) -> str:
    """단수/복수 msgid를 문자열 하나로 정리."""
    # plurals인 경우 entry.id가 튜플일 수 있음
    if isinstance(entry.id, tuple):
        return entry.id[0]
    return entry.id


def translate_with_models(
    client: OpenWebUIClient,
    pot_path: str,
    models: List[str],
    system_prompt: str,
    limit: int | None = None,
) -> Dict[str, Dict[str, str]]:
    """
    여러 모델을 돌려서:
        결과 구조 = { model_name: { msgid: msgstr, ... }, ... }
    형태로 반환.
    """
    entries = load_pot_entries(pot_path, limit)
    total = len(entries)
    print(f"POT entries: {total}")

    all_results: Dict[str, Dict[str, str]] = {}

    for model in models:
        print(f"\n=== Translating with [{model}] ===")
        model_results: Dict[str, str] = {}

        for idx, entry in enumerate(entries, 1):
            msgid = normalize_msgid(entry)
            preview = msgid.replace("\n", " ")[:80]

            print(f"[{model}] {idx}/{total} : {preview!r}")
            try:
                msgstr = client.chat(model, system_prompt, msgid)
            except Exception as e:
                print(f"  ! Error: {e}", file=sys.stderr)
                msgstr = ""  # 실패 시 빈 문자열로 넣어둠

            model_results[msgid] = msgstr

        all_results[model] = model_results

    return all_results


def print_preview(all_results: Dict[str, Dict[str, str]], models: List[str], sample_count: int = 5) -> None:
    """터미널에서 간단히 side-by-side 프리뷰 보여주기."""
    if not all_results:
        return

    # 첫 번째 모델의 msgid 리스트 기준
    first_model = models[0]
    msgids = list(all_results[first_model].keys())[:sample_count]

    print("\n\n===== Preview of first few entries =====")
    for msgid in msgids:
        print("\n----------------------------------------")
        print(f"msgid: {msgid}")
        for model in models:
            msgstr = all_results.get(model, {}).get(msgid, "")
            print(f"\n[{model}]")
            print(msgstr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare Ollama models via OpenWebUI")
    parser.add_argument("--pot", required=True, help="입력 POT 파일 경로")
    parser.add_argument(
        "--models",
        default="llama3.2:3b,qwen2.5:7b,gemma2:2b",
        help="콤마로 구분된 모델 이름 목록 (기본: llama3.2:3b,qwen2.5:7b,gemma2:2b)",
    )
    parser.add_argument(
        "--system-prompt",
        default="Translate the following English UI text to natural, professional Korean.",
        help="번역에 사용할 system prompt",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="번역할 최대 entry 수 (테스트용, 기본: 전체)",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="결과 JSON 저장 경로 (예: results/ollama-translations.json)",
    )

    args = parser.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    if not models:
        print("Error: at least one model must be specified via --models", file=sys.stderr)
        sys.exit(1)

    print(f"OpenWebUI URL: {OPENWEBUI_URL}")
    print(f"Models: {models}")
    print(f"POT: {args.pot}")
    if args.limit:
        print(f"Limit entries: {args.limit}")

    client = OpenWebUIClient()
    all_results = translate_with_models(
        client=client,
        pot_path=args.pot,
        models=models,
        system_prompt=args.system_prompt,
        limit=args.limit,
    )

    # JSON으로 저장 (모델 기준)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Saved translations to: {args.output}")

    # 간단 프리뷰
    print_preview(all_results, models=models, sample_count=5)


if __name__ == "__main__":
    main()