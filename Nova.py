import os
import requests
import polib
import time
import json

OLLAMA_API_URL = "http://127.0.0.1:11434/api/chat"
MODEL_NAME = "llama3.2:1b"

TARGET_LANGUAGES = [
    'ko'
]

POT_URL = 'https://tarballs.opendev.org/openstack/translation-source/nova/master/releasenotes/source/locale/releasenotes.pot'
GLOSSARY_URL = 'https://opendev.org/openstack/openstack-manuals/raw/branch/master/doc/common/glossary.rst'
POT_FILENAME = 'nova_releasenotes.pot'
OUTPUT_DIR = 'po_nova_translated'

# 번역 할 .rst 파일 다운로드
def download_file(url, filename):
    if os.path.exists(filename):
        print(f"'{filename}' 파일이 이미 존재합니다. 다운로드를 건너뜁니다.")
        return True
    print(f"파일 다운로드 중: {url}")
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        with open(filename, 'wb') as f:
            f.write(response.content)
        print("다운로드 완료.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"파일 다운로드 실패: {e}")
        return False

# Glossary 다운로드
def download_and_parse_glossary(url):
    print(f"온라인 용어집 다운로드 중: {url}")
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        content = response.text
        terms = []
        in_glossary_block = False
        for line in content.splitlines():
            if line.strip().startswith('.. glossary::'):
                in_glossary_block = True
                continue
            if in_glossary_block and line.strip() and not line.startswith(('    ', '\t')):
                term = line.strip().replace(':', '').strip()
                if term:
                    terms.append(term)
        print(f"온라인 용어집에서 {len(terms)}개의 용어를 찾았습니다.")
        return terms
    except requests.exceptions.RequestException as e:
        print(f"온라인 용어집 다운로드 실패: {e}")
        return []

def ollama_translate(msgid: str, system_message: str, model_name: str, language_name: str) -> str:
    """Ollama API를 호출하여 번역을 수행합니다."""

    # 프롬프트
    user_prompt = f"""
    Your task is to translate the provided English technical text into professional, natural-sounding {language_name}.

    Follow these rules strictly:
    1. Translate the entire English text exactly as provided. Do not add or remove any content.
    2. Maintain all technical placeholders, symbols, formatting characters, and newline markers.
    3. The output must contain ONLY the translated text, nothing else.

    ENGLISH TEXT:
    {msgid}
    """

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_prompt}
        ],
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_ctx": 4096, # Llama 3.2 
            "num_predict": 512,
        }
    }

    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()

        return data.get("message", {}).get("content", "").strip()

    except requests.exceptions.RequestException as e:
        print(f"\n[ERROR] Ollama API 호출 실패: {e}")
        return ""


def main():
    if not download_file(POT_URL, POT_FILENAME):
        return

    print(f"Ollama 모델 '{MODEL_NAME}'을 사용하여 번역을 시작합니다.")
    print("Ollama 서버가 실행 중인지 확인해주세요.")

    online_glossary_terms = download_and_parse_glossary(GLOSSARY_URL)

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    lang_map = { 'ko': 'Korean' }

    for lang in TARGET_LANGUAGES:
        language_name = lang_map.get(lang, lang)
        print(f"\n[{language_name}] 언어 번역 시작...")

        po_lang = polib.pofile(POT_FILENAME)
        po_lang.metadata['Language'] = lang
        po_lang.metadata['Content-Type'] = 'text/plain; charset=UTF-8'

        overall_start_time = time.time()
        
        translated_count = 0
        entries_to_translate = [e for e in po_lang if e.msgid and not e.msgstr]
        total_entries = len(entries_to_translate)
        
        for i, entry in enumerate(entries_to_translate):
            if TRANSLATE_LIMIT > 0 and translated_count >= TRANSLATE_LIMIT:
                print(f"\n{TRANSLATE_LIMIT}개 항목만 테스트 번역을 진행하고 중단합니다.")
                break
            
            print(f"[{lang}] Translating... ({i + 1}/{total_entries})", end='\r')

            system_message = "You are a highly skilled technical translator, translating software documentation from English to Korean. Your sole task is to provide a direct, accurate, and professional translation."

            translated_text = ollama_translate(
                entry.msgid,
                system_message,
                MODEL_NAME,
                language_name
            )

            if translated_text:
                entry.msgstr = translated_text
                translated_count += 1
        
        print() 

        overall_end_time = time.time()
        total_duration = overall_end_time - overall_start_time

        output_filename = os.path.join(OUTPUT_DIR, f"{lang}.po")
        po_lang.save(output_filename)
        print(f"\n[{language_name}] 번역 완료. 파일 저장: {output_filename}")
        print(f"[{language_name}] 총 번역 시간: {total_duration:.2f}초 ({translated_count}개 항목 번역됨)")


if __name__ == '__main__':
    main()

