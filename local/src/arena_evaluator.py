import json
import os
import sys
import requests
import argparse

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(project_root)

try:
    from local.src.utils import load_glossary
except ImportError:
    print("❌ 오류: 'local/src/utils.py'를 찾을 수 없습니다.")
    sys.exit(1)

def load_env_key():
    try:
        env_path = os.path.join(project_root, 'local', '.env')
        with open(env_path, 'r') as f:
            for line in f:
                if line.strip().startswith('OPENWEBUI_API_KEY'):
                    return line.split('=', 1)[1].strip().strip('"').strip("'")
    except:
        pass
    return os.getenv("OPENWEBUI_API_KEY")

OPENWEBUI_URL = "http://localhost:3000"
API_KEY = load_env_key()

class ArenaEvaluator:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def submit_feedback(self, model_a, model_b, msgid, trans_a, trans_b, winner):
        payload = {
            "type": "arena",
            "model_a": model_a,
            "model_b": model_b,
            "winner": winner,
            "content": msgid,
            "response_a": trans_a,
            "response_b": trans_b
        }

        try:
            response = requests.post(
                f"{self.base_url}/api/v1/evaluations/feedback",
                headers=self.headers,
                json=payload,
                timeout=5
            )
            if response.status_code != 200:
                print(f"   ❌ API 제출 실패 ({response.status_code}): {response.text[:100]}")
                return None
            return response.json()
        except Exception as e:
            print(f"   ❌ API 연결 오류: {e}")
            return None

    def auto_evaluate_pair(self, msgid, trans_a, trans_b, glossary):
        score_a = 0
        score_b = 0
        import re

        # ---------------------------------------------------------
        # 1. 변수 보존 체크 (-100점)
        # ---------------------------------------------------------
        format_patterns = r"(%s|%d|%\(\w+\)s|\{\w+\})"
        vars_in_src = re.findall(format_patterns, msgid)
        for var in vars_in_src:
            if var not in trans_a: score_a -= 100
            if var not in trans_b: score_b -= 100

        # ---------------------------------------------------------
        # 2. 화이트리스트 기반 외계어 차단 (-100점)
        # "특수기호/공백(\W), 숫자(\d), 밑줄(_), 한글(가-힣), 영문(a-zA-Z)"이
        # 아닌 문자가 하나라도 있으면 적발! (한자, 베트남어, 특수문자 등 한방에 차단)
        # ---------------------------------------------------------
        alien_pattern = re.compile(r'[^\W\d_가-힣a-zA-Z]')

        if alien_pattern.search(trans_a): score_a -= 100
        if alien_pattern.search(trans_b): score_b -= 100

        # ---------------------------------------------------------
        # 3. 구조 및 길이 기반 쓰레기 텍스트 차단 (-50점)
        # ---------------------------------------------------------
        # 원본에 줄바꿈이 없는데, 번역본에 줄바꿈이 생겼다면 (설명 추가, 포맷 파괴)
        if '\n' not in msgid:
            if '\n' in trans_a: score_a -= 50
            if '\n' in trans_b: score_b -= 50

        # 번역본이 원본보다 비정상적으로 길다면 (3배 초과)
        len_src = len(msgid)
        if len_src > 0:
            if len(trans_a) > len_src * 3: score_a -= 50
            if len(trans_b) > len_src * 3: score_b -= 50

        # ---------------------------------------------------------
        # 4. [기본] 한국어 필수 포함 (-50점)
        # ---------------------------------------------------------
        has_korean_a = bool(re.search(r"[가-힣]", trans_a))
        has_korean_b = bool(re.search(r"[가-힣]", trans_b))
        if not has_korean_a: score_a -= 50
        if not has_korean_b: score_b -= 50

        # ---------------------------------------------------------
        # 5. [가산점] 용어집(Glossary) 준수 (+10점)
        # ---------------------------------------------------------
        msgid_lower = msgid.lower()
        for en_term, ko_term in glossary.items():
            if len(en_term) > 2 and en_term in msgid_lower:
                if ko_term in trans_a: score_a += 10
                if ko_term in trans_b: score_b += 10

        # ---------------------------------------------------------
        # 최종 승자 판정
        # ---------------------------------------------------------
        if score_a > score_b: return "model_a"
        elif score_b > score_a: return "model_b"
        else: return "tie"

    def compare_all_models(self, translations, glossary):
        models = list(translations.keys())
        results = []
        print(f"🏟️ 비교 시작: {models}")

        for i in range(len(models)):
            for j in range(i + 1, len(models)):
                model_a = models[i]
                model_b = models[j]

                # 원본 딕셔너리의 전체 키를 가져옴
                msgids = list(translations[model_a].keys())
                print(f"   🥊 {model_a} vs {model_b} 진행 중... (총 {len(msgids)}개 문장)")

                # 전체 문장을 순회하며 평가
                for msgid in msgids:
                    trans_a = translations[model_a].get(msgid, "")
                    trans_b = translations[model_b].get(msgid, "")

                    api_winner = self.auto_evaluate_pair(msgid, trans_a, trans_b, glossary)

                    self.submit_feedback(
                        model_a, model_b,
                        msgid, trans_a, trans_b,
                        api_winner
                    )

                    results.append({
                        "model_a": model_a,
                        "model_b": model_b,
                        "msgid": msgid,
                        "winner": "A" if api_winner == "model_a" else ("B" if api_winner == "model_b" else "tie"),
                        "trans_a": trans_a,
                        "trans_b": trans_b
                    })
        return results

    def get_leaderboard(self):
        """Arena 리더보드 조회"""
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/evaluations/leaderboard",
                headers=self.headers,
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ API에서 리더보드 가져오기 성공!")
                return data
            else:
                print(f"   ❌ 리더보드 조회 실패: {response.status_code} - {response.text[:50]}")
                return {}
        except Exception as e:
            print(f"   ❌ 리더보드 연결 오류: {e}")
            return {}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--translations", required=True)
    parser.add_argument("--glossary", required=False)
    parser.add_argument("--submit-feedback", action="store_true")
    parser.add_argument("--get-leaderboard", action="store_true")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    print("📚 용어집(Glossary) 로드 중...")
    glossary_data = load_glossary("ko_KR")

    if not glossary_data:
        glossary_data = {}

    evaluator = ArenaEvaluator(OPENWEBUI_URL, API_KEY)

    with open(args.translations, 'r', encoding='utf-8') as f:
        translations = json.load(f)

    results = {}

    if args.submit_feedback:
        print("🚀 Arena API에 피드백 전송 시작...")
        comparison_results = evaluator.compare_all_models(translations, glossary_data)
        results['comparisons'] = comparison_results

    if args.get_leaderboard:
        print("🏆 API에서 리더보드 데이터 요청 중...")
        leaderboard = evaluator.get_leaderboard()
        results['leaderboard'] = leaderboard

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"🎉 평가 완료! 데이터가 저장되었습니다: {args.output}")