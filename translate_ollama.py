import ollama
import os
import time
import concurrent.futures
import requests
import json
from tqdm import tqdm
from babel.messages import pofile, Catalog
from utils import parse_args, init_environment, load_glossary, save_experiment_log

# 하나의 문장(entry)을 번역
def translate_entry(payload):

    entry, i, total_count = payload

    relevant_glossary_terms = {
        en: ko for en, ko in GLOSSARY.items() if en in entry.id.lower()
    }

    if relevant_glossary_terms:
        glossary_rules = (
            " Apply these translation rules: "
            + ", ".join(
                [
                    f"'{en}' must be translated as '{ko}'"
                    for en, ko in relevant_glossary_terms.items()
                ]
            )
            + "."
        )
    else:
        glossary_rules = ""

    # ai에게 전달하는 프롬프트
    messages = [
        # 1. System 역할
        {
            "role": "system",
            "content": (
                "You are a translation engine. "
                "Your only job is to translate the user's English into Korean."
                " Do not add any other words."
                " Preserve all reStructuredText (RST) syntax."
            ),
        },
        # 2. 첫 번째 예시. => 추후 예시 po 파일로 변경?
        {"role": "user", "content": "A new default has been added."},
        {"role": "assistant", "content": "새로운 기본값이 추가되었습니다."},
        # 3. 두 번째 예시. => 추후 예시 po 파일로 변경?
        {"role": "user", "content": "This is **very** important."},
        {"role": "assistant", "content": "이것은 **매우** 중요합니다."},
        # 4. 실제 번역 내용 + glossary 규칙
        {"role": "user", "content": f"{glossary_rules}\n\n{entry.id}"},
    ]

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

        translation = response["message"]["content"]

        # 번역한 문장을 삽입한 entry
        return (entry.id, translation, entry.locations)

    except Exception as e:
        print(
            (
                f"!!! [{i+1}/{total_count}] Error translating entry "
                f"'{entry.id[:30]}...': {e} !!!"
            )
        )
        return None


# pot 파일을 읽어 번역해 최종 po 파일로 저장하는 함수
def translate_pot_file(pot_path, po_path):

    with open(pot_path, "rb") as f:
        pot = pofile.read_po(f)

    po = Catalog(
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
    '''
    entries_to_translate = entries_to_translate[START_TRANSLATE:END_TRANSLATE]
    '''
    total_entries = len(entries_to_translate)

    print(f"--- {os.path.basename(pot_path)} 번역 ---")
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
                executor.map(translate_entry, payloads),
                total=total_entries,
                desc="Translating entries",
                unit="entry",
            )
        )

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
    
    print("=================================================")
    print(f"번역 시작, AI 모델: {MODEL_NAME}")
    print("=================================================\n")    
    
    # 폴더 생성 + POT/Glossary 다운로드 + 경로 계산
    pot_file_path, glossary_po_path, glossary_json_path = init_environment(
            pot_dir=POT_DIR,
            po_dir=PO_DIR,
            glossary_dir=GLOSSARY_DIR,
            pot_url=POT_URL,
            target_pot_file=TARGET_POT_FILE,
            glossary_url=GLOSSARY_URL,
            glossary_po_file=GLOSSARY_PO_FILE,
            glossary_json_file=GLOSSARY_JSON_FILE,
        )

    # 용어집 로드
    GLOSSARY = load_glossary(glossary_po_path, glossary_json_path)

    # 모델별 폴더 구성 + 파일 경로
    base_name = os.path.basename(pot_file_path).replace(".pot", ".po")
    model_folder = os.path.join(PO_DIR, MODEL_NAME)
    os.makedirs(model_folder, exist_ok=True)
    po_file_path = os.path.join(model_folder, base_name)
    
    start = time.time()
    translate_pot_file(pot_file_path, po_file_path)
    end = time.time()
    duration = round(end - start, 2)

    # Git 정보 + 로그 자동 기록
    save_experiment_log(
        model_name=MODEL_NAME,
        pot_file=pot_file_path,
        po_file=po_file_path,
        duration_sec=duration,
    )