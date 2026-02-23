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
from collections import defaultdict
from datetime import datetime
from pathlib import Path


HTML_TEMPLATE = """<!DOCTYPE html>
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
        .winner-badge {{
            display: inline-block;
            background: #4CAF50; color: white;
            padding: 2px 8px; border-radius: 4px; font-size: 0.85em;
        }}
        .sample {{ background: #f9f9f9; border-left: 4px solid #4CAF50;
                   padding: 15px; margin: 15px 0; border-radius: 4px; }}
        .win-a   {{ color: #2196F3; font-weight: bold; }}
        .win-b   {{ color: #FF9800; font-weight: bold; }}
        .win-tie {{ color: #9E9E9E; }}
        .arena-badge {{
            display: inline-block; background: #4CAF50; color: white;
            padding: 5px 12px; border-radius: 5px;
        }}
        .msgid {{ font-family: monospace; font-size: 0.9em; color: #555; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin: 20px 0; }}
        .stat-card {{ background: #f0f4f8; border-radius: 8px; padding: 20px; text-align: center; }}
        .stat-num {{ font-size: 2em; font-weight: bold; color: #4CAF50; }}
    </style>
</head>
<body>
    <h1>&#127941; OpenWebUI Arena Translation Quality Report</h1>
    <p><span class="arena-badge">Powered by OpenWebUI Arena</span>
       &nbsp; 생성일시: {date}</p>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-num">{total_comparisons}</div>
            <div>총 비교 횟수</div>
        </div>
        <div class="stat-card">
            <div class="stat-num">{model_count}</div>
            <div>비교 모델 수</div>
        </div>
        <div class="stat-card">
            <div class="stat-num">{eval_method}</div>
            <div>평가 방식</div>
        </div>
    </div>

    <h2>&#128202; 모델별 성적</h2>
    <table>
        <tr>
            <th>순위</th><th>모델</th><th>승</th><th>패</th><th>무</th><th>승률</th>
        </tr>
        {leaderboard_rows}
    </table>

    <h2>&#128161; 추천 모델</h2>
    <div class="sample">
        <strong>&#127942; 최적 모델: {best_model}</strong><br>
        승률: {best_win_rate:.1f}% &nbsp;|&nbsp; 승: {best_wins} / 패: {best_losses} / 무: {best_ties}<br>
        평가 기준: 승률 기반 순위 (판정 방식: {eval_method})
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


def calc_stats(comparisons: list) -> dict:
    """comparisons 리스트에서 모델별 승/패/무 집계"""
    stats = defaultdict(lambda: {"wins": 0, "losses": 0, "ties": 0})
    for c in comparisons:
        ma, mb = c["model_a"], c["model_b"]
        winner = c.get("winner", "tie")
        if winner == "A":
            stats[ma]["wins"] += 1
            stats[mb]["losses"] += 1
        elif winner == "B":
            stats[mb]["wins"] += 1
            stats[ma]["losses"] += 1
        else:
            stats[ma]["ties"] += 1
            stats[mb]["ties"] += 1
    return dict(stats)


def leaderboard_rows_html(stats: dict) -> str:
    def win_rate(s):
        total = s["wins"] + s["losses"]
        return s["wins"] / total * 100 if total else 0

    ranked = sorted(stats.items(), key=lambda x: win_rate(x[1]), reverse=True)
    rows = []
    for rank, (model, s) in enumerate(ranked, 1):
        wr = win_rate(s)
        css = 'class="winner-row"' if rank == 1 else ""
        badge = '<span class="winner-badge">&#127942; 1위</span>' if rank == 1 else ""
        rows.append(
            f'<tr {css}><td>{rank}</td><td>{model} {badge}</td>'
            f'<td>{s["wins"]}</td><td>{s["losses"]}</td><td>{s["ties"]}</td>'
            f'<td>{wr:.1f}%</td></tr>'
        )
    return "\n".join(rows)


def sample_comparisons_html(comparisons: list, num_samples: int = 10) -> str:
    samples = []
    for c in comparisons[:num_samples]:
        winner = c.get("winner", "tie")
        if winner == "A":
            label_a = f'<span class="win-a">&#9733; 승자 ({c["model_a"]})</span>'
            label_b = f'<span>{c["model_b"]}</span>'
        elif winner == "B":
            label_a = f'<span>{c["model_a"]}</span>'
            label_b = f'<span class="win-b">&#9733; 승자 ({c["model_b"]})</span>'
        else:
            label_a = f'<span class="win-tie">{c["model_a"]} (무승부)</span>'
            label_b = f'<span class="win-tie">{c["model_b"]} (무승부)</span>'

        entry_id = c.get("id", "")
        msgid = c.get("msgid", "").replace("<", "&lt;").replace(">", "&gt;")
        trans_a = c.get("trans_a", "").replace("<", "&lt;").replace(">", "&gt;")
        trans_b = c.get("trans_b", "").replace("<", "&lt;").replace(">", "&gt;")

        samples.append(f"""
        <div class="sample">
            <strong>[{entry_id}] 원문:</strong>
            <div class="msgid">{msgid}</div>
            <br>
            <div style="padding:8px;margin:4px 0;border-left:3px solid #2196F3;">
                {label_a}<br><code>{trans_a}</code>
            </div>
            <div style="padding:8px;margin:4px 0;border-left:3px solid #FF9800;">
                {label_b}<br><code>{trans_b}</code>
            </div>
        </div>""")
    return "\n".join(samples)


def generate_html_report(arena_results: dict, output_path: Path, num_samples: int = 10):
    comparisons = arena_results.get("comparisons", [])

    # 평가 방식 추출 (첫 항목의 method 필드)
    eval_method = "heuristic"
    if comparisons and "method" in comparisons[0]:
        eval_method = comparisons[0]["method"]

    stats = calc_stats(comparisons)

    def win_rate(s):
        total = s["wins"] + s["losses"]
        return s["wins"] / total * 100 if total else 0

    if stats:
        best_model, best_s = max(stats.items(), key=lambda x: win_rate(x[1]))
    else:
        best_model, best_s = "N/A", {"wins": 0, "losses": 0, "ties": 0}

    html = HTML_TEMPLATE.format(
        date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        total_comparisons=len(comparisons),
        model_count=len(stats),
        eval_method=eval_method,
        leaderboard_rows=leaderboard_rows_html(stats),
        best_model=best_model,
        best_win_rate=win_rate(best_s),
        best_wins=best_s["wins"],
        best_losses=best_s["losses"],
        best_ties=best_s["ties"],
        num_samples=min(num_samples, len(comparisons)),
        sample_comparisons=sample_comparisons_html(comparisons, num_samples),
    )

    output_path.write_text(html, encoding="utf-8")
    print(f"HTML 리포트 생성 완료: {output_path}")
    print(f"최적 모델: {best_model} (승률: {win_rate(best_s):.1f}%)")


def main():
    parser = argparse.ArgumentParser(description="Arena 결과로 HTML 리포트 생성")
    parser.add_argument("--arena-results", required=True, help="arena_results.json 경로")
    parser.add_argument("--output", required=True, help="출력 HTML 경로")
    parser.add_argument("--samples", type=int, default=10, help="리포트에 포함할 샘플 수 (기본: 10)")
    args = parser.parse_args()

    with open(args.arena_results, "r", encoding="utf-8") as f:
        arena_results = json.load(f)

    generate_html_report(arena_results, Path(args.output), num_samples=args.samples)


if __name__ == "__main__":
    main()
