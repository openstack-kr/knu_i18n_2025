#!/usr/bin/env python
import sys
import polib
import os
import argparse
from copy import deepcopy
from config_loader import load_config

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

    dir_path = os.path.dirname(translated_po_path)
    if dir_path and (not os.path.isdir(dir_path) or not os.path.isfile(translated_po_path)):
        os.makedirs(dir_path, exist_ok=True)
        print(f"[+] Created directory: {dir_path}")

        # 비어 있는 번역 po 파일 생성
        with open(translated_po_path, "w", encoding="utf-8") as f:
            pass
        print(f"[+] Created empty po file: {translated_po_path}")

        # src_po_path 기준으로 POT 위치 계산
        parts = src_po_path.split("/")
        doc, country, detail, filename = parts[-4:]
        pot_path = f"./data/target/{doc}/{filename.replace('.po', '.pot')}"

        # 기존 POT가 있으면 msgstr 비우기
        if os.path.isfile(pot_path):
            po = polib.pofile(pot_path)
            for e in po:
                e.msgstr = ""
                e.msgstr_plural = {}
            po.save(pot_path)
            print(f"[=] Cleared POT msgstr: {pot_path}")
        else:
            print(f"[!] POT not found: {pot_path}")

        # 새 언어 초기화만 하고 여기서 끝냄
        return

    
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config_local.yaml")
    args = parser.parse_args()

    cfg = load_config(args.config)

    project = cfg["project"]
    languages = cfg.get("languages")

    if isinstance(languages, list):
        # 지금은 한 개만 쓴다고 가정하고 첫 번째 사용
        lang = languages[0]
    else:
        lang = languages

    files_cfg = cfg["files"]

    origin_po = files_cfg["origin_po"].format(
        project=project,
        languages=lang,
        language=lang,
        lang=lang,
    )
    trans_po = files_cfg["origin_trans_po"].format(
        project=project,
        languages=lang,
        language=lang,
        lang=lang,
    )
    out_pot = files_cfg["ai_target_pot"].format(
        project=project,
        languages=lang,
        language=lang,
        lang=lang,
    )
    pot_dir = files_cfg["pot_dir"].format(
        project=project,
        languages=lang,
        language=lang,
        lang=lang,
    )

    os.makedirs(pot_dir, exist_ok=True)
    main(origin_po, trans_po, out_pot)
