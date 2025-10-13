#!/usr/bin/env python3
# scripts/split_pot.py
import polib, pathlib, json, sys

if len(sys.argv) < 3:
    print("Usage: split_pot.py input.pot outdir/")
    sys.exit(1)

INPUT  = sys.argv[1]
OUTDIR = pathlib.Path(sys.argv[2])
OUTDIR.mkdir(parents=True, exist_ok=True)

# ✅ 실제로 청크 크기를 조절하는 것은 'BATCH_SIZE'
BATCH_SIZE = 20   # ← 50에서 줄이기 (더 안정: 10)

po = polib.pofile(INPUT)

batch = []
batch_idx = 1

def flush():
    global batch, batch_idx
    if not batch:
        return
    path = OUTDIR / f"batch_{batch_idx:04d}.json"
    path.write_text(json.dumps(batch, ensure_ascii=False, indent=2))
    batch = []
    batch_idx += 1

for e in po:
    if not e.msgid:
        continue
    batch.append({"msgid": e.msgid, "msgctxt": e.msgctxt or ""})
    if len(batch) >= BATCH_SIZE:
        flush()

flush()  # ✅ 마지막 남은 항목 저장
print(f"✅ Split complete: {OUTDIR} (files: {batch_idx-1}, batch_size={BATCH_SIZE})")
