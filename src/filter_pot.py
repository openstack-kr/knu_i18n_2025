#!/usr/bin/env python
import polib
import os
import argparse
from copy import deepcopy
from config_loader import load_config
from utils import is_untranslated


def extract_untranslated(source_po):
    result = polib.POFile()
    result.metadata = source_po.metadata
    for e in source_po:
        if is_untranslated(e):
            new_e = deepcopy(e)
            new_e.msgstr = ""
            new_e.msgstr_plural = {}
            result.append(new_e)
    return result


def main(translated_po_path, out_pot_path="remaining.pot"):
    trans_po = polib.pofile(translated_po_path)
    result = extract_untranslated(trans_po)
    result.save(out_pot_path)
    print(f"[+] POT saved: {out_pot_path}")
    print(f"[*] Untranslated entries: {len(result)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    cfg = load_config(args.config)
    
    languages = cfg.get("languages")

    if isinstance(languages, list):
        # 지금은 한 개만 쓴다고 가정하고 첫 번째 사용
        lang = languages[0]
    else:
        lang = languages

    files_cfg = cfg["files"]
    
    # config에서 파일명만 받음
    target_file = files_cfg["target_file"]
    # target_file (po, pot) 확장자 분리
    target_file_name, _ = os.path.splitext(target_file)
    
    # 자동으로 ./data/target 아래에서 찾도록 경로 구성
    trans_po = os.path.join(f"./data/target/{lang}", target_file)
    pot_dir = "./pot"
    os.makedirs(pot_dir, exist_ok=True)
    
    out_pot = os.path.join(pot_dir, f"{target_file_name}.pot")
    
    main(trans_po, out_pot)