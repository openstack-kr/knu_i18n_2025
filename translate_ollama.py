import polib
import ollama
import os
import time
import concurrent.futures
import requests
from tqdm import tqdm

MODEL_NAME = "llama3.2:3b"
POT_DIR = "./pot"
PO_DIR = "./po"
GLOSSARY_DIR = "./glossary"

POT_URL = "https://tarballs.opendev.org/openstack/translation-source/swift/master/releasenotes/source/locale/releasenotes.pot"
TARGET_POT_FILE = 'releasenotes_swift.pot'
GLOSSARY_URL = "https://opendev.org/openstack/i18n/raw/commit/129b9de7be12740615d532591792b31566d0972f/glossary/locale/ko_KR/LC_MESSAGES/glossary.po"
GLOSSARY_FILE = "glossary_ko.po"

MAX_WORKERS = 8
START_TRANSLATE = 300
END_TRANSLATE = 320

# --- 다운로드 기능 ---
# pot, po, glossary 폴더가 없으면 생성
os.makedirs(POT_DIR, exist_ok=True)
os.makedirs(PO_DIR, exist_ok=True)
os.makedirs(GLOSSARY_DIR, exist_ok=True)
pot_file_path = os.path.join(POT_DIR, TARGET_POT_FILE)
glossary_file_path = os.path.join(GLOSSARY_DIR, GLOSSARY_FILE)

print(f"Downloading pot file from {POT_URL}...")
try:
    response = requests.get(POT_URL, timeout=30)
    response.raise_for_status() # HTTP 오류가 있으면 예외 발생
    with open(pot_file_path, 'wb') as f:
        f.write(response.content)
    print(f"Successfully downloaded and saved to {pot_file_path}")
except requests.exceptions.RequestException as e:
    print(f"Error downloading file: {e}")
    exit() # 파일 다운로드 실패 시 스크립트 종료

print(f"Downloading glossary file from {GLOSSARY_URL}...")
try:
    response = requests.get(GLOSSARY_URL, timeout=30)
    response.raise_for_status()
    with open(glossary_file_path, 'wb') as f:
        f.write(response.content)
    print(f"Successfully downloaded and saved to {glossary_file_path}\n")
except requests.exceptions.RequestException as e:
    print(f"Warning: Could not download glossary file: {e}\n")
# --- 다운로드 끝 ---
    
GLOSSARY = {}
if os.path.exists(glossary_file_path):
    print("Loading glossary...")
    glossary_po = polib.pofile(glossary_file_path)
    GLOSSARY = {entry.msgid.lower(): entry.msgstr for entry in glossary_po if entry.translated()}
    print(f"Glossary loaded with {len(GLOSSARY)} terms.\n")


def translate_entry(payload): #하나의 문장(entry)을 번역
    
    entry, i, total_count = payload
    
    relevant_glossary_terms = {en: ko for en, ko in GLOSSARY.items() if en in entry.msgid.lower()}
    
    if relevant_glossary_terms:
        glossary_rules = " Apply these translation rules: " + ", ".join([f"'{en}' must be translated as '{ko}'" for en, ko in relevant_glossary_terms.items()]) + "."
    else:
        glossary_rules = ""

    # ai에게 전달하는 프롬프트
    messages = [
        # 1. System 역할
        {
            "role": "system",
            "content": "You are a translation engine. Your one and only job is to translate the user's English text into formal Korean. Do not add any other words. Preserve all reStructuredText (RST) syntax."
        },

        # 2. 첫 번째 예시. => 추후 예시 po 파일로 변경?
        {
            "role": "user",
            "content": "A new default has been added."
        },
        {
            "role": "assistant",
            "content": "새로운 기본값이 추가되었습니다."
        },

        # 3. 두 번째 예시. => 추후 예시 po 파일로 변경?
        {
            "role": "user",
            "content": "This is **very** important."
        },
        {
            "role": "assistant",
            "content": "이것은 **매우** 중요합니다."
        },

        # 4. 실제 번역 내용 + glossary 규칙
        {
            "role": "user",
            "content": f"{glossary_rules}\n\n{entry.msgid}"
        }
    ]
    
    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=messages,
            stream=False,
            options={
                'temperature': 0.3,
                'top_p': 0.95,
                'repetition_penalty': 1.2,
                "stop": ["\n"]
            }
        )
        
        translation = response['message']['content']

        # 번역한 문장을 삽입한 entry
        new_entry = polib.POEntry(
            msgid=entry.msgid,
            msgstr=translation,
            occurrences=entry.occurrences
        )
        return new_entry

    except Exception as e:
        print(f"!!! [{i+1}/{total_count}] Error translating entry '{entry.msgid[:30]}...': {e} !!!")
        return None


def translate_pot_file(pot_path, po_path): # pot 파일을 읽어 번역해 최종 po 파일로 저장하는 함수
    pot = polib.pofile(pot_path)
    po = polib.POFile()
    po.metadata = pot.metadata
    po.header = "This is a translation translated by AI.\n" + po.header

    entries_to_translate = [entry for entry in pot if entry.msgid]
    #entries_to_translate = entries_to_translate[START_TRANSLATE:END_TRANSLATE]
    total_entries = len(entries_to_translate) 

    print(f"--- {os.path.basename(pot_path)} 번역 ---")
    print(f"총 {total_entries} 라인의 번역입니다. {MAX_WORKERS} 개의 병렬 코어를 사용합니다.")

    # (entry, 순서, 전체 개수) 의 payload 만들기
    payloads = [(entry, i, total_entries) for i, entry in enumerate(entries_to_translate)]

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # payload 전달, tqdm으로 진행률 표시
        results = list(
            tqdm(
                executor.map(translate_entry, payloads),
                total=total_entries,
                desc="Translating entries",
                unit="entry"
            )
        )

    for new_entry in results:
        po.append(new_entry)

    po.save(po_path)
    print(f"{po_path}가 저장되었습니다.")


if __name__ == "__main__":
    print("=================================================")
    print(f"번역 시작, AI 모델: {MODEL_NAME}")
    print("=================================================\n")

    pot_file = os.path.join(POT_DIR, TARGET_POT_FILE)

    translate_start_time = time.time()
            
    base_name = os.path.basename(pot_file).replace('.pot', '.po')
    po_file = os.path.join(PO_DIR, base_name)
            
    translate_pot_file(pot_file, po_file)

    translate_end_time = time.time()
    print(f"{translate_end_time - translate_start_time:.2f} 초 번역했습니다.\n")