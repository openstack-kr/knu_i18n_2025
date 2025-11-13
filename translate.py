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
import json
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


# entry를 5개씩 묶은 batch 단위로 번역 수행
def translate_batch(payload, language_name):
    """
    여러 entry를 batch로 묶어 LLM을 사용해 번역하는 함수.
    Translates a batch of PO/POT entries using the selected LLM model.

    Args:
        payload (tuple): (entries, batch_index, total_batches)
            entries (list): 번역 대상 메시지 객체 리스트
            batch_index (int): 현재 batch 순서
            total_batches (int): 전체 batch 수
        language_name (str): 번역하는 언어 이름

    Returns:
        list | None: [(msgid, translation, locations), ...] 또는 오류 시 None
    """
    entries, batch_idx, total_batches = payload
    
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
    
    # Few-shot 예시 추가 (batch 형식)
    example_input = [msgid for msgid, _ in FEW_SHOT_EXAMPLES]
    example_output = [msgstr for _, msgstr in FEW_SHOT_EXAMPLES]
    
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
        f"containing exactly {len(texts_to_translate)} translated strings in the same order."
        "Do NOT add any other text, explanations, or markdown formatting.\n\n"
        f"{json.dumps(texts_to_translate, ensure_ascii=False)}"
    )
    
    messages.append({"role": "user", "content": user_content})
    
    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=messages,
            stream=False,
            options={
                "temperature": 0,
                "top_p": 1,
                "repetition_penalty": 1.2,
            },
        )
        
        translation_text = response["message"]["content"].strip()
        
        # JSON 파싱 시도
        try:
            translations = json.loads(translation_text)
        except json.JSONDecodeError:
            # JSON 파싱 실패 시 대체 처리
            print(f"!!! Batch [{batch_idx + 1}/{total_batches}] JSON parsing failed, trying to extract array !!!")
            print(f"Falling back: extract simple array for this batch.")
            # 간단한 array 추출 시도
            start = translation_text.find('[')
            end = translation_text.rfind(']') + 1
            if start != -1 and end != 0:
                translations = json.loads(translation_text[start:end])
            else:
                raise ValueError("Cannot extract JSON array from response")
        
        # 번역 결과와 entry 매칭
        if len(translations) != len(entries):
            print(
                f"!!! Batch [{batch_idx + 1}/{total_batches}] "
                f"Translation count mismatch: expected {len(entries)}, got {len(translations)} !!!"
            )
            print(f"Falling back: leaving msgstr empty for this batch.")
            results = []
            for entry in entries:
                results.append((entry.id, "", entry.locations))
            return results
        
        results = []
        for entry, translation in zip(entries, translations):
            results.append((entry.id, translation.strip(), entry.locations))
        return results
        
    except Exception as e:
        print(
            f"!!! Batch [{batch_idx + 1}/{total_batches}] Error translating batch: {e} !!!"
        )
        results = []
        for entry in entries:
            results.append((entry.id, "", entry.locations)) 
        return results


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


def translate_pot_file(pot_path, po_path, language_code, language_name, batch_size=5):
    """
    POT 파일을 읽어 batch 단위로 병렬 번역 후 PO 파일로 저장하는 함수.
    Reads a .pot file, translates entries in batches in parallel, and saves as .po file.

    Args:
        pot_path (str): 원본 POT 파일 경로
        po_path (str): 번역된 결과를 저장할 PO 파일 경로
        language_code (str): 번역하는 언어 코드
        language_name (str): 번역하는 언어 이름
        batch_size (int): 한 번에 번역할 entry 개수 (기본값: 5)

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
    po.header_comment = "Initial translation by AI (batch mode).\n" + pot.header_comment

    entries_to_translate = [entry for entry in pot if entry.id]
    total_entries = len(entries_to_translate)
    
    # entry를 batch로 분할
    batches = create_batches(entries_to_translate, batch_size)
    total_batches = len(batches)

    print(f"--- {os.path.basename(pot_path)}를 {language_code}로 번역 ---")
    print(
        f"총 {total_entries}개 entry를 {total_batches}개 batch로 나누어 번역합니다. "
        f"(Batch size: {batch_size}, Workers: {MAX_WORKERS})"
    )

    # (batch, 순서, 전체 batch 수)의 payload 만들기
    payloads = [
        (batch, i, total_batches)
        for i, batch in enumerate(batches)
    ]

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(
            tqdm(
                executor.map(
                    lambda payload: translate_batch(
                        payload,
                        language_name),
                    payloads),
                total=total_batches,
                desc=f"Translating batches [{language_code}]",
                unit="batch",
            ))

    for batch_result in results:
        if batch_result:
            for msgid, translation, locations in batch_result:
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
    BATCH_SIZE = getattr(args, 'batch_size', 5)

    print("=================================================")
    print(f"번역 시작, AI 모델: {MODEL_NAME}, Batch Size: {BATCH_SIZE}")
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
            GLOSSARY_DIR
        )
        
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

        # 4. 번역 실행 (language_code, language_name, batch_size 전달)
        translate_pot_file(
            pot_file_path,
            po_file_path,
            lang_code,
            language_name,
            batch_size=BATCH_SIZE
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