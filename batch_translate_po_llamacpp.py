#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
batch_translate_po_llamacpp.py — Llama.cpp 기반 로컬 번역기 (CPU 전용 + glossary system prompt)
"""

import os
import json
import polib
import time
from tqdm import tqdm
from llama_cpp import Llama

# =========[ 설정값 ]=========
MODEL_PATH = "/Users/jiwoo/i18n/models/llama3.2-3b-instruct.gguf"
IN_FILE = "po/ko_KR/releasenotes.po"
OUT_FILE = "po_llamacpp/releasenotes-ko.po"
LANG = "ko"
GLOSSARY_FILE = "glossary/slim_glossary.txt"

# ⚙️ CPU 전용 설정
CTX = 3072
THREADS = os.cpu_count() or 8  # M4 Pro의 물리코어 기반
GPU_LAYERS = 0  # CPU 전용
BATCH_SIZE = 12

# =========[ glossary 로드 ]=========
def load_glossary(path):
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()

GLOSSARY_CONTENT = load_glossary(GLOSSARY_FILE)
SYSTEM_PROMPT = f"""You are a professional technical translator.
Strictly follow these glossary mappings:
{GLOSSARY_CONTENT}

Rules:
- Translate from English to Korean.
- Follow glossary translations exactly. Do not paraphrase or omit them.
- Preserve placeholders, punctuation, and technical terms.
- Output only the translation.
"""

# =========[ Llama 모델 로드 ]=========
print("🔧 Loading model...")
llm = Llama(
    model_path=MODEL_PATH,
    n_ctx=CTX,
    n_threads=THREADS,
    n_gpu_layers=GPU_LAYERS,
    verbose=False
)
print("✅ Model ready.")

# =========[ 함수 정의 ]=========
def translate_text(entry_text):
    """한 개 항목 번역"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Translate the following English text into Korean:\n\n{entry_text}"}
    ]
    try:
        output = llm.create_chat_completion(
            messages=messages,
            temperature=0.1,
            max_tokens=512
        )
        result = output["choices"][0]["message"]["content"].strip()
        return result
    except Exception as e:
        print(f"[ERROR] 번역 실패: {e}")
        return entry_text

# =========[ 메인 로직 ]=========
def main():
    po = polib.pofile(IN_FILE)
    total = len(po)
    print(f"↩️ Resume: 0/{total} entries")

    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    start_time = time.time()

    for idx, entry in enumerate(tqdm(po, desc="Translating", ncols=80)):
        if entry.msgstr.strip():
            continue
        translated = translate_text(entry.msgid)
        entry.msgstr = translated

        # 주기적으로 저장
        if idx % 20 == 0:
            po.save(OUT_FILE)
            print(f"💾 saved: {idx}/{total}")

    po.save(OUT_FILE)
    print(f"🎉 Done: {OUT_FILE}")
    print(f"⏱️ Elapsed: {time.time() - start_time:.1f}s")

# =========[ 실행 ]=========
if __name__ == "__main__":
    main()
