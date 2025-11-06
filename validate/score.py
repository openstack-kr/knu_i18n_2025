# -*- coding: utf-8 -*-
"""
Compare two PO files semantically using SimCSE.
- Match entries by key: (msgctxt, msgid, plural_index)
- Encode with SimCSE (SentenceTransformers) and compute cosine similarity
- Save JSON report
- Update ONLY the LAST row of experiments.csv with summary metrics
- (Optional) Auto-select latest .po via --b-latest-in [--b-pattern]

Usage examples:
  python score.py --a base.po --b new.po --out result.json
  python score.py --a base.po --b-latest-in po/ko_KR --out result.json --b-pattern guide.po
"""

from __future__ import annotations
from datetime import datetime
import argparse
import csv
import io
import json
import re
import statistics
import sys
from pathlib import Path

import polib
import torch
from sentence_transformers import SentenceTransformer, util
from babel.messages.pofile import read_po as babel_read_po


# --------------------------
# Utilities
# --------------------------
def normalize_text(s: str, do_norm: bool = False, do_lower: bool = False) -> str:
    if s is None:
        s = ""
    if do_norm:
        s = re.sub(r"\s+", " ", s.strip())
    if do_lower:
        s = s.lower()
    return s


def load_po_entries(path: Path, only_translated=False, skip_fuzzy=False,
                    do_norm=False, do_lower=False):
    """
    Return dict: key -> string
      key = (context, msgid, plural_index)
    Try polib first; on failure, fallback to babel.
    """
    def _from_polib(po):
        m = {}
        for e in po:
            if e.obsolete:
                continue
            if e.msgid == "" and not e.msgid_plural:  # header
                continue
            if skip_fuzzy and "fuzzy" in (e.flags or []):
                continue
            if e.msgid_plural:
                if e.msgstr_plural:
                    for idx, s in sorted(e.msgstr_plural.items(), key=lambda kv: int(kv[0])):
                        s = normalize_text(s, do_norm, do_lower)
                        if only_translated and s == "":
                            continue
                        m[(e.msgctxt or "", e.msgid, int(idx))] = s
                else:
                    s = normalize_text("", do_norm, do_lower)
                    if not (only_translated and s == ""):
                        m[(e.msgctxt or "", e.msgid, 0)] = s
            else:
                s = normalize_text(e.msgstr, do_norm, do_lower)
                if only_translated and s == "":
                    continue
                m[(e.msgctxt or "", e.msgid, 0)] = s
        return m

    try:
        po = polib.pofile(str(path), wrapwidth=0)
        return _from_polib(po)
    except Exception:
        # Fallback to babel
        raw = path.read_bytes().lstrip(b"\xef\xbb\xbf")
        text = raw.decode("utf-8", errors="ignore")
        if not text.lstrip().startswith('msgid ""'):
            text = 'msgid ""\nmsgstr ""\n\n' + text
        cat = babel_read_po(io.StringIO(text), locale=None)
        m = {}
        for msg in cat:
            if msg.id is None:
                continue
            ctx = msg.context or ""
            if isinstance(msg.id, tuple):  # plural
                strings = msg.string if isinstance(msg.string, tuple) else (msg.string,)
                for idx, s in enumerate(strings):
                    s = normalize_text(s, do_norm, do_lower)
                    if only_translated and s == "":
                        continue
                    m[(ctx, msg.id[0], idx)] = s
            else:
                s = normalize_text(msg.string, do_norm, do_lower)
                if only_translated and s == "":
                    continue
                m[(ctx, msg.id, 0)] = s
        return m


def batched(iterable, n: int):
    for i in range(0, len(iterable), n):
        yield iterable[i:i + n]


def find_latest_po(directory: Path, pattern: str | None = None) -> Path:
    """Pick the most recently modified .po under directory. Optional substring filter."""
    if not directory.exists():
        print(f"[ERROR] directory not found: {directory}", file=sys.stderr)
        sys.exit(1)
    cands = []
    for p in directory.rglob("*.po"):
        if pattern and pattern not in str(p):
            continue
        cands.append(p)
    if not cands:
        print(f"[ERROR] no .po found in {directory} (pattern={pattern})", file=sys.stderr)
        sys.exit(1)
    cands.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    latest = cands[0]
    print(f"[auto] Selected latest PO: {latest}")
    return latest


# --------------------------
# Main
# --------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True, help="Baseline/reference PO file")
    ap.add_argument("--b", help="Target PO file to compare")
    ap.add_argument("--b-latest-in", help="Directory to auto-pick the latest PO")
    ap.add_argument("--b-pattern", help="Substring to filter when picking latest PO")
    ap.add_argument("--out", required=True, help="Path (ignored name; JSON saved under validate/json/<po>_timestamp.json)")
    ap.add_argument("--model", default="princeton-nlp/sup-simcse-roberta-base")
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--threshold", type=float, default=0.80)
    ap.add_argument("--only-translated", action="store_true")
    ap.add_argument("--skip-fuzzy", action="store_true")
    ap.add_argument("--normalize-text", action="store_true")
    ap.add_argument("--lowercase", action="store_true")
    ap.add_argument("--topk", type=int, default=20)
    ap.add_argument("--experiments_csv",
                    default=str(Path(__file__).resolve().parent.parent / "experiments.csv"))
    args = ap.parse_args()

    pa = Path(args.a)
    if not pa.exists():
        print(f"[ERROR] file not found: {pa}", file=sys.stderr)
        sys.exit(1)

    if args.b_latest_in:
        pb = find_latest_po(Path(args.b_latest_in), args.b_pattern)
    elif args.b:
        pb = Path(args.b)
    else:
        print("[ERROR] Must specify either --b or --b-latest-in", file=sys.stderr)
        sys.exit(1)

    if not pb.exists():
        print(f"[ERROR] file not found: {pb}", file=sys.stderr)
        sys.exit(1)

    # --- Load entries
    A = load_po_entries(pa, args.only_translated, args.skip_fuzzy,
                        args.normalize_text, args.lowercase)
    B = load_po_entries(pb, args.only_translated, args.skip_fuzzy,
                        args.normalize_text, args.lowercase)

    common_keys = sorted(set(A.keys()) & set(B.keys()))
    if not common_keys:
        print("[WARN] No overlapping msgid keys.", file=sys.stderr)

    pairs = [(k, A[k], B[k]) for k in common_keys]

    # --- Model
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SentenceTransformer(args.model, device=device)

    sims: list[float] = []

    def encode_texts(texts):
        return model.encode(texts, convert_to_tensor=True, normalize_embeddings=True)

    for batch in batched(pairs, args.batch_size):
        a_texts = [p[1] for p in batch]
        b_texts = [p[2] for p in batch]
        emb_a = encode_texts(a_texts)
        emb_b = encode_texts(b_texts)
        cos = util.cos_sim(emb_a, emb_b).diag().tolist()
        sims.extend(cos)

    # --- Stats
    if sims:
        avg = float(sum(sims) / len(sims))
        med = float(statistics.median(sims))
        p90 = float(statistics.quantiles(sims, n=10)[-1]) if len(sims) >= 10 else None
        ratio = 100.0 * sum(1 for s in sims if s >= args.threshold) / len(sims)
    else:
        avg = med = ratio = 0.0
        p90 = None

    # --- JSON out
    out_dir = Path("validate/json")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    pout = out_dir / f"{pb.stem}_{ts}.json"

    report = {
        "metadata": {
            "file_a": str(pa),
            "file_b": str(pb),
            "model": args.model,
            "device": device,
            "threshold": args.threshold,
            "only_translated": args.only_translated,
            "skip_fuzzy": args.skip_fuzzy,
            "normalize_text": args.normalize_text,
            "lowercase": args.lowercase,
            "pairs": len(sims),
        },
        "summary": {
            "num_common_pairs": len(sims),
            "avg_similarity": round(avg, 4),
            "median_similarity": round(med, 4) if sims else None,
            "p90_similarity": round(p90, 4) if p90 is not None else None,
            "pct_over_threshold": round(ratio, 2),
        },
    }
    pout.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {pout}")
    if sims:
        print(f"Pairs={len(sims)} | Avg={avg:.4f} | Med={med:.4f} | ≥{args.threshold} = {ratio:.2f}%")
    else:
        print("No comparable pairs found.")

    # --- CSV update: ONLY last row
    csv_path = Path(args.experiments_csv)
    if csv_path.exists():
        with csv_path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            fields = reader.fieldnames or []

        # Ensure columns exist
        need_cols = ["Avg_sim", "Med_sim", "sim_over_0.8(≥0.8)"]
        for c in need_cols:
            if c not in fields:
                fields.append(c)

        if rows:
            last = rows[-1]
            last["Avg_sim"] = f"{avg:.4f}"
            last["Med_sim"] = f"{med:.4f}"
            last["sim_over_0.8(≥0.8)"] = f"{ratio:.2f}"
            rows[-1] = last
        else:
            print(f"[WARN] {csv_path} is empty. Nothing to update.", file=sys.stderr)

        # Write back with quoting to protect paths containing ':' etc.
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(rows)
        print(f"[quality] Updated only the last row in: {csv_path}")
    else:
        print(f"[quality] experiments.csv not found, skip update: {csv_path}")


if __name__ == "__main__":
    main()
