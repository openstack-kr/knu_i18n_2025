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

def translate_entry(payload, language_name):
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
        f"총 {total_entries}개 entry를 번역합니다. "
        f"(Workers: {MAX_WORKERS})"
    )

    # (entry, 순서, 전체 수)의 payload 만들기
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
    args = parse_args()
    MODEL_NAME = args.model
    POT_DIR = args.pot_dir
    PO_DIR = args.po_dir
    GLOSSARY_DIR = args.glossary_dir
    START_TRANSLATE = args.start
    END_TRANSLATE = args.end
    MAX_WORKERS = args.workers
    POT_URL = args.pot_url
    TARGET_POT_FILE = args.target_pot_file
    GLOSSARY_URL = args.glossary_url
    GLOSSARY_PO_FILE = args.glossary_po_file
    GLOSSARY_JSON_FILE = args.glossary_json_file
    LANGUAGES_TO_TRANSLATE = args.languages.split(',')

    print("=================================================")
    print(f"번역 시작, AI 모델: {MODEL_NAME}")
    print("=================================================\n")

    # 폴더 생성 + POT 다운로드
    pot_file_path = init_environment(
        pot_dir=POT_DIR,
        po_dir=PO_DIR,
        glossary_dir=GLOSSARY_DIR,
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

        # 2. 전역 변수 GLOSSARY 업데이트 (다운로드 포함)
        GLOSSARY = load_glossary(
            lang_code,
            GLOSSARY_URL,
            GLOSSARY_PO_FILE,
            GLOSSARY_JSON_FILE,
            GLOSSARY_DIR)

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
