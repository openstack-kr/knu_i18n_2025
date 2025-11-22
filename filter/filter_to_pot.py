#!/usr/bin/env python
import sys
import polib
from copy import deepcopy

def is_translated(entry: polib.POEntry) -> bool:
    """msgstr(또는 복수형 msgstr_plural) 중 하나라도 채워져 있으면 '번역됨'으로 판단."""
    # 헤더 건드리지 않음
    if entry.msgid == "":
        return False

    # 주석 처리된 엔트리는 무시
    if entry.obsolete:
        return False

    # 복수형일 때
    if entry.msgid_plural:
        return any(s.strip() for s in entry.msgstr_plural.values())
    # 단수형일 때
    return bool(entry.msgstr.strip())

def make_key(entry: polib.POEntry):
    """msgctxt + msgid + msgid_plural 로 엔트리 식별."""
    return (entry.msgctxt, entry.msgid, entry.msgid_plural)

def main(src_po_path, translated_po_path, out_pot_path="remaining.pot"):

    src_po = polib.pofile(src_po_path)
    trans_po = polib.pofile(translated_po_path)

    # 1) 번역된 엔트리들(msgstr 채워진 것들)의 key 집합 만들기
    translated_keys = set()
    for e in trans_po:
        if is_translated(e):
            translated_keys.add(make_key(e))

    print(f"[*] 번역된 엔트리 수: {len(translated_keys)}")

    # 2) 원문 po 에서, 번역된 key 들은 제거한 새 PO 만들기
    result = polib.POFile()
    result.metadata = dict(src_po.metadata)
    result.header = src_po.header

    kept_count = 0

    for e in src_po:
        # 헤더 엔트리는 항상 유지
        if e.msgid == "":
            result.append(deepcopy(e))
            continue

        key = make_key(e)
        # 이미 번역된 항목이면 스킵
        if key in translated_keys:
            continue

        new_e = deepcopy(e)
        # 혹시라도 msgstr 가 들어있다면 템플릿 용으로 비워줌
        new_e.msgstr = ""
        new_e.msgstr_plural = {}
        # fuzzy 등 플래그도 정리
        new_e.flags = [f for f in new_e.flags if f != "fuzzy"]

        result.append(new_e)
        kept_count += 1

    print(f"[*] 남은(미번역) 엔트리 수: {kept_count}")

    # 3) 남은 엔트리를 POT 한 버전으로만 저장
    result.save(out_pot_path)

    print(f"[+] 저장 완료:")
    print(f"    POT: {out_pot_path}")

if __name__ == "__main__":
    # 사용법:
    #   python filter_to_pot.py 원문.po 번역.po [out_pot]
    if len(sys.argv) < 3:
        print("Usage: python filter_to_pot.py <source_po> <translated_po> [out_pot]")
        sys.exit(1)

    src_po = sys.argv[1]
    trans_po = sys.argv[2]
    out_pot = sys.argv[3] if len(sys.argv) >= 4 else "remaining.pot"

    main(src_po, trans_po, out_pot)