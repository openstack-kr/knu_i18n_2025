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

import ollama
import os
import time
import concurrent.futures
from tqdm import tqdm
from babel.messages import pofile, Catalog
from utils import (
    parse_args,
    init_environment,
    load_glossary,
    load_fixed_examples,
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

# 하나의 문장(entry)을 번역


def translate_entry(payload, language_name):
    """
    번역 단위(entry)를 LLM을 사용해 번역하는 함수.
    Translates a single PO/POT entry using the selected LLM model.

    Args:
        payload (tuple): (entry, index, total_count)
            entry (babel.messages.catalog.Message): 번역 대상 메시지 객체
            index (int): 현재 번역 순서
            total_count (int): 전체 번역 항목 수
        language_name (str): 번역하는 언어 이름

    Returns:
        tuple | None: (msgid, translation, locations) 또는 오류 시 None
    """

    entry, i, total_count = payload

    GLOSSARY_TEXT_LINES = [f"* '{en}': '{ko}'" for en, ko in GLOSSARY.items()]
    FORMATTED_GLOSSARY = "\n".join(GLOSSARY_TEXT_LINES)

    SYSTEM_PROMPT_BASE = """
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
    SYSTEM_PROMPT = SYSTEM_PROMPT_BASE + FORMATTED_GLOSSARY

    messages = [
        # System 역할: 전체 규칙과 '전체' 용어집을 한 번에 전달
        {
            "role": "system",
            "content": SYSTEM_PROMPT.format(language_name=language_name),
        },
    ]

    for msgid, msgstr in FEW_SHOT_EXAMPLES:
        messages.append({"role": "user", "content": msgid})
        messages.append({"role": "assistant", "content": msgstr})

    messages.append({"role": "user", "content": entry.id})

    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=messages,
            stream=False,
            options={
                "temperature": 0,
                "top_p": 1,
                "repetition_penalty": 1.2,
                "stop": ["\n"],
            },
        )

        translation = response["message"]["content"].strip()

        # 번역한 문장을 삽입한 entry
        return (entry.id, translation, entry.locations)

    except Exception as e:
        print(
            (
                f"!!! [{i + 1}/{total_count}] Error translating entry "
                f"'{entry.id[:30]}...': {e} !!!"
            )
        )
        return None


# pot 파일을 읽어 번역해 최종 po 파일로 저장하는 함수
def translate_pot_file(pot_path, po_path, language_code, language_name):
    """
    POT 파일을 읽어 병렬 번역 후 PO 파일로 저장하는 함수.
    Reads a .pot file, translates entries in parallel, and saves as .po file.

    Args:
        pot_path (str): 원본 POT 파일 경로
        po_path (str): 번역된 결과를 저장할 PO 파일 경로
        language_code (str): 번역하는 언어 코드
        language_name (str): 번역하는 언어 이름

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
                        language_name),
                    payloads),
                total=total_entries,
                desc=f"Translating entries [{language_code}]",
                unit="entry",
            ))

    for result in results:
        if result:
            msgid, translation, locations = result
            po.add(id=msgid, string=translation, locations=locations)

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
    args = parse_args()
    MODEL_NAME = args.model
    POT_DIR = args.pot_dir
    PO_DIR = args.po_dir
    GLOSSARY_DIR = args.glossary_dir
    EXAMPLE_DIR = args.example_dir
    START_TRANSLATE = args.start
    END_TRANSLATE = args.end
    MAX_WORKERS = args.workers
    POT_URL = args.pot_url
    TARGET_POT_FILE = args.target_pot_file
    GLOSSARY_URL = args.glossary_url
    GLOSSARY_PO_FILE = args.glossary_po_file
    GLOSSARY_JSON_FILE = args.glossary_json_file
    EXAMPLE_URL = args.example_url
    EXAMPLE_FILE = args.example_file
    LANGUAGES_TO_TRANSLATE = args.languages.split(',')
    FIXED_EXAMPLE_JSON = args.fixed_example_json

    print("=================================================")
    print(f"번역 시작, AI 모델: {MODEL_NAME}")
    print("=================================================\n")

    # 폴더 생성 + POT 다운로드
    pot_file_path = init_environment(
        pot_dir=POT_DIR,
        po_dir=PO_DIR,
        glossary_dir=GLOSSARY_DIR,
        example_dir=EXAMPLE_DIR,
        pot_url=POT_URL,
        target_pot_file=TARGET_POT_FILE,
    )

    # 모델별 폴더 구성 + 파일 경로
    base_name = os.path.basename(pot_file_path).replace(".pot", ".po")

    start = time.time()
    # --- 언어 루프 ---
    for lang_code in LANGUAGES_TO_TRANSLATE:
        lang_start_time = time.time()
        print(f"--- [{lang_code}] Language Translation Start ---")

        # 1. 언어 이름 찾기 (LANG_MAP 사용)
        language_name = LANG_MAP.get(lang_code, lang_code)

        # 2. 전역 변수 GLOSSARY, FEW_SHOT_EXAMPLES 업데이트 (다운로드 포함)
        GLOSSARY = load_glossary(
            lang_code,
            GLOSSARY_URL,
            GLOSSARY_PO_FILE,
            GLOSSARY_JSON_FILE,
            GLOSSARY_DIR)

        FEW_SHOT_EXAMPLES = load_fixed_examples(
            lang_code,
            EXAMPLE_DIR,
            FIXED_EXAMPLE_JSON,
            EXAMPLE_URL,
            EXAMPLE_FILE
        )

        # 3. 결과 저장 경로 설정 (모델명/언어코드/파일명)
        model_lang_folder = os.path.join(PO_DIR, MODEL_NAME, lang_code)
        os.makedirs(model_lang_folder, exist_ok=True)
        po_file_path = os.path.join(model_lang_folder, base_name)

        # 4. 번역 실행 (language_code, language_name 전달)
        translate_pot_file(
            pot_file_path,
            po_file_path,
            lang_code,
            language_name
        )

        lang_end_time = time.time()
        duration = round(lang_end_time - lang_start_time, 2)
        print(f"---[{lang_code}] Language Translation End ({duration}s)---\n")

        # 5. 로그 기록 (language 인자 추가)
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
