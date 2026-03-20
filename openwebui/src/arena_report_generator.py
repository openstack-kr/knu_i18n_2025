#!/usr/bin/env python3
"""
OpenWebUI Arena 결과 기반 HTML 리포트 생성

Usage:
    python src/arena_report_generator.py \
        --arena-results results/arena_results.json \
        --output results/report.html
"""
import argparse
import json
from datetime import datetime
from pathlib import Path


SCORE_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>OpenWebUI Arena Translation Quality Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; color: #333; }}
        h1, h2 {{ color: #2c3e50; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .winner-row {{ background-color: #d4edda; font-weight: bold; }}
        .winner-badge {{ background: #4CAF50; color: white; padding: 2px 8px; border-radius: 4px; font-size: .85em; }}
        .sample {{ background: #f9f9f9; border-left: 4px solid #4CAF50; padding: 15px; margin: 15px 0; border-radius: 4px; }}
        .msgid {{ font-family: monospace; font-size: .9em; color: #555; }}
        .arena-badge {{ background: #4CAF50; color: white; padding: 5px 12px; border-radius: 5px; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(3,1fr); gap: 20px; margin: 20px 0; }}
        .stat-card {{ background: #f0f4f8; border-radius: 8px; padding: 20px; text-align: center; }}
        .stat-num {{ font-size: 2em; font-weight: bold; color: #4CAF50; }}
    </style>
</head>
<body>
    <h1>&#127941; OpenWebUI Arena Translation Quality Report</h1>
    <p><span class="arena-badge">점수제 평가 (0~5점)</span> &nbsp; 생성일시: {date}</p>
    <div class="stats-grid">
        <div class="stat-card"><div class="stat-num">{model_count}</div><div>비교 모델 수</div></div>
        <div class="stat-card"><div class="stat-num">{total_entries}</div><div>평가 항목 수</div></div>
        <div class="stat-card"><div class="stat-num">{eval_method}</div><div>판정 모델</div></div>
    </div>
    <h2>&#128202; 모델 순위 (평균 점수)</h2>
    <table>
        <tr><th>순위</th><th>모델</th><th>평균 점수</th><th>점수 바</th><th>항목 수</th></tr>
        {leaderboard_rows}
    </table>
    <h2>&#128161; 추천 모델</h2>
    <div class="sample">
        <strong>&#127942; 최적 모델: {best_model}</strong><br>
        평균 점수: {best_score:.2f} / 5.0 &nbsp;|&nbsp; 판정 모델: {eval_method}
    </div>
    <h2>&#128269; 샘플 비교 ({num_samples}개)</h2>
    {sample_comparisons}
    <h2>&#128279; 링크</h2>
    <ul>
        <li><a href="http://localhost:3000" target="_blank">OpenWebUI Dashboard</a></li>
        <li><a href="http://localhost:3000/arena" target="_blank">Arena Interface</a></li>
    </ul>
</body>
</html>
"""


def score_leaderboard_rows_html(model_scores: dict) -> str:
    ranked = sorted(model_scores.items(), key=lambda x: x[1]["avg_score"], reverse=True)
    rows = []
    for rank, (model, data) in enumerate(ranked, 1):
        avg = data["avg_score"]
        css = 'class="winner-row"' if rank == 1 else ""
        badge = '<span class="winner-badge">&#127942; 1위</span>' if rank == 1 else ""
        bar = "&#9632;" * int(avg) + "&#9633;" * (5 - int(avg))
        rows.append(
            f'<tr {css}><td>{rank}</td><td>{model} {badge}</td>'
            f'<td style="font-size:1.2em">{avg:.2f} / 5.0</td>'
            f'<td style="color:#4CAF50">{bar}</td>'
            f'<td>{len(data["entries"])}개</td></tr>'
        )
    return "\n".join(rows)


def score_sample_html(model_scores: dict, num_samples: int = 5) -> str:
    all_models = list(model_scores.keys())
    if not all_models:
        return ""
    first_entries = model_scores[all_models[0]]["entries"][:num_samples]

    samples = []
    for entry in first_entries:
        msgid = entry["msgid"].replace("<", "&lt;").replace(">", "&gt;")
        sample_html = f'<div class="sample"><strong>원문:</strong><div class="msgid">{msgid}</div><br>'
        for model in all_models:
            m_entries = {e["msgid"]: e for e in model_scores[model]["entries"]}
            if entry["msgid"] in m_entries:
                e = m_entries[entry["msgid"]]
                trans = e["translation"].replace("<", "&lt;").replace(">", "&gt;")
                score = e["score"]
                color = ["#e74c3c","#e67e22","#f1c40f","#2ecc71","#27ae60","#1a8a4a"][score]
                sample_html += (
                    f'<div style="padding:6px;margin:3px 0;border-left:3px solid {color}">'
                    f'<span style="color:{color};font-weight:bold">{model} [{score}/5]</span><br>'
                    f'<code>{trans}</code></div>'
                )
        sample_html += "</div>"
        samples.append(sample_html)
    return "\n".join(samples)


def model_scores_from_matches(matches: list, translations: dict) -> dict:
    """elo_matches.json (승자 목록) → model_scores 포맷 변환.
    승률을 0~5 점수로 환산: (wins + 0.5*ties) / total * 5
    """
    stats: dict = {}
    for m in matches:
        for key in ("model_a", "model_b"):
            name = m[key]
            if name not in stats:
                stats[name] = {"wins": 0, "losses": 0, "ties": 0, "msgids": []}

        winner = m.get("winner")
        mA, mB = m["model_a"], m["model_b"]
        msgid = m.get("msgid", "")

        if winner == "A":
            stats[mA]["wins"] += 1
            stats[mB]["losses"] += 1
        elif winner == "B":
            stats[mB]["wins"] += 1
            stats[mA]["losses"] += 1
        else:
            stats[mA]["ties"] += 1
            stats[mB]["ties"] += 1

        if msgid not in stats[mA]["msgids"]:
            stats[mA]["msgids"].append(msgid)
        if msgid not in stats[mB]["msgids"]:
            stats[mB]["msgids"].append(msgid)

    model_scores = {}
    for model, s in stats.items():
        total = s["wins"] + s["losses"] + s["ties"]
        avg_score = (s["wins"] + 0.5 * s["ties"]) / total * 5 if total > 0 else 0.0
        entries = []
        for msgid in s["msgids"]:
            trans = translations.get(model, {}).get(msgid, "")
            entries.append({"msgid": msgid, "translation": trans, "score": round(avg_score)})
        model_scores[model] = {"avg_score": avg_score, "entries": entries}

    return model_scores


def generate_html_report(matches: list, translations: dict, output_path: Path,
                         judge_model: str = "llm", num_samples: int = 10):
    model_scores = model_scores_from_matches(matches, translations)
    eval_method = judge_model
    best_model = max(model_scores, key=lambda m: model_scores[m]["avg_score"]) if model_scores else "N/A"
    best_score = model_scores[best_model]["avg_score"] if best_model != "N/A" else 0
    total_entries = len(next(iter(model_scores.values()))["entries"]) if model_scores else 0

    html = SCORE_HTML_TEMPLATE.format(
        date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        model_count=len(model_scores),
        total_entries=total_entries,
        eval_method=eval_method,
        leaderboard_rows=score_leaderboard_rows_html(model_scores),
        best_model=best_model,
        best_score=best_score,
        num_samples=min(num_samples, total_entries),
        sample_comparisons=score_sample_html(model_scores, num_samples),
    )
    output_path.write_text(html, encoding="utf-8")
    print(f"HTML 리포트 생성 완료: {output_path}")
    print(f"최적 모델: {best_model} (평균 점수: {best_score:.2f}/5.0)")


def main():
    parser = argparse.ArgumentParser(description="Arena 결과로 HTML 리포트 생성")
    parser.add_argument("--elo-matches", required=True, help="elo_matches.json 경로")
    parser.add_argument("--translations", required=True, help="arena_translations.json 경로")
    parser.add_argument("--judge-model", default="llm", help="판정 모델 이름 (표시용)")
    parser.add_argument("--output", required=True, help="출력 HTML 경로")
    parser.add_argument("--samples", type=int, default=10, help="리포트에 포함할 샘플 수 (기본: 10)")
    args = parser.parse_args()

    with open(args.elo_matches, "r", encoding="utf-8") as f:
        matches = json.load(f)
    with open(args.translations, "r", encoding="utf-8") as f:
        translations = json.load(f)

    generate_html_report(matches, translations, Path(args.output),
                         judge_model=args.judge_model, num_samples=args.samples)


if __name__ == "__main__":
    main()
