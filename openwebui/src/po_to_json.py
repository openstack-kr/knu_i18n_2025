#!/usr/bin/env python3
"""
PO 파일들을 하나의 JSON으로 변환 (모델별 묶음).

사용법 예시:

    python src/po_to_json.py \
      --pot pot/test2.pot \
      --po-dir po \
      --models qwen2.5:3b,llama3.2:3b \
      --lang ko_KR \
      --output results/arena_translations.json

생성되는 JSON 예시:

    {
      "qwen2.5:3b": {
        "Original msgid 1": "번역 결과 1",
        "Original msgid 2": "번역 결과 2"
      },
      "llama3.2:3b": {
        "Original msgid 1": "번역 결과 1",
        "Original msgid 2": "번역 결과 2"
      }
    }
"""

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional

from babel.messages import pofile


def load_po_as_dict(path: Path) -> Dict[str, str]:
    """PO 파일에서 msgid → msgstr 딕셔너리로 읽어온다."""
    with path.open("rb") as f:
        catalog = pofile.read_po(f)

    data: Dict[str, str] = {}
    for entry in catalog:
        if entry.id:  # msgid가 있을 때만
            msgid = entry.id[0] if isinstance(entry.id, tuple) else entry.id
            # msgstr가 None이면 ""로 강제 → 빈 번역도 그대로 유지
            data[msgid] = entry.string or ""
    return data


def read_msgids(pot_path: Path, max_entries: Optional[int] = None) -> List[str]:
    """POT에서 msgid 목록만 뽑아온다(순서 유지)."""
    with pot_path.open("rb") as f:
        catalog = pofile.read_po(f)

    msgids: List[str] = [
        e.id[0] if isinstance(e.id, tuple) else e.id
        for e in catalog
        if e.id
    ]
    if max_entries is not None:
        msgids = msgids[:max_entries]
    return msgids


def main():
    parser = argparse.ArgumentParser(
        description="PO 파일들을 하나의 JSON(모델별 묶음)으로 변환"
    )
    parser.add_argument(
        "--pot",
        required=True,
        help="원본 POT 파일 경로 (msgid 순서 기준)",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="JSON 출력 파일 경로 (예: results/arena_translations.json)",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=None,
        help="최대 entry 수 (msgid 기준, 옵션)",
    )
    parser.add_argument(
        "--po-dir",
        required=True,
        help="po/ 디렉터리 루트 경로",
    )
    parser.add_argument(
        "--models",
        required=True,
        help="콤마로 구분된 모델 이름 (예: qwen2.5:3b,llama3.2:3b)",
    )
    parser.add_argument(
        "--lang",
        default="ko_KR",
        help="언어 코드 (기본: ko_KR)",
    )

    args = parser.parse_args()

    pot_path = Path(args.pot)
    po_root = Path(args.po_dir)
    out_file = Path(args.output)

    # POT 기준 msgid 목록
    msgids = read_msgids(pot_path, args.max)

    # 모델 목록 파싱
    models = [m.strip() for m in args.models.split(",") if m.strip()]

    print("===========================================")
    print(f"POT       : {pot_path}")
    print(f"언어       : {args.lang}")
    print(f"모델 목록  : {models}")
    print(f"출력 파일  : {out_file}")
    print("===========================================\n")

    pot_stem = pot_path.stem
    all_translations: Dict[str, Dict[str, str]] = {}

    for model in models:
        po_path = po_root / model / args.lang / f"{pot_stem}.po"
        if not po_path.exists():
            raise FileNotFoundError(f"[{model}] PO 파일 없음: {po_path}")

        print(f"[{model}] PO 로드: {po_path}")
        full_dict = load_po_as_dict(po_path)

        # POT msgid 순서를 기준으로 정렬 + max 적용
        translations_ordered: Dict[str, str] = {}
        for msgid in msgids:
            # 해당 msgid가 PO에 없으면 빈 문자열로 채움
            translations_ordered[msgid] = full_dict.get(msgid, "")

        all_translations[model] = translations_ordered
        print(f"  → {model} entries: {len(translations_ordered)}")

    # 최종 하나의 JSON으로 저장
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("w", encoding="utf-8") as f:
        json.dump(all_translations, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 모든 모델 번역을 하나의 JSON으로 저장 완료: {out_file}")


if __name__ == "__main__":
    main()