#!/usr/bin/env python3
import re, sys, json, polib, pathlib
from typing import Dict, List, Tuple

USAGE = "Usage: glossary_apply.py glossary.json in.po out.po [--dry]"

def compile_term_patterns(terms: Dict[str,str]) -> List[Tuple[re.Pattern,str,str]]:
    """
    msgid 안에 src(영문 용어)가 나타나면 msgstr에 tgt(번역어)가 들어있도록 강제.
    - 단어경계 \b 사용
    - 대소문자, 간단 복수형(s/es) 커버
    """
    rules = []
    for src, tgt in terms.items():
        # 공백/하이픈/언더스코어 변형 대비(간단)
        src_alt = re.escape(src)
        src_alt = src_alt.replace(r"\-", r"[- ]?").replace(r"\s+", r"[ _-]?")
        # 단어 경계 + 복수형 허용
        pat = re.compile(rf"\b{src_alt}(?:e?s)?\b", re.IGNORECASE)
        rules.append((pat, src, tgt))
    return rules

def ensure_header(po: polib.POFile):
    po.metadata.setdefault("Content-Type", "text/plain; charset=UTF-8")
    po.metadata.setdefault("Language", "ko")
    if "charset=UTF-8" not in po.metadata["Content-Type"]:
        po.metadata["Content-Type"] = "text/plain; charset=UTF-8"

def apply_glossary(gloss: Dict[str,str], in_po: str, out_po: str, dry=False):
    po = polib.pofile(in_po)
    ensure_header(po)
    rules = compile_term_patterns(gloss)

    changed = 0
    for e in po:
        if not e.msgid or not e.msgstr:
            continue
        original = e.msgstr
        # msgid에 용어가 등장할 때만 교정(오탐 감소)
        for pat, src, tgt in rules:
            if pat.search(e.msgid) and tgt not in e.msgstr:
                # 간단치환: 영문 src가 msgstr에 남았으면 번역어로 바꾸기
                # msgstr에도 영문 src가 보이면 치환, 없으면 그대로(문장 훼손 방지)
                if pat.search(e.msgstr):
                    e.msgstr = pat.sub(tgt, e.msgstr)
        if e.msgstr != original:
            changed += 1

    if dry:
        print(f"[DRY] would change {changed} entries (no file written).")
        return
    pathlib.Path(out_po).parent.mkdir(parents=True, exist_ok=True)
    po.save(out_po)
    print(f"[OK] wrote: {out_po} (changed {changed} entries)")

def main():
    if len(sys.argv) < 4:
        print(USAGE); sys.exit(1)
    gloss_path, in_po, out_po = sys.argv[1:4]
    dry = ("--dry" in sys.argv[4:])
    gloss = json.load(open(gloss_path))
    apply_glossary(gloss, in_po, out_po, dry=dry)

if __name__ == "__main__":
    main()
