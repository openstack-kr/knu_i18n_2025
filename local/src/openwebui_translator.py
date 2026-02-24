# translate.py 와 연결하기?
# config.yaml 로 인자 관리하기?

import requests
import json
import os
import time

# .env 파일에서 키를 직접 읽어오는 함수 (라이브러리 의존성 줄임)
def load_env_key():
    try:
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
        with open(env_path, 'r') as f:
            for line in f:
                if line.strip().startswith('OPENWEBUI_API_KEY'):
                    # 등호(=) 뒤의 값을 가져오고, 앞뒤 공백/따옴표 제거
                    key = line.split('=', 1)[1].strip().strip('"').strip("'")
                    return key
    except Exception as e:
        print(f"⚠️ .env 파일을 읽는 중 오류: {e}")
    return None

# 설정
OPENWEBUI_URL = "http://localhost:3000"
API_KEY = load_env_key()

if not API_KEY:
    print("❌ 오류: local/.env 파일에서 OPENWEBUI_API_KEY를 찾을 수 없습니다.")
    exit(1)

class OpenWebUITranslator:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        # Bearer 토큰 방식 헤더 설정
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def translate_entry(self, model, msgid, system_prompt):
        """단일 문장 번역 요청"""
        try:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Translate this to Korean:\n{msgid}"}
                ],
                "temperature": 0.1,
                "stream": False
            }

            response = requests.post(
                f"{self.base_url}/api/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()

            # 응답 파싱
            result = response.json()
            if "choices" in result:
                return result["choices"][0]["message"]["content"].strip()
            else:
                return f"Error: 예상치 못한 응답 형식 - {result}"

        except Exception as e:
            return f"Error: {str(e)}"

    def translate_with_all_models(self, pot_file, models):
        """
        여러 모델로 번역 진행 (limit 제한 제거됨)
        """
        import polib

        print(f"📂 파일 읽는 중: {pot_file}")
        try:
            pot = polib.pofile(pot_file)
            entries = [e for e in pot if e.msgid]
        except Exception as e:
            print(f"⚠️ polib로 파일을 읽을 수 없어 임시 테스트 데이터를 사용합니다. ({e})")
            class MockEntry:
                def __init__(self, id): self.msgid = id
            entries = [MockEntry("Hello world"), MockEntry("This is a test")]

        all_results = {}

        for model in models:
            print(f"\n🤖 모델 시작: {model} (총 {len(entries)}개 문장)")
            model_results = {}

            for i, entry in enumerate(entries):
                print(f"   [{i+1}/{len(entries)}] 번역 중... ", end="", flush=True)

                start_time = time.time()
                translated_text = self.translate_entry(
                    model,
                    entry.msgid,
                    "You are a professional technical translator. Translate the following text into Korean. Do not add explanations."
                )
                end_time = time.time()

                print(f"완료 ({end_time - start_time:.2f}s)")
                model_results[entry.msgid] = translated_text

            all_results[model] = model_results

        return all_results

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--pot", required=True, help="입력 POT 파일 경로")
    parser.add_argument("--models", required=True, help="사용할 모델 (콤마로 구분)")
    parser.add_argument("--output", required=True, help="결과 저장할 JSON 파일 경로")
    args = parser.parse_args()

    # 모델 리스트 분리 (공백 제거)
    models = [m.strip() for m in args.models.split(',')]

    translator = OpenWebUITranslator(OPENWEBUI_URL, API_KEY)
    results = translator.translate_with_all_models(args.pot, models)

    # 결과 저장
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n🎉 모든 작업 완료! 결과가 저장되었습니다: {args.output}")