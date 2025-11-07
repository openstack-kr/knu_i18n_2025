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
    2. utils.init_environment()에서 POT 폴더 생성 및 파일 다운로드
    3. load_glossary()로 언어별 glossary 파일 다운로드 및 로드
    4. load_examples()로 언어별 예시 파일 다운로드 및 로드
    4. translate_pot_file()-> translate_entry()에서 병렬 번역 및 tqdm 표시
    5. save_experiment_log()로 결과 기록 및 Git 메타데이터 저장
"""

import os
import time
import concurrent.futures
from tqdm import tqdm
import random
from babel.messages import pofile, Catalog
import google.generativeai as genai
from utils import (
    parse_args,
    init_environment,
    load_glossary,
    load_examples,
    save_experiment_log
)

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

def translate_entry(payload, language_name, llm_model, glossary, few_shot_examples):
    """
    번역 단위(entry)를 LLM을 사용해 번역하는 함수.
    Translates a single PO/POT entry using the selected LLM model.

    Args:
        payload (tuple): (entry, index, total_count)
            entry (babel.messages.catalog.Message): 번역 대상 메시지 객체
            index (int): 현재 번역 순서
            total_count (int): 전체 번역 항목 수
        language_name (str): 번역하는 언어 이름
        llm_model (genai.GenerativeModel): 초기화된 LLM 모델 객체
        glossary (dict): 용어집 딕셔너리
        few_shot_examples (list): Few-shot 학습을 위한 예시 리스트

    Returns:
        tuple | None: (msgid, translation, locations) 또는 오류 시 None
    """

    entry, i, total_count = payload

    relevant_glossary_terms = {
        en: ko for en, ko in glossary.items() if en in entry.id.lower()
    }

    glossary_rules = ""
    if relevant_glossary_terms:
        glossary_rules = (
            "Apply these translation rules: "
            + ", ".join(
                [
                    f"'{en}' must be translated as '{ko}'"
                    for en, ko in relevant_glossary_terms.items()
                ]
            )
            + "."
        )

    # For Gemini, system instructions are best provided via the `system_instruction`
    # parameter during model initialization. As a fallback, we include them in the
    # first user message of the conversation.
    system_instruction = (
        "You are a strict translation engine. "
        f"You must translate the user's English text into {language_name} only. "
        "Your response MUST be written 100% in the target language. "
        "Do not mix in any other languages, including English. "
        "Do not add explanations, comments, or any other extraneous text. "
        "Output only the translated text itself, without any surrounding quotes. "
        "Preserve all reStructuredText (RST) syntax, placeholders, "
        "and formatting exactly as in the original input."
    )

    genai_messages = []

    # Add few-shot examples to guide the model
    if few_shot_examples:
        num_to_sample = min(len(few_shot_examples), 2)
        selected_examples = random.sample(few_shot_examples, num_to_sample)
        for msgid, msgstr in selected_examples:
            genai_messages.append({"role": "user", "parts": [msgid]})
            genai_messages.append({"role": "model", "parts": [msgstr]})

    # Combine instructions, rules, and the text into the final user prompt.
    final_prompt_parts = [system_instruction]
    if glossary_rules:
        final_prompt_parts.append(glossary_rules)
    final_prompt_parts.append(f"Translate the following text:\n\n{entry.id}")

    final_user_prompt = "\n\n".join(final_prompt_parts)
    genai_messages.append({"role": "user", "parts": [final_user_prompt]})

    try:
        generation_config = {
            "temperature": 0,
            "top_p": 1,
            "stop_sequences": ["\n"],  # Stop at newline to mimic original behavior
        }
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]

        response = llm_model.generate_content(
            genai_messages,
            generation_config=generation_config,
            safety_settings=safety_settings
        )

        # Robustly access the generated text. The `.text` accessor raises a
        # ValueError if the response is blocked or empty.
        translation = response.text.strip()

        return (entry.id, translation, entry.locations)

    except ValueError:
        # Handle cases where the response is blocked or empty.
        finish_reason = "UNKNOWN"
        if response.candidates:
            finish_reason = response.candidates[0].finish_reason.name

        print(
            (
                f"!!! [{i + 1}/{total_count}] Warning: Model returned no valid text for "
                f"'{entry.id[:30]}...'. Reason: {finish_reason} !!!"
            )
        )
        return None
    except Exception as e:
        # Catch other potential API errors (e.g., network issues).
        print(
            (
                f"!!! [{i + 1}/{total_count}] Error translating entry "
                f"'{entry.id[:30]}...': {e} !!!"
            )
        )
        return None


def translate_pot_file(pot_path, po_path, language_code, language_name, llm_model, glossary, few_shot_examples):
    """
    POT 파일을 읽어 병렬 번역 후 PO 파일로 저장하는 함수.
    Reads a .pot file, translates entries in parallel, and saves as .po file.

    Args:
        pot_path (str): 원본 POT 파일 경로
        po_path (str): 번역된 결과를 저장할 PO 파일 경로
        language_code (str): 번역하는 언어 코드
        language_name (str): 번역하는 언어 이름
        llm_model (genai.GenerativeModel): 초기화된 LLM 모델 객체
        glossary (dict): 용어집 딕셔너리
        few_shot_examples (list): Few-shot 학습을 위한 예시 리스트

    Returns:
        None
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
    po.header_comment = "Initial translation by AI.\n" + pot.header_comment

    entries_to_translate = [entry for entry in pot if entry.id]
    total_entries = len(entries_to_translate)

    print(f"--- {os.path.basename(pot_path)}를 {language_code}로 번역 ---")
    print(
        f"총 {total_entries} 라인의 번역입니다. {MAX_WORKERS} 개의 병렬 코어를 사용합니다."
    )

    # (entry, 순서, 전체 개수) 의 payload 만들기
    payloads = [
        (entry, i, total_entries)
        for i, entry in enumerate(entries_to_translate)
    ]

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:
        # payload 전달, tqdm으로 진행률 표시
        results = list(
            tqdm(
                executor.map(
                    lambda payload: translate_entry(
                        payload,
                        language_name,
                        llm_model,
                        glossary,
                        few_shot_examples
                    ),
                    payloads),
                total=total_entries,
            )
        )