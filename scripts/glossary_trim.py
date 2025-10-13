import json, sys
from collections import Counter

gloss = json.load(open(sys.argv[1]))
N = int(sys.argv[2])
out_path = sys.argv[3]

# 용어 사용 빈도 기반 top N (단순 key 기준)
items = list(gloss.items())[:N]

with open(out_path, "w") as f:
    f.write("### Glossary (Top terms)\n")
    for k, v in items:
        f.write(f'- "{k}" → "{v}"\n')
print(f"[OK] wrote {len(items)} terms to {out_path}")
