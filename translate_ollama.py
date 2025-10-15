import ollama
import os
import time
import concurrent.futures
import requests
import json
from tqdm import tqdm
from babel.messages import pofile, Catalog

MODEL_NAME = "llama3.2:3b"
POT_DIR = "./pot"
PO_DIR = "./po"
GLOSSARY_DIR = "./glossary"

POT_URL = (
    "https://tarballs.opendev.org/openstack/translation-source/swift/"
    "master/releasenotes/source/locale/releasenotes.pot"
)
TARGET_POT_FILE = "releasenotes_swift.pot"
GLOSSARY_URL = (
    "https://opendev.org/openstack/i18n/raw/commit/"
    "129b9de7be12740615d532591792b31566d0972f/glossary/locale/ko_KR/"
    "LC_MESSAGES/glossary.po"
)
GLOSSARY_PO_FILE = "glossary_ko.po"
GLOSSARY_JSON_FILE = "glossary_ko.json"

MAX_WORKERS = 8
START_TRANSLATE = 300
END_TRANSLATE = 320

# --- 다운로드 기능 ---
# pot, po, glossary 폴더가 없으면 생성
os.makedirs(POT_DIR, exist_ok=True)
os.makedirs(PO_DIR, exist_ok=True)
os.makedirs(GLOSSARY_DIR, exist_ok=True)
pot_file_path = os.path.join(POT_DIR, TARGET_POT_FILE)
glossary_po_path = os.path.join(GLOSSARY_DIR, GLOSSARY_PO_FILE)
glossary_json_path = os.path.join(GLOSSARY_DIR, GLOSSARY_JSON_FILE)

if not os.path.exists(pot_file_path):
    print(f"Downloading pot file from {POT_URL}...")
    try:
        response = requests.get(POT_URL, timeout=30)
        response.raise_for_status()  # HTTP 오류가 있으면 예외 발생
        with open(pot_file_path, "wb") as f:
            f.write(response.content)
        print(f"Successfully downloaded and saved to {pot_file_path}")
    except requests.exceptions.RequestException as e:
        print(f"Error downloading file: {e}")
        exit()  # 파일 다운로드 실패 시 스크립트 종료
else:
    print(f"'{TARGET_POT_FILE}' already exists. skipping download.")

if not os.path.exists(pot_file_path):
    print(f"Downloading glossary file from {GLOSSARY_URL}...")
    try:
        response = requests.get(GLOSSARY_URL, timeout=30)
        response.raise_for_status()
        with open(glossary_po_path, "wb") as f:
            f.write(response.content)
        print(f"Successfully downloaded and saved to {glossary_po_path}\n")
    except requests.exceptions.RequestException as e:
        print(f"Warning: Could not download glossary file: {e}\n")
else:
    print(f"'{GLOSSARY_PO_FILE}' already exists. skipping download.\n")

# --- 다운로드 끝 ---

GLOSSARY = {}
if os.path.exists(glossary_po_path):
    print("Converting glossary.po -> glossary.json...")
    try:
        with open(glossary_po_path, "rb") as f:
            glossary_po = pofile.read_po(f)
        glossary_dict = {
            entry.id.strip().lower(): entry.string.strip()
            for entry in glossary_po
            if entry.id and entry.string
        }

        with open(glossary_json_path, "w", encoding="utf-8") as f:
            json.dump(glossary_dict, f, ensure_ascii=False, indent=2)
        print(f"Converted JSON to {glossary_json_path}")

        with open(glossary_json_path, "r", encoding="utf-8") as f:
            GLOSSARY = json.load(f)
        print(f"Glossary loaded from JSON ({len(GLOSSARY)} terms)\n")
    except Exception as e:
        print(f"Error reading Glossary file: {e}\n")


def translate_entry(payload):  # 하나의 문장(entry)을 번역

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
                "temperature": 0.3,
                "top_p": 0.95,
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


def translate_pot_file(
    pot_path, po_path
):  # pot 파일을 읽어 번역해 최종 po 파일로 저장하는 함수

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
    entries_to_translate = entries_to_translate[START_TRANSLATE:END_TRANSLATE]
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
    print("=================================================")
    print(f"번역 시작, AI 모델: {MODEL_NAME}")
    print("=================================================\n")

    pot_file = os.path.join(POT_DIR, TARGET_POT_FILE)

    translate_start_time = time.time()

    base_name = os.path.basename(pot_file).replace(".pot", ".po")
    po_file = os.path.join(PO_DIR, base_name)

    translate_pot_file(pot_file, po_file)

    translate_end_time = time.time()
    print(
        f"{translate_end_time - translate_start_time:.2f} 초 번역했습니다.\n"
    )
