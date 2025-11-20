#!/usr/bin/env python3
import polib
import sys
from copy import deepcopy

def make_key(e):
    return (e.msgctxt, e.msgid, e.msgid_plural)

def merge_translations(
    original_po_path,
    pot_file_path,
    translated_po_path,
    output_path="merged.po"
):
    print("[*] Loading files...")
    orig = polib.pofile(original_po_path)
    pot = polib.pofile(pot_file_path)
    translated = polib.pofile(translated_po_path)

    # key → entry 형태로 딕셔너리화
    orig_map = {make_key(e): e for e in orig}
    trans_map = {make_key(e): e for e in translated}
    pot_keys = {make_key(e) for e in pot}

    updated_count = 0
    missing_count = 0

    print("[*] Merging translated entries...")

    for key in pot_keys:
        if key not in orig_map:
            print(f"[WARNING] Key in POT but missing in original: {key}")
            continue

        o = orig_map[key]
        t = trans_map.get(key)

        # 원본에 이미 번역 있으면 그대로 냅둠
        if o.msgstr.strip():
            continue
        
        # 번역된 메시지가 없으면 체크 카운트 증가
        if t is None or not t.msgstr.strip():
            missing_count += 1
            continue

        # 번역 삽입
        o.msgstr = t.msgstr
        o.msgstr_plural = deepcopy(t.msgstr_plural)
        updated_count += 1

    # 저장
    orig.save(output_path)

    print(f"[+] Merge saved to {output_path}")
    print(f"[+] 새로 채워 넣은 번역 수: {updated_count}")
    print(f"[+] 아직도 미번역 상태인 msgid 수: {missing_count}")

    if missing_count > 0:
        print("[!] 경고: 아직 미번역된 항목이 남아있습니다.")
    else:
        print("[OK] 모든 항목이 성공적으로 번역되었습니다!")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python merge_translations.py <original_ru.po> <pot_file> <translated_po> [output.po]")
        sys.exit(1)

    original = sys.argv[1]
    pot = sys.argv[2]
    translated = sys.argv[3]
    out = sys.argv[4] if len(sys.argv) >= 5 else "merged.po"

    merge_translations(original, pot, translated, out)
