"""
OpenWebUI API를 통한 여러 LLM 번역
"""
import requests
import json
import os

OPENWEBUI_URL = "http://133.186.134.236:3000"
API_KEY = os.getenv("OPENWEBUI_API_KEY")

class OpenWebUITranslator:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def translate_entry(self, model, msgid, system_prompt):
        """단일 entry 번역"""
        response = requests.post(
            f"{self.base_url}/api/chat/completions",
            headers=self.headers,
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": msgid}
                ],
                "temperature": 0
            }
        )
        return response.json()["choices"][0]["message"]["content"]

    def translate_batch(self, model, entries):
        """배치 번역"""
        results = {}
        for entry in entries:
            msgstr = self.translate_entry(
                model,
                entry.id,
                "Translate English RST to Korean"
            )
            results[entry.id] = msgstr
        return results

    def translate_with_all_models(self, pot_file, models):
        """모든 모델로 번역"""
        from babel.messages import pofile

        with open(pot_file, 'rb') as f:
            pot = pofile.read_po(f)

        entries = [e for e in pot if e.id]

        all_results = {}
        for model in models:
            print(f"Translating with {model}...")
            all_results[model] = self.translate_batch(model, entries)

        return all_results

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--pot", required=True)
    parser.add_argument("--models", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    translator = OpenWebUITranslator(OPENWEBUI_URL, API_KEY)
    models = args.models.split(',')

    results = translator.translate_with_all_models(args.pot, models)

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)