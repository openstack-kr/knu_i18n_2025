"""
arena_score.py (LLM-only + 내부 매치 파일 기반 ELO)

- LLM 기반 번역 품질 평가 (0~5점)
- 점수 비교로 A/B 승자 결정
- Arena 서버로 POST 전송 없음 (완전히 제거됨)
- ELO 계산은 내부 매치 파일(JSON) 기준으로 수행
"""

import json
import os
import requests

OPENWEBUI_URL = "http://localhost:3000"
API_KEY = os.getenv("OPENWEBUI_API_KEY")


class ArenaEvaluator:
    def __init__(self, judge_model: str):
        if not judge_model:
            raise ValueError("judge-model must be provided for LLM-based evaluation.")
        self.judge_model = judge_model

    # ---------------------------------------------------
    # 1) LLM 기반 번역 점수: 0~5
    # ---------------------------------------------------
    def llm_score(self, msgid: str, translation: str) -> int:
        prompt = (
            f"[Source]\n{msgid}\n\n"
            f"[Translation]\n{translation}\n\n"
            f"Rate the quality of the above translation on a scale of 0 to 5.\n"
            f"Reply with only a single digit (0-5)."
        )

        if not API_KEY:
            print("[WARN] OPENWEBUI_API_KEY 가 설정되어 있지 않습니다. 0점으로 처리합니다.")
            return 0

        url = f"{OPENWEBUI_URL}/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        }

        try:
            resp = requests.post(
                url,
                headers=headers,
                json={
                    "model": self.judge_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a translation quality evaluator. "
                                "Reply with only one digit: 0, 1, 2, 3, 4, or 5."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0,
                },
                timeout=60,
            )
        except Exception as e:
            print(f"[WARN] LLM request failed ({url}): {e}")
            return 0

        # HTTP 에러 응답 처리
        if resp.status_code != 200:
            preview = resp.text[:200].replace("\n", " ")
            print(f"[WARN] LLM HTTP {resp.status_code}: {preview!r}")
            return 0

        # JSON 파싱 방어
        try:
            data = resp.json()
        except Exception as e:
            preview = resp.text[:200].replace("\n", " ")
            print(f"[WARN] LLM JSON parse error: {e} | body={preview!r}")
            return 0

        if not isinstance(data, dict) or "choices" not in data or not data["choices"]:
            print(f"[WARN] Unexpected LLM response: {data!r}")
            return 0

        text = str(data["choices"][0]["message"]["content"]).strip()

        for ch in text:
            if ch.isdigit():
                val = int(ch)
                if 0 <= val <= 5:
                    return val

        print(f"[WARN] Could not parse score from: {text!r}")
        return 0

    # ---------------------------------------------------
    # 2) LLM 기반 승자 결정
    # ---------------------------------------------------
    def auto_evaluate_pair_llm(self, msgid, trans_a, trans_b):
        s_a = self.llm_score(msgid, trans_a)
        s_b = self.llm_score(msgid, trans_b)

        print(f"    LLM scores: A={s_a}, B={s_b}")

        if s_a > s_b:
            return "A"
        elif s_b > s_a:
            return "B"
        return "tie"

    # ---------------------------------------------------
    # 3) 모델 전체 쌍 비교(POST 없음)
    # ---------------------------------------------------
    def compare_all_models(self, translations):
        models = list(translations.keys())
        comparisons = []

        for i in range(len(models)):
            for j in range(i + 1, len(models)):
                mA = models[i]
                mB = models[j]
                print(f"\n### Comparing {mA} vs {mB} ###")

                for msgid in translations[mA].keys():
                    tA = translations[mA].get(msgid, "")
                    tB = translations[mB].get(msgid, "")

                    winner = self.auto_evaluate_pair_llm(msgid, tA, tB)

                    comparisons.append({
                        "model_a": mA,
                        "model_b": mB,
                        "msgid": msgid,
                        "winner": winner
                    })

        return comparisons

    # ---------------------------------------------------
    # 4) ELO 계산
    # ---------------------------------------------------
    def compute_elo(self, matches):
        stats = {}
        k = 32

        for m in matches:
            a = m["model_a"]
            b = m["model_b"]
            w = m["winner"]

            for name in (a, b):
                if name not in stats:
                    stats[name] = {"elo": 1000.0, "wins": 0, "losses": 0, "ties": 0}

            Ra = stats[a]["elo"]
            Rb = stats[b]["elo"]
            Ea = 1 / (1 + 10 ** ((Rb - Ra) / 400))

            if w == "A":
                stats[a]["wins"] += 1
                stats[b]["losses"] += 1
                stats[a]["elo"] += k * (1 - Ea)
                stats[b]["elo"] -= k * (1 - Ea)
            elif w == "B":
                stats[b]["wins"] += 1
                stats[a]["losses"] += 1
                stats[a]["elo"] += k * (0 - Ea)
                stats[b]["elo"] -= k * (0 - Ea)
            else:
                stats[a]["ties"] += 1
                stats[b]["ties"] += 1
                stats[a]["elo"] += k * (0.5 - Ea)
                stats[b]["elo"] -= k * (0.5 - Ea)

        return stats

    # ---------------------------------------------------
    # 5) 콘솔 ELO 출력
    # ---------------------------------------------------
    def print_elo(self, stats):
        ranking = sorted(stats.items(), key=lambda x: x[1]["elo"], reverse=True)
        print("\n📈 ELO Ranking")
        print("========================")
        for i, (model, s) in enumerate(ranking, 1):
            print(f"{i}. {model:20s} | ELO={s['elo']:.1f} | W-L-T={s['wins']}-{s['losses']}-{s['ties']}")


# ---------------------------------------------------
# 실행부
# ---------------------------------------------------
if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--translations", required=True)
    p.add_argument("--judge-model", required=True)
    p.add_argument("--elo-data", required=False)
    p.add_argument("--submit-feedback", action="store_true")  # 의미는 비교 수행 여부
    p.add_argument("--output", required=True)
    args = p.parse_args()

    evaluator = ArenaEvaluator(judge_model=args.judge_model)

    with open(args.translations, "r", encoding="utf-8") as f:
        translations = json.load(f)

    # 새 비교 결과
    new_matches = []
    if args.submit_feedback:
        new_matches = evaluator.compare_all_models(translations)

    # 기존 매치 파일 로드
    all_matches = []
    if args.elo_data and os.path.exists(args.elo_data):
        with open(args.elo_data, "r", encoding="utf-8") as f:
            all_matches = json.load(f)

    # 병합
    all_matches.extend(new_matches)

    # 저장
    if args.elo_data:
        with open(args.elo_data, "w", encoding="utf-8") as f:
            json.dump(all_matches, f, ensure_ascii=False, indent=2)

    # ELO 계산
    elo_stats = evaluator.compute_elo(all_matches)
    evaluator.print_elo(elo_stats)

    # Output 저장
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({
            "comparisons": new_matches,
            "elo": elo_stats,
        }, f, ensure_ascii=False, indent=2)