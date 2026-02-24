#!/usr/bin/env python3
"""
PO 파일들을 Arena용 JSONL로 변환.

두 가지 사용법:
  1) 다중 모델 자동 pairwise (권장):
     python src/po_to_arena.py \
       --pot pot/test2.pot \
       --po-dir po \
       --models qwen2.5:3b,llama3.2:3b \
       --lang ko_KR \
       --output results/arena_dataset.jsonl

  2) 2개 모델 직접 지정 (기존 방식):
     python src/po_to_arena.py \
       --pot pot/test2.pot \
       --po-a po/qwen2.5:3b/ko_KR/test2.po \
       --po-b po/llama3.2:3b/ko_KR/test2.po \
       --model-a qwen2.5:3b --model-b llama3.2:3b \
       --output results/arena_dataset.jsonl
"""
import argparse
import itertools
import json
from pathlib import Path
from babel.messages import pofile


def load_po_as_dict(path: Path) -> dict[str, str]:
    """PO 파일에서 msgid → msgstr 딕셔너리로 읽어온다."""
    with path.open("rb") as f:
        catalog = pofile.read_po(f)
    data = {}
    for entry in catalog:
        if entry.id and entry.string:
            msgid = entry.id[0] if isinstance(entry.id, tuple) else entry.id
            data[msgid] = entry.string
    return data


def read_msgids(pot_path: Path, max_entries: int | None = None) -> list[str]:
    with pot_path.open("rb") as f:
        catalog = pofile.read_po(f)
    msgids = [
        e.id[0] if isinstance(e.id, tuple) else e.id
        for e in catalog if e.id
    ]
    if max_entries is not None:
        msgids = msgids[:max_entries]
    return msgids


def write_pairs(msgids, model_pairs, out_path: Path):
    """
    model_pairs: [(model_a, trans_dict_a, model_b, trans_dict_b), ...]
    """
    count = 0
    with out_path.open("w", encoding="utf-8") as f:
        for model_a, trans_a, model_b, trans_b in model_pairs:
            for idx, msgid in enumerate(msgids, 1):
                cand_a = trans_a.get(msgid, "").strip()
                cand_b = trans_b.get(msgid, "").strip()
                if not cand_a and not cand_b:
                    continue
                record = {
                    "id": f"{model_a}vs{model_b}-{idx}",
                    "source": msgid,
                    "candidate_a": cand_a,
                    "candidate_b": cand_b,
                    "meta": {"model_a": model_a, "model_b": model_b},
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                count += 1
    return count


def main():
    parser = argparse.ArgumentParser(
        description="PO 파일들을 Arena용 JSONL로 변환 (2개 또는 다중 모델)"
    )
    parser.add_argument("--pot", required=True, help="원본 POT 파일 경로 (msgid 순서 기준)")
    parser.add_argument("--output", required=True, help="출력 JSONL 경로")
    parser.add_argument("--max", type=int, default=None, help="최대 entry 수")

    # --- 다중 모델 모드 ---
    parser.add_argument("--po-dir", default=None,
                        help="po/ 디렉토리 경로 (--models와 함께 사용)")
    parser.add_argument("--models", default=None,
                        help="콤마로 구분된 모델 이름 (예: qwen2.5:3b,llama3.2:3b)")
    parser.add_argument("--lang", default="ko_KR",
                        help="언어 코드 (기본: ko_KR)")

    # --- 2개 모델 직접 지정 모드 (기존 방식) ---
    parser.add_argument("--po-a", default=None, help="모델 A의 PO 파일 경로")
    parser.add_argument("--po-b", default=None, help="모델 B의 PO 파일 경로")
    parser.add_argument("--model-a", default=None, help="모델 A 이름")
    parser.add_argument("--model-b", default=None, help="모델 B 이름")

    args = parser.parse_args()

    pot_path = Path(args.pot)
    out_path = Path(args.output)
    msgids = read_msgids(pot_path, args.max)

    # --- 모드 판별 ---
    if args.models and args.po_dir:
        # 다중 모델 자동 pairwise
        models = [m.strip() for m in args.models.split(",") if m.strip()]
        po_dir = Path(args.po_dir)
        pot_stem = pot_path.stem  # e.g. "test2"

        # 각 모델의 PO 파일 로드
        translations = {}
        for model in models:
            po_path = po_dir / model / args.lang / f"{pot_stem}.po"
            if not po_path.exists():
                raise FileNotFoundError(f"PO 파일 없음: {po_path}")
            translations[model] = load_po_as_dict(po_path)
            print(f"  로드: {po_path}")

        # 모든 pairwise 조합 생성
        pairs = list(itertools.combinations(models, 2))
        print(f"  pairwise 조합: {pairs}")

        model_pairs = [
            (a, translations[a], b, translations[b])
            for a, b in pairs
        ]

    elif args.po_a and args.po_b:
        # 2개 직접 지정 모드
        model_a = args.model_a or Path(args.po_a).parent.parent.name
        model_b = args.model_b or Path(args.po_b).parent.parent.name
        model_pairs = [(
            model_a, load_po_as_dict(Path(args.po_a)),
            model_b, load_po_as_dict(Path(args.po_b)),
        )]

    else:
        parser.error(
            "--models + --po-dir 또는 --po-a + --po-b 중 하나를 지정하세요."
        )

    count = write_pairs(msgids, model_pairs, out_path)
    print(f"Arena용 JSONL 생성 완료: {out_path} (총 {count}개 항목)")


if __name__ == "__main__":
    main()
