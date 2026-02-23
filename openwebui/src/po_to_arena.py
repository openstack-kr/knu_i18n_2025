#!/usr/bin/env python3
import argparse
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
            # plurals 안 쓴다고 가정. 
            msgid = entry.id[0] if isinstance(entry.id, tuple) else entry.id
            data[msgid] = entry.string
    return data


def main():
    parser = argparse.ArgumentParser(
        description="두 개의 PO 파일(qwen, llama)을 Arena용 JSONL로 변환"
    )
    parser.add_argument("--pot", required=True, help="원본 POT 파일 경로 (msgid 순서 기준)")
    parser.add_argument("--po-a", required=True, help="모델 A의 PO 파일 경로")
    parser.add_argument("--po-b", required=True, help="모델 B의 PO 파일 경로")
    parser.add_argument(
        "--model-a", default="qwen2.5:7b", help="모델 A 이름 (기본: qwen2.5:7b)"
    )
    parser.add_argument(
        "--model-b", default="llama3.2:3b", help="모델 B 이름 (기본: llama3.2:3b)"
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Arena에서 읽을 JSONL 출력 경로 (예: arena_dataset.jsonl)",
    )

    args = parser.parse_args()

    pot_path = Path(args.pot)
    po_a_path = Path(args.po_a)
    po_b_path = Path(args.po_b)
    out_path = Path(args.output)

    # msgid 순서를 POT에서 읽기
    with pot_path.open("rb") as f:
        pot_catalog = pofile.read_po(f)

    msgids = [e.id[0] if isinstance(e.id, tuple) else e.id
              for e in pot_catalog if e.id]

    if args.max is not None:
        msgids = msgids[: args.max]

    # 각 모델의 번역 로드
    translations_a = load_po_as_dict(po_a_path)
    translations_b = load_po_as_dict(po_b_path)

    count = 0
    with out_path.open("w", encoding="utf-8") as out_f:
        for idx, msgid in enumerate(msgids, 1):
            cand_a = translations_a.get(msgid, "").strip()
            cand_b = translations_b.get(msgid, "").strip()

            # 둘 중 하나라도 비어 있으면 스킵하거나, 비워둔 채로 넘길지 선택
            if not cand_a and not cand_b:
                continue

            record = {
                "id": f"msg-{idx}",
                "source": msgid,
                "candidate_a": cand_a,
                "candidate_b": cand_b,
                "meta": {
                    "model_a": args.model_a,
                    "model_b": args.model_b,
                },
            }
            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1

    print(f"Arena용 JSONL 생성 완료: {out_path} (총 {count}개 항목)")


if __name__ == "__main__":
    main()