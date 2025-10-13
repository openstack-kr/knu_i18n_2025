#!/usr/bin/env python3
import polib, json, pathlib, sys
if len(sys.argv)<4:
    print("Usage: merge_chunks_to_po.py original.pot outdir/ out.po")
    sys.exit(1)

pot=polib.pofile(sys.argv[1])
outdir=pathlib.Path(sys.argv[2])
out=polib.POFile()
mapping={}
for f in sorted(outdir.glob("*.json")):
    data=json.load(open(f))
    for d in data:
        mapping[d["msgid"]]=d.get("msgstr","")

for e in pot:
    if e.msgid in mapping:
        e.msgstr=mapping[e.msgid]
    out.append(e)
out.save(sys.argv[3])
print("✅ merged:",sys.argv[3])
