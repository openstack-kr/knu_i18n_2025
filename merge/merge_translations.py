#!/usr/bin/env python3
import polib
import sys
import os

def make_key(entry):
    """Entry를 고유하게 식별하는 key 생성 (msgctxt, msgid, msgid_plural)"""
    return (entry.msgctxt, entry.msgid, entry.msgid_plural)

def is_translated(entry):
    """msgstr(또는 복수형 msgstr_plural) 중 하나라도 채워져 있으면 '번역됨'으로 판단."""
    if entry.msgid == "":
        return True
    if entry.obsolete:
        return True
    if entry.msgid_plural:
        return any(s.strip() for s in entry.msgstr_plural.values())
    return bool(entry.msgstr.strip())

def merge_po_files(src_full_po, pot_file, translated_po, output_file):
    print(f"[+] Loading files...")
    full = polib.pofile(src_full_po)
    pot = polib.pofile(pot_file)
    translated = polib.pofile(translated_po)

    # 첫 줄/헤더 무시: msgid가 빈 엔트리는 제외
    entries_to_process = [e for e in translated if e.msgid != ""]

    # 번역 결과를 key 기준으로 딕셔너리화
    translated_map = {make_key(e): e.msgstr for e in entries_to_process}

    merged = polib.POFile()
    merged.metadata = dict(full.metadata)
    merged.header = full.header

    missing = []  # 번역이 비어있는 msgid 추적

    print("[*] Merging...")

    # POT에 있는 msgid만 교체 대상으로 사용
    pot_keys = {make_key(e) for e in pot}

    for e in full:
        key = make_key(e)

        new_e = polib.POEntry(
            msgid=e.msgid,
            msgstr=e.msgstr,
            msgctxt=e.msgctxt,
            msgid_plural=e.msgid_plural,
            occurrences=e.occurrences,
            flags=e.flags,
        )

        # 헤더는 그대로 복사
        if e.msgid == "":
            merged.append(new_e)
            continue

        # POT(미번역 목록)에 포함된 msgid라면 번역 결과로 교체
        if key in pot_keys:
            translated_str = translated_map.get(key, "").strip()

            if translated_str:
                new_e.msgstr = translated_str
            else:
                missing.append(e.msgid)  # 번역 빠진 경우 기록

        merged.append(new_e)

    merged.save(output_file)
    print(f"[+] Saved merged file: {output_file}")

    if missing:
        print("!! WARNING: Missing translations in merged file:")
        for m in missing:
            print(" -", m)
    else:
        print("[OK] No missing translations. All good!")

    return missing

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: python merge_translations.py <full.po> <extracted.pot> <translated.po> <output.po>")
        sys.exit(1)

    src_full_po   = sys.argv[1]
    pot_file      = sys.argv[2]
    translated_po = sys.argv[3]
    output_file   = sys.argv[4]

    merge_po_files(src_full_po, pot_file, translated_po, output_file)
