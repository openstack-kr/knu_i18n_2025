"""
OpenWebUI Arena를 통한 LLM 평가
"""
import requests
import json
import os

OPENWEBUI_URL = "http://localhost:3000"
API_KEY = os.getenv("OPENWEBUI_API_KEY")

class ArenaEvaluator:
    def __init__(self, base_url, api_key, judge_model=None):
        self.base_url = base_url
        self.judge_model = judge_model
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def submit_feedback(self, model_a, model_b, msgid, trans_a, trans_b, winner):
        """
        Arena에 평가 피드백 제출

        Args:
            winner: "A", "B", or "tie"
        """
        response = requests.post(
            f"{self.base_url}/api/v1/evaluations/feedback",
            headers=self.headers,
            json={
                "type": "arena",
                "model_a": model_a,
                "model_b": model_b,
                "winner": winner,
                "content": msgid,
                "response_a": trans_a,
                "response_b": trans_b
            }
        )
        return response.json()

    def auto_evaluate_pair(self, msgid, trans_a, trans_b, glossary):
        """
        두 번역을 자동으로 비교하여 승자 결정

        간단한 규칙 기반 평가:
        1. Glossary 일관성 체크
        2. 번역 길이 적절성
        """
        score_a = 0
        score_b = 0

        # Glossary 체크
        for en_term, ko_term in glossary.items():
            if en_term in msgid:
                if ko_term in trans_a:
                    score_a += 1
                if ko_term in trans_b:
                    score_b += 1

        # 길이 비율 체크 (한국어는 1.0-1.5배가 적절)
        ratio_a = len(trans_a) / len(msgid) if len(msgid) > 0 else 0
        ratio_b = len(trans_b) / len(msgid) if len(msgid) > 0 else 0

        # 1.0-1.5 범위에 더 가까운 쪽에 점수
        if 1.0 <= ratio_a <= 1.5:
            score_a += 2
        if 1.0 <= ratio_b <= 1.5:
            score_b += 2

        # 승자 결정
        if score_a > score_b:
            return "A"
        elif score_b > score_a:
            return "B"
        else:
            return "tie"

    def llm_judge(self, msgid, trans_a, trans_b):
        """
        LLM에게 두 번역의 품질을 판단하도록 요청

        Returns: "A", "B", or "tie"
        """
        prompt = (
            f"아래 영어 원문과 두 개의 한국어 번역을 비교하세요.\n\n"
            f"[원문]\n{msgid}\n\n"
            f"[번역 A]\n{trans_a}\n\n"
            f"[번역 B]\n{trans_b}\n\n"
            f"평가 기준:\n"
            f"1. 원문 의미를 정확히 전달하는가\n"
            f"2. 자연스러운 한국어인가\n"
            f"3. 영어·외국어 단어가 불필요하게 섞이지 않았는가\n"
            f"4. 반복·오탈자·이상한 문자가 없는가\n\n"
            f"더 나은 번역이 A이면 'A', B이면 'B', 비슷하면 'tie'라고만 답하세요."
        )
        response = requests.post(
            f"{self.base_url}/api/v1/chat/completions",
            headers=self.headers,
            json={
                "model": self.judge_model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a translation quality evaluator. "
                            "Reply with exactly one word: 'A', 'B', or 'tie'."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0,
            },
        )
        data = response.json()
        if "choices" not in data:
            raise RuntimeError(f"LLM Judge 오류 ({self.judge_model}): {data}")
        answer = data["choices"][0]["message"]["content"].strip().upper()
        # 응답이 한 단어가 아닐 수 있으므로 포함 여부로 판단
        has_a = "A" in answer
        has_b = "B" in answer
        if has_a and not has_b:
            return "A"
        if has_b and not has_a:
            return "B"
        return "tie"

    def compare_from_jsonl(self, jsonl_path, glossary):
        """
        po_to_arena.py 가 생성한 JSONL 파일을 읽어 Arena에 제출

        JSONL 한 줄 형식:
          {"id":"msg-1","source":"...","candidate_a":"...","candidate_b":"...",
           "meta":{"model_a":"qwen2.5:3b","model_b":"llama3.2:3b"}}
        """
        results = []
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                model_a = record["meta"]["model_a"]
                model_b = record["meta"]["model_b"]
                msgid   = record["source"]
                trans_a = record["candidate_a"]
                trans_b = record["candidate_b"]

                if self.judge_model:
                    winner = self.llm_judge(msgid, trans_a, trans_b)
                    method = f"llm:{self.judge_model}"
                else:
                    winner = self.auto_evaluate_pair(msgid, trans_a, trans_b, glossary)
                    method = "heuristic"

                self.submit_feedback(model_a, model_b, msgid, trans_a, trans_b, winner)

                results.append({
                    "id":      record.get("id"),
                    "model_a": model_a,
                    "model_b": model_b,
                    "msgid":   msgid,
                    "trans_a": trans_a,
                    "trans_b": trans_b,
                    "winner":  winner,
                    "method":  method,
                })
                print(f"  {record.get('id')} | winner: {winner}  [{method}]")
        return results

    def compare_all_models(self, translations, glossary):
        """
        모든 모델 쌍을 비교하고 Arena에 제출
        """
        models = list(translations.keys())
        results = []

        for i in range(len(models)):
            for j in range(i + 1, len(models)):
                model_a = models[i]
                model_b = models[j]

                print(f"Comparing {model_a} vs {model_b}...")

                # 첫 10개 entry만 비교 (시간 절약)
                msgids = list(translations[model_a].keys())[:10]

                for msgid in msgids:
                    trans_a = translations[model_a][msgid]
                    trans_b = translations[model_b][msgid]

                    winner = self.auto_evaluate_pair(
                        msgid, trans_a, trans_b, glossary
                    )

                    self.submit_feedback(
                        model_a, model_b,
                        msgid, trans_a, trans_b,
                        winner
                    )

                    results.append({
                        "model_a": model_a,
                        "model_b": model_b,
                        "msgid": msgid,
                        "winner": winner
                    })

        return results

    def get_leaderboard(self):
        """Arena 리더보드 조회"""
        response = requests.get(
            f"{self.base_url}/api/v1/evaluations/leaderboard",
            headers=self.headers
        )
        return response.json()

    def export_all_feedbacks(self):
        """모든 평가 결과 내보내기"""
        response = requests.get(
            f"{self.base_url}/api/v1/evaluations/feedbacks/all/export",
            headers=self.headers
        )
        return response.json()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    # JSONL 입력 (po_to_arena.py 출력)
    parser.add_argument(
        "--jsonl", default=None,
        help="po_to_arena.py 가 생성한 arena_dataset.jsonl 경로"
    )
    # 기존 JSON 입력 (openwebui_translator.py 출력)
    parser.add_argument(
        "--translations", default=None,
        help="openwebui_translator.py 가 생성한 translations.json 경로"
    )
    parser.add_argument("--glossary", default=None)
    parser.add_argument(
        "--judge-model", default=None,
        help="평가에 사용할 LLM 모델 (예: qwen2.5:7b). 미지정 시 규칙 기반 평가."
    )
    parser.add_argument("--submit-feedback", action="store_true")
    parser.add_argument("--get-leaderboard", action="store_true")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    if not args.jsonl and not args.translations:
        parser.error("--jsonl 또는 --translations 중 하나는 반드시 지정해야 합니다.")

    evaluator = ArenaEvaluator(OPENWEBUI_URL, API_KEY, judge_model=args.judge_model)

    glossary = {}
    if args.glossary:
        with open(args.glossary, 'r', encoding='utf-8') as f:
            glossary = json.load(f)

    results = {}

    if args.jsonl:
        # --- JSONL 경로: po_to_arena.py 출력을 직접 평가 ---
        print(f"JSONL 파일에서 Arena 평가 제출 중: {args.jsonl}")
        comparison_results = evaluator.compare_from_jsonl(args.jsonl, glossary)
        results['comparisons'] = comparison_results
    elif args.submit_feedback:
        # --- 기존 JSON 경로 ---
        print("Submitting feedback to Arena...")
        with open(args.translations, 'r', encoding='utf-8') as f:
            translations = json.load(f)
        comparison_results = evaluator.compare_all_models(translations, glossary)
        results['comparisons'] = comparison_results

    if args.get_leaderboard:
        print("Fetching leaderboard...")
        leaderboard = evaluator.get_leaderboard()
        results['leaderboard'] = leaderboard

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"Arena results saved to {args.output}")