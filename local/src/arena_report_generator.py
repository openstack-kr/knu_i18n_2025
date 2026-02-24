"""OpenWebUI Arena 결과 기반 HTML 리포트 생성"""
import json
from datetime import datetime
import argparse

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>OpenWebUI Arena Translation Quality Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .winner {{ background-color: #90EE90; font-weight: bold; }}
        .sample {{ background-color: #f9f9f9; padding: 15px; margin: 10px 0; border-left: 4px solid #4CAF50; }}
        .arena-badge {{
            display: inline-block;
            background: #4CAF50;
            color: white;
            padding: 5px 10px;
            border-radius: 5px;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <h1>🏟️ OpenWebUI Arena Translation Quality Report</h1>
    <p><span class="arena-badge">Powered by OpenWebUI Arena & Hybrid Evaluator</span></p>

    <h2>📊 Arena ELO Leaderboard</h2>
    <table>
        <tr>
            <th>Rank</th>
            <th>Model</th>
            <th>ELO Rating</th>
            <th>Wins</th>
            <th>Losses</th>
            <th>Ties</th>
            <th>Win Rate</th>
        </tr>
        {leaderboard_rows}
    </table>

    <h2>💡 Recommendation</h2>
    <div class="sample">
        <strong>🏆 Best Model for Production: {best_model}</strong><br>
        ELO Rating: {best_elo}<br>
        Win Rate: {win_rate:.1f}%<br>
        Reason: {reason}
    </div>

    <h2>🔍 Sample Comparisons</h2>
    {sample_comparisons}

    <h2>📈 Evaluation Statistics</h2>
    <ul>
        <li>Total comparisons: {total_comparisons}</li>
        <li>Models evaluated: {model_count}</li>
        <li>Evaluation method: {eval_method}</li>
        <li>Evaluation date: {date}</li>
    </ul>
</body>
</html>
"""

def compute_local_leaderboard(comparisons):
    """API 리더보드가 비어있을 때, 파이썬이 직접 ELO를 계산합니다."""
    stats = {}
    for c in comparisons:
        for m in [c['model_a'], c['model_b']]:
            if m not in stats:
                stats[m] = {'elo': 1000.0, 'wins': 0, 'losses': 0, 'ties': 0}

    k_factor = 32
    for c in comparisons:
        a = c['model_a']
        b = c['model_b']
        winner = c['winner']

        rating_a = stats[a]['elo']
        rating_b = stats[b]['elo']
        expected_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))

        if winner == 'A':
            stats[a]['wins'] += 1
            stats[b]['losses'] += 1
            stats[a]['elo'] += k_factor * (1.0 - expected_a)
            stats[b]['elo'] -= k_factor * (1.0 - expected_a)
        elif winner == 'B':
            stats[b]['wins'] += 1
            stats[a]['losses'] += 1
            stats[a]['elo'] += k_factor * (0.0 - expected_a)
            stats[b]['elo'] -= k_factor * (0.0 - expected_a)
        else: # tie
            stats[a]['ties'] += 1
            stats[b]['ties'] += 1
            stats[a]['elo'] += k_factor * (0.5 - expected_a)
            stats[b]['elo'] -= k_factor * (0.5 - expected_a)
    return stats

def get_valid_leaderboard(raw_leaderboard, comparisons):
    """서버 API 응답을 파싱하고, 비어있으면 로컬 계산기로 우회(Fallback)합니다."""
    lb = {}
    is_local = False

    # 1. API 응답("entries": [...]) 파싱 시도
    if isinstance(raw_leaderboard, dict) and 'entries' in raw_leaderboard:
        entries = raw_leaderboard['entries']
        if isinstance(entries, list):
            for item in entries:
                name = item.get('model') or item.get('id') or 'unknown'
                elo = item.get('rating') or item.get('elo') or 1000
                lb[name] = {
                    'elo': float(elo),
                    'wins': item.get('wins', 0),
                    'losses': item.get('losses', 0),
                    'ties': item.get('ties', 0)
                }

    # 2. 파싱했는데도 비어있다면? -> 로컬 계산
    if not lb and comparisons:
        print("⚠️ API 리더보드 데이터가 비어있어, 로컬 전적 데이터로 직접 ELO를 계산합니다.")
        lb = compute_local_leaderboard(comparisons)
        is_local = True

    return lb, is_local

def generate_leaderboard_table(leaderboard):
    sorted_models = sorted(
        leaderboard.items(),
        key=lambda x: x[1].get('elo', 1000),
        reverse=True
    )

    rows = []
    for rank, (model, stats) in enumerate(sorted_models, 1):
        css_class = 'winner' if rank == 1 else ''
        elo = stats.get('elo', 1000)
        wins = stats.get('wins', 0)
        losses = stats.get('losses', 0)
        ties = stats.get('ties', 0)
        total = wins + losses + ties
        win_rate = (wins / total * 100) if total > 0 else 0

        row = f"""
        <tr class="{css_class}">
            <td>{rank}</td>
            <td>{model}</td>
            <td>{elo:.0f}</td>
            <td>{wins}</td>
            <td>{losses}</td>
            <td>{ties}</td>
            <td>{win_rate:.1f}%</td>
        </tr>
        """
        rows.append(row)
    return ''.join(rows)

def generate_sample_comparisons(translations, num_samples=20):
    samples = []
    if not translations: return "No samples available."

    msgids = list(next(iter(translations.values())).keys())[:num_samples]

    for msgid in msgids:
        sample_html = f"""
        <div class="sample">
            <strong>Original:</strong><br>
            <code>{msgid}</code><br><br>
        """
        for model, trans_dict in translations.items():
            msgstr = trans_dict.get(msgid, "N/A")
            sample_html += f"""
            <strong>{model}:</strong><br>
            <code>{msgstr}</code><br><br>
            """
        sample_html += "</div>"
        samples.append(sample_html)
    return ''.join(samples)

def generate_html_report(translations, arena_results, output_path):
    raw_lb = arena_results.get('leaderboard', {})
    comparisons = arena_results.get('comparisons', [])

    # API 데이터를 검사하고, 비어있으면 로컬 계산
    leaderboard, is_local = get_valid_leaderboard(raw_lb, comparisons)

    if leaderboard:
        best_model_name, best_stats = max(
            leaderboard.items(),
            key=lambda x: x[1].get('elo', 1000)
        )
        best_elo = best_stats.get('elo', 1000)
        wins = best_stats.get('wins', 0)
        losses = best_stats.get('losses', 0)
        ties = best_stats.get('ties', 0)
        total = wins + losses + ties
        win_rate = (wins / total * 100) if total > 0 else 0
    else:
        best_model_name = "N/A"
        best_elo = 0
        win_rate = 0

    method_str = "Local ELO Calculation (Fallback)" if is_local else "Official OpenWebUI API"

    html = HTML_TEMPLATE.format(
        leaderboard_rows=generate_leaderboard_table(leaderboard),
        best_model=best_model_name,
        best_elo=best_elo,
        win_rate=win_rate,
        reason=f"Highest ELO rating from {method_str}",
        sample_comparisons=generate_sample_comparisons(translations),
        total_comparisons=len(comparisons),
        model_count=len(leaderboard),
        eval_method=method_str,
        date=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"✅ Arena report generated: {output_path}")
    print(f"🏆 Best model: {best_model_name} (ELO: {best_elo:.0f})")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--translations", required=True)
    parser.add_argument("--arena-results", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    with open(args.translations, 'r', encoding='utf-8') as f:
        translations = json.load(f)

    with open(args.arena_results, 'r', encoding='utf-8') as f:
        arena_results = json.load(f)

    generate_html_report(translations, arena_results, args.output)