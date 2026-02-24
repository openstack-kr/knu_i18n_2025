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

    def llm_score(self, msgid, translation):
        """
        Rate the quality of a single translation on a scale of 0-5.

        Returns: int (0~5)
        """
        prompt = (
            f"[Source]\n{msgid}\n\n"
            f"[Translation]\n{translation}\n\n"
            f"Rate the quality of the above translation on a scale of 0 to 5.\n"
            f"5: Perfect — accurate meaning, natural Korean\n"
            f"4: Good — correct meaning, minor awkwardness\n"
            f"3: Fair — mostly correct but some errors\n"
            f"2: Poor — mistranslation or foreign word mixing\n"
            f"1: Very poor — mostly mistranslated\n"
            f"0: Failed — not translated, repetition, or garbled output\n\n"
            f"Reply with only a single digit (0-5)."
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
                            "Reply with only a single digit: 0, 1, 2, 3, 4, or 5."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0,
            },
        )
        data = response.json()
        if "choices" not in data:
            raise RuntimeError(f"LLM Score error ({self.judge_model}): {data}")
        answer = data["choices"][0]["message"]["content"].strip()
        for ch in answer:
            if ch.isdigit() and int(ch) <= 5:
                return int(ch)
        return 0  # fallback

    def score_from_jsonl(self, jsonl_path):
        """
        Extract (model, msgid, translation) pairs from JSONL and assign 0-5 scores.
        O(models × entries) calls — efficient for many models.

        Returns:
            {model: {"avg_score": float, "entries": [{"msgid", "translation", "score"}]}}
        """
        model_entries = {}
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                ma = record["meta"]["model_a"]
                mb = record["meta"]["model_b"]
                msgid = record["source"]
                model_entries.setdefault(ma, {})[msgid] = record["candidate_a"]
                model_entries.setdefault(mb, {})[msgid] = record["candidate_b"]

        results = {}
        total_models = len(model_entries)
        for m_idx, (model, entries) in enumerate(model_entries.items(), 1):
            print(f"\n[{m_idx}/{total_models}] Scoring model: {model} ({len(entries)} entries)")
            scored = []
            for e_idx, (msgid, translation) in enumerate(entries.items(), 1):
                score = self.llm_score(msgid, translation)
                scored.append({"msgid": msgid, "translation": translation, "score": score})
                print(f"  {e_idx}/{len(entries)} score={score}")
            avg = sum(s["score"] for s in scored) / len(scored) if scored else 0
            results[model] = {"avg_score": round(avg, 2), "entries": scored}
            print(f"  → {model} avg score: {avg:.2f}")
        return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--jsonl", required=True,
        help="Path to arena_dataset.jsonl produced by po_to_arena.py"
    )
    parser.add_argument(
        "--judge-model", default=None,
        help="LLM model to use for scoring (e.g. qwen2.5:7b)"
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    evaluator = ArenaEvaluator(OPENWEBUI_URL, API_KEY, judge_model=args.judge_model)

    print(f"Score evaluation started: {args.jsonl}")
    results = {
        "mode": "score",
        "model_scores": evaluator.score_from_jsonl(args.jsonl),
    }

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nArena results saved to {args.output}")
