import json, polib, sys

if len(sys.argv) < 3:
    print("Usage: python glossary_verify.py glossary.json target.po")
    sys.exit(1)

glossary = json.load(open(sys.argv[1]))
po = polib.pofile(sys.argv[2])

for src, tgt in glossary.items():
    for e in po:
        if tgt not in e.msgstr and src in e.msgid:
            print(f"[WARN] '{src}' 번역 누락 → '{tgt}' 예상 | line: {e.linenum}")
