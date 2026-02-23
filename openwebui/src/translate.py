"""
Key Features:
    - POT → PO 변환 자동화
    - 다국어 번역 지원
    - 병렬 스레드 기반 번역
    - Glossary(용어집) 기반 일관성 유지
    - LLM 모델 (Ollama / Qwen / Llama 등) 교체 가능 구조
    - 번역 결과 및 실험 로그 자동 저장 (CSV 기반)
    - Git 정보 포함 실험 기록

Execution Flow:
    1. utils.argparse로 CLI 인자값을 수신
    2. POT 폴더 생성 및 파일 다운로드
    3. load_glossary()로 언어별 glossary 파일 다운로드 및 로드
    4. load_fixed_examples()로 언어별 예시 로드
    5. translate_pot_file()-> translate_batch()에서 병렬 배치 번역 및 tqdm 표시
    6. save_experiment_log()로 결과 기록 및 Git 메타데이터 저장
"""

import requests
import ollama
import os
import time
import concurrent.futures
import json
import argparse
from dataclasses import dataclass
from typing import Callable
from tqdm import tqdm
from babel.messages import pofile, Catalog
from utils import (
    load_config,
    load_glossary,
    load_fixed_examples,
    save_experiment_log
)
from commercial_llm import (
    call_claude_chat,
    call_gemini_chat,
    call_openai_chat
)


def build_llm_caller(llm_mode: str, model_name: str) -> Callable:
    """LLM 백엔드를 선택하여 호출 함수를 생성하고 반환한다."""
    if llm_mode == "gpt":
        def _call(messages):
            return call_openai_chat(messages, model=model_name)

    elif llm_mode == "claude":
        def _call(messages):
            claude_messages = []
            claude_system = None
            for msg in messages:
                if msg["role"] == "system":
                    claude_system = msg["content"]
                else:
                    claude_messages.append(msg)
            return call_claude_chat(
                claude_messages,
                model=model_name,
                system=claude_system
            )

    elif llm_mode == "gemini":
        def _call(messages):
            return call_gemini_chat(messages, model=model_name)

    elif llm_mode == "openwebui":
        
        def _call(messages):
            url = f"{OPENWEBUI_URL.rstrip('/')}/api/v1/chat/completions"
            headers = {"Content-Type": "application/json"}
            if OPENWEBUI_API_KEY:
                headers["Authorization"] = f"Bearer {OPENWEBUI_API_KEY}"

            payload = {
                "model": model_name,   
                "messages": messages,
                "temperature": 0,
            }

            resp = requests.post(url, json=payload, headers=headers, timeout=120)
            resp.raise_for_status()
            data = resp.json()

            try:
                return data["choices"][0]["message"]["content"].strip()
            except (KeyError, IndexError) as e:
                raise RuntimeError(f"Unexpected OpenWebUI response: {data}") from e

    else:
        # 기본: 로컬 Ollama 직접 호출
        def _call(messages):
            response = ollama.chat(
                model=model_name,
                messages=messages,
                stream=False,
                options={
                    "temperature": 0,
                    "top_p": 1,
                    "repetition_penalty": 1.2,
                },
            )
            return response["message"]["content"].strip()

    return _call

OPENWEBUI_URL = os.getenv("OPENWEBUI_URL", "http://localhost:3000")
OPENWEBUI_API_KEY = os.getenv("OPENWEBUI_API_KEY")

LANG_MAP = {
    "vi_VN": "Vietnamese (Vietnam)",
    "ur": "Urdu",
    "tr_TR": "Turkish (Turkey)",
    "Th": "Thai",
    "te_IN": "Telugu (India)",
    "ta": "Tamil",
    "es_MX": "Spanish (Mexico)",
    "es": "Spanish",
    "sl_SI": "Slovenian (Slovenia)",
    "sr": "Serbian",
    "ru": "Russian",
    "Ro": "Romanian",
    "pa_IN": "Punjabi (India)",
    "pt_BR": "Portuguese (Brazil)",
    "pt": "Portuguese",
    "pl_PL": "Polish (Poland)",
    "fa": "Persian",
    "ne": "Nepali",
    "mr": "Marathi",
    "mni": "Manipuri",
    "mai": "Maithili",
    "lo": "Lao",
    "ko_KR": "Korean (South Korea)",
    "kok": "Konkani",
    "ks": "Kashmiri",
    "kn": "Kannada",
    "ja": "Japanese",
    "it": "Italian",
    "id": "Indonesian",
    "hu": "Hungarian",
    "hi": "Hindi",
    "he": "Hebrew",
    "gu": "Gujarati",
    "el": "Greek",
    "de": "German",
    "ka_GE": "Georgian (Georgia)",
    "fr": "French",
    "fi_FI": "Finnish (Finland)",
    "fil": "Filipino",
    "eo": "Esperanto",
    "en_US": "English (United States)",
    "en_GB": "English (United Kingdom)",
    "en_AU": "English (Australia)",
    "nl_NL": "Dutch (Netherlands)",
    "cs": "Czech",
    "zh_TW": "Chinese (Taiwan)",
    "zh_CN": "Chinese (China)",
    "ca": "Catalan",
    "bg_BG": "Bulgarian (Bulgaria)",
    "brx": "Bodo",
    "bn_IN": "Bengali (India)",
    "as": "Assamese",
    "ar": "Arabic",
    "sq": "Albanian",
}

PROMPT_DIR = os.path.join(os.path.dirname(__file__), "prompts")

DEFAULT_SYSTEM_PROMPT = """
    You are a strict translation engine.
    You are translating from English to {language_name}.

    **[Output Format Rules (MUST Follow)]**
    * Respond ONLY with the raw, translated text for {language_name}.
    * Your answer MUST be 100% in {language_name}.
    * Do NOT mix in any other languages (including English).
    * Do NOT add explanations, comments, apologies, or quotes.

    **[Critical Preservation Rules (MUST Follow)]**
    * Preserve all reStructuredText (RST) syntax exactly.
    * Preserve all placeholders exactly.
    * Preserve all HTML tags exactly.
    * You MUST use the exact translations provided in the `[Glossary]` section.

    **[Anti-Hallucination Rules (MUST Follow)]**
    * You MUST NOT add placeholders that are NOT in the original `msgid`.
    * You MUST NOT repeat phrases. Repetition is strictly forbidden.

    **[Glossary]**
    """


@dataclass
class TranslationContext:
    glossary: dict
    few_shot_examples: list
    call_llm_fn: Callable
    max_workers: int
    start: int | None
    end: int | None
    system_prompt: str


def load_support_prompt(language_code: str) -> str | None:
    """언어별 커스텀 프롬프트 파일이 있으면 로드, 없으면 None 반환."""
    prompt_path = os.path.join(PROMPT_DIR, f"{language_code}.txt")
    if os.path.isfile(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return None


def translate_batch(payload, language_name, ctx: TranslationContext):
    """
    여러 entry를 batch로 묶어 LLM을 사용해 번역하는 함수.
    Translates a batch of PO/POT entries using the selected LLM model.

    Args:
        payload (tuple): (entries, batch_index, total_batches)
        language_name (str): 번역하는 언어 이름
        ctx (TranslationContext): 번역에 필요한 컨텍스트 객체

    Returns:
        list: [(msgid, translation, locations), ...]
                - 정상일 때: translation에 번역 문자열이 채워진다.
                - 오류/파싱 실패 시: translation(msgstr)을 빈 문자열("")로 둔 채 반환한다.
    """
    entries, batch_idx, total_batches = payload

    glossary_text = "\n".join(
        f"* '{en}': '{ko}'" for en,
        ko in ctx.glossary.items())
    system_prompt = ctx.system_prompt + glossary_text

    messages = [
        {
            "role": "system",
            "content": system_prompt.format(language_name=language_name),
        },
    ]

    # Few-shot 예시 추가 (batch 형식)
    example_input = [msgid for msgid, _ in ctx.few_shot_examples]
    example_output = [msgstr for _, msgstr in ctx.few_shot_examples]

    messages.append({
        "role": "user",
        "content": (
            "Here are examples of translating a JSON array:\n"
            f"{json.dumps(example_input, ensure_ascii=False)}"
        )
    })
    messages.append({
        "role": "assistant",
        "content": json.dumps(example_output, ensure_ascii=False)
    })

    # 실제 번역할 텍스트들을 JSON 배열로 구성
    texts_to_translate = [entry.id for entry in entries]
    user_content = (
        f"Translate the following {len(texts_to_translate)} items.\n"
        f"Your response MUST be a single, valid JSON array `[...]` "
        f"containing exactly {len(texts_to_translate)} translated strings "
        "in the same order."
        "Do NOT add any other text, explanations, or markdown formatting.\n\n"
        f"{json.dumps(texts_to_translate, ensure_ascii=False)}")

    messages.append({"role": "user", "content": user_content})

    try:
        translation_text = ctx.call_llm_fn(messages)

        # JSON 파싱 시도
        try:
            translations = json.loads(translation_text)
        except json.JSONDecodeError:
            print(
                f"!!! Batch [{batch_idx + 1}/{total_batches}] "
                "JSON parsing failed, trying to extract array !!!")
            print("Falling back: extract simple array for this batch.")
            start = translation_text.find('[')
            end = translation_text.rfind(']') + 1
            if start != -1 and end != 0:
                translations = json.loads(translation_text[start:end])
            else:
                raise ValueError("Cannot extract JSON array from response")

        # 번역 결과와 entry 매칭
        if len(translations) != len(entries):
            print(
                (
                    "!!! Batch [{idx}/{total}] Translation count mismatch: "
                    "expected {expected}, got {actual} !!!"
                ).format(
                    idx=batch_idx + 1,
                    total=total_batches,
                    expected=len(entries),
                    actual=len(translations),
                )
            )
            print("Falling back: leaving msgstr empty for this batch.")
            return [(entry.id, "", entry.locations) for entry in entries]

        return [(entry.id, translation.strip(), entry.locations)
                for entry, translation in zip(entries, translations)]

    except Exception as e:
        print(
            (
                "!!! Batch [{idx}/{total}] Error translating batch: "
                "{error} !!!"
            ).format(
                idx=batch_idx + 1,
                total=total_batches,
                error=e,
            )
        )
        return [(entry.id, "", entry.locations) for entry in entries]


def create_batches(entries, batch_size):
    """
    Entry 리스트를 지정된 크기의 batch로 분할하는 함수.

    Args:
        entries (list): 전체 entry 리스트
        batch_size (int): 각 batch의 크기

    Returns:
        list: batch로 분할된 entry 리스트의 리스트
    """
    batches = []
    for i in range(0, len(entries), batch_size):
        batches.append(entries[i:i + batch_size])
    return batches


def translate_pot_file(
        pot_path,
        po_path,
        language_code,
        language_name,
        batch_size,
        ctx: TranslationContext):
    """
    POT 파일을 읽어 batch 단위로 병렬 번역 후 PO 파일로 저장하는 함수.

    Args:
        pot_path (str): 원본 POT 파일 경로
        po_path (str): 번역된 결과를 저장할 PO 파일 경로
        language_code (str): 번역하는 언어 코드
        language_name (str): 번역하는 언어 이름
        batch_size (int): 한 번에 번역할 entry 개수
        ctx (TranslationContext): 번역에 필요한 컨텍스트 객체
    """
    with open(pot_path, "rb") as f:
        pot = pofile.read_po(f)

    po = Catalog(
        locale=language_code,
        project=pot.project,
        version=pot.version,
        copyright_holder=pot.copyright_holder,
        msgid_bugs_address=pot.msgid_bugs_address,
        creation_date=pot.creation_date,
        language_team=pot.language_team,
        charset="UTF-8",
    )

    entries_to_translate = [entry for entry in pot if entry.id]

    # start/end 범위 제한 적용
    if ctx.start is not None or ctx.end is not None:
        start_idx = ctx.start if ctx.start is not None else 0
        end_idx = ctx.end if ctx.end is not None else len(entries_to_translate)
        entries_to_translate = entries_to_translate[start_idx:end_idx]
    total_entries = len(entries_to_translate)

    batches = create_batches(entries_to_translate, batch_size)
    total_batches = len(batches)

    print(f"--- {os.path.basename(pot_path)}를 {language_code}로 번역 ---")
    print(
        f"총 {total_entries}개 entry를 {total_batches}개 batch로 나누어 번역합니다. "
        f"(Batch size: {batch_size}, Workers: {ctx.max_workers})"
    )

    payloads = [
        (batch, i, total_batches)
        for i, batch in enumerate(batches)
    ]

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=ctx.max_workers
    ) as executor:
        results = list(
            tqdm(
                executor.map(
                    lambda payload: translate_batch(
                        payload,
                        language_name,
                        ctx),
                    payloads),
                total=total_batches,
                desc=f"Translating batches [{language_code}]",
                unit="batch",
            ))

    for batch_result in results:
        if batch_result:
            for msgid, translation, locations in batch_result:
                po.add(id=msgid, string=translation, locations=locations,
                       user_comments=["Initial translation by AI."])

    try:
        with open(po_path, "wb") as f:
            pofile.write_po(f, po)
        print(f"{po_path}가 저장되었습니다.")
    except Exception as e:
        print(f"PO 파일 저장 실패: {e}")


if __name__ == "__main__":
    """
    메인 실행 블록.
    Handles argument parsing, environment setup, translation execution,
    and experiment logging.

    Steps:
        1. 인자 파싱 및 경로 초기화
        2. 언어별 Glossary 파일 및 예시 파일 다운로드 및 로드
        3. 모델별/언어별 폴더 생성 및 번역 수행
        4. 언어별 번역 결과 저장 및 Git 로그 기록
    """
    # 1) --config 하나만 받기
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    cfg = load_config(args.config)

    # -----------------------------
    # files Config
    # -----------------------------
    POT_DIR = "./pot/"
    PO_DIR = "./po"

    # local 모드: config의 target_file이 파일명 키
    target_file = cfg["target_file"]
    target_file_name, _ = os.path.splitext(target_file)

    POT_FILE = os.path.join(POT_DIR, f"{target_file_name}.pot")

    # -----------------------------
    # languages Config
    # -----------------------------
    languages_cfg = cfg.get("languages")
    if isinstance(languages_cfg, str):
        LANGUAGES_TO_TRANSLATE = [
            s.strip() for s in languages_cfg.split(',') if s.strip()]
    else:
        LANGUAGES_TO_TRANSLATE = languages_cfg

    # -----------------------------
    # LLM Config
    # -----------------------------
    llm_cfg = cfg.get("llm")
    MODEL_NAME = llm_cfg.get("model")
    LLM_MODE = llm_cfg.get("mode")
    MAX_WORKERS = llm_cfg.get("workers")
    call_llm_fn = build_llm_caller(LLM_MODE, MODEL_NAME)
    START_TRANSLATE = llm_cfg.get("start")
    END_TRANSLATE = None if llm_cfg.get("end") == -1 else llm_cfg.get("end")
    BATCH_SIZE = llm_cfg.get("batch_size")

    # -----------------------------
    # Glossary / Examples Config
    # -----------------------------
    examples_cfg = cfg.get("examples")
    EXAMPLE_DIR = "./po-example"
    EXAMPLE_URL = examples_cfg.get("example_url")
    EXAMPLE_FILE = examples_cfg.get("example_file")
    FIXED_EXAMPLE_JSON = "fixed_examples.json"

    print("=================================================")
    print(f"Translation Start, LLM: {MODEL_NAME}, Batch Size: {BATCH_SIZE}")
    print("=================================================\n")

    # 폴더 생성 + POT 다운로드
    os.makedirs(POT_DIR, exist_ok=True)
    os.makedirs(PO_DIR, exist_ok=True)
    os.makedirs(EXAMPLE_DIR, exist_ok=True)

    if POT_FILE:
        pot_file_path = POT_FILE
        print(f"Using local POT file: {pot_file_path}")
        if not os.path.exists(pot_file_path):
            raise FileNotFoundError(f"POT file not found: {pot_file_path}")
    base_name = os.path.basename(pot_file_path).replace(".pot", ".po")

    start = time.time()
    # --- 언어 루프 ---
    for lang_code in LANGUAGES_TO_TRANSLATE:
        lang_start_time = time.time()
        print(f"--- [{lang_code}] Language Translation Start ---")

        # 1. 언어 이름 찾기 (LANG_MAP 사용)
        language_name = LANG_MAP.get(lang_code, lang_code)

        # 2. 언어별 glossary, 예시, 프롬프트 로드
        glossary = load_glossary(lang_code)

        few_shot_examples = load_fixed_examples(
            lang_code,
            EXAMPLE_DIR,
            FIXED_EXAMPLE_JSON,
            EXAMPLE_URL,
            EXAMPLE_FILE
        )

        custom_prompt = load_support_prompt(lang_code)
        if custom_prompt:
            print(f"Using custom support prompt for {lang_code}")
            system_prompt = custom_prompt
        else:
            system_prompt = DEFAULT_SYSTEM_PROMPT

        # 3. TranslationContext 생성
        ctx = TranslationContext(
            glossary=glossary,
            few_shot_examples=few_shot_examples,
            call_llm_fn=call_llm_fn,
            max_workers=MAX_WORKERS,
            start=START_TRANSLATE,
            end=END_TRANSLATE,
            system_prompt=system_prompt,
        )

        # 4. 결과 저장 경로 설정 (모델명/언어코드/파일명)
        model_lang_folder = os.path.join(PO_DIR, MODEL_NAME, lang_code)
        os.makedirs(model_lang_folder, exist_ok=True)
        po_file_path = os.path.join(model_lang_folder, base_name)

        # 5. 번역 실행
        translate_pot_file(
            pot_file_path,
            po_file_path,
            lang_code,
            language_name,
            BATCH_SIZE,
            ctx
        )

        lang_end_time = time.time()
        duration = round(lang_end_time - lang_start_time, 2)
        print(f"---[{lang_code}] Language Translation End ({duration}s)---\n")

        # 6. 로그 기록
        save_experiment_log(
            model_name=MODEL_NAME,
            pot_file=pot_file_path,
            po_file=po_file_path,
            duration_sec=duration,
            language=lang_code
        )
    end = time.time()
    duration = round(end - start, 2)
    print(f"Total translation time: {duration}s")
