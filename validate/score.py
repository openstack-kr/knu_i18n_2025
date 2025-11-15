# -*- coding: utf-8 -*-
"""
Compare two PO files semantically using SimCSE.
- Match entries by key: (msgctxt, msgid, plural_index)
- Embed msgstr pairs with a SimCSE model
- Compute cosine similarity, summary stats, and top-K examples
- Save a JSON report.

Usage:
  python po_simcse_compare.py --a A.po --b B.po --out result.json
Options:
  --model MODEL_NAME        (default: princeton-nlp/sup-simcse-roberta-base)
  --batch-size N            (default: 64)
  --threshold 0.80          (report %≥threshold)
  --only-translated         (skip empty msgstr)
  --skip-fuzzy              (skip entries with 'fuzzy' flag)
  --normalize-text          (strip + collapse spaces before embedding)
  --lowercase               (lowercase before embedding)
  --topk 20                 (how many best/worst pairs to store in JSON)
"""

from datetime import datetime, timedelta
import argparse
import json
import re
import sys
import io
import statistics
import csv
from datetime import datetime
from pathlib import Path

import polib
import torch
from sentence_transformers import SentenceTransformer, util
from babel.messages.pofile import read_po as babel_read_po

timestamp = (datetime.now() + timedelta(hours=9)).strftime("%Y%m%d_%H%M")

def normalize_text(s: str, do_norm=False, do_lower=False) -> str:
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
      where plural_index is int or 0 for singular
    Try polib first; on failure, fallback to babel.
    """
    def _from_polib(po):
        m = {}
        for e in po:
            if e.obsolete:
                continue
            # skip header
            if e.msgid == "" and not e.msgid_plural:
                continue
            if skip_fuzzy and "fuzzy" in (e.flags or []):
                continue

            if e.msgid_plural:
                if e.msgstr_plural:
                    for idx, s in sorted(
                        e.msgstr_plural.items(), key=lambda kv: int(
                            kv[0])):
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
                strings = msg.string if isinstance(
                    msg.string, tuple) else (msg.string,)
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


def batched(iterable, n):
    for i in range(0, len(iterable), n):
        yield iterable[i:i + n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="princeton-nlp/sup-simcse-roberta-base")
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--threshold", type=float, default=0.80)
    ap.add_argument("--only-translated", action="store_true")
    ap.add_argument("--skip-fuzzy", action="store_true")
    ap.add_argument("--normalize-text", action="store_true")
    ap.add_argument("--lowercase", action="store_true")
    ap.add_argument("--topk", type=int, default=100)
    ap.add_argument("--experiments_csv", default=str(Path(__file__).
    resolve().parent.parent / "experiments.csv"))
    args = ap.parse_args()

    pa, pb, pout = Path(args.a), Path(args.b), Path(args.out)
    if not pa.exists() or not pb.exists():
        missing = pa if not pa.exists() else pb
        print(f"[ERROR] file not found: {missing}", file=sys.stderr)
        sys.exit(1)

    # 1) Load entries
    A = load_po_entries(pa, args.only_translated, args.skip_fuzzy,
                        args.normalize_text, args.lowercase)
    B = load_po_entries(pb, args.only_translated, args.skip_fuzzy,
                        args.normalize_text, args.lowercase)

    common_keys = sorted(set(A.keys()) & set(B.keys()))
    if not common_keys:
        print("[WARN] No overlapping msgid keys to compare.", file=sys.stderr)

    # 2) Build pairs
    pairs = [(k, A[k], B[k]) for k in common_keys]

    # 3) Load model
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SentenceTransformer(args.model, device=device)

    # 4) Encode & cosine similarity
    sims = []

    def encode_texts(texts):
        return model.encode(
            texts,
            convert_to_tensor=True,
            normalize_embeddings=True)

    # batched to save memory
    for batch in batched(pairs, args.batch_size):
        a_texts = [p[1] for p in batch]
        b_texts = [p[2] for p in batch]
        emb_a = encode_texts(a_texts)
        emb_b = encode_texts(b_texts)
        cos = util.cos_sim(emb_a, emb_b).diag().tolist()
        sims.extend(cos)

    # 5) Stats
    if sims:
        avg = float(sum(sims) / len(sims))
        med = float(statistics.median(sims))
        p90 = float(statistics.quantiles(sims, n=10)
                    [-1]) if len(sims) >= 10 else None
        above = sum(1 for s in sims if s >= args.threshold)
        ratio = above / len(sims) * 100.0
    else:
        avg = med = p90 = ratio = 0.0

    # 6) Top-K examples
    # attach info for sorting
    detailed = []
    for (k, sA, sB), sc in zip(pairs, sims):
        ctx, msgid, idx = k
        detailed.append({
            "similarity": float(sc),
            "context": ctx,
            "msgid": msgid,
            "plural_index": idx,
            "a_msgstr": sA,
            "b_msgstr": sB
        })
    topk = sorted(
        detailed,
        key=lambda x: x["similarity"],
        reverse=True)[
        :args.topk]
    worstk = sorted(detailed, key=lambda x: x["similarity"])[:args.topk]

    # 7) Save JSON
    report = {
        "metadata": {
            "file_a": str(pa),
            "file_b": str(pb),
            "model": args.model,
            "batch_size": args.batch_size,
            "threshold": args.threshold,
            "only_translated": args.only_translated,
            "skip_fuzzy": args.skip_fuzzy,
            "normalize_text": args.normalize_text,
            "lowercase": args.lowercase,
            "device": device
        },
        "summary": {
            "num_common_pairs": len(sims),
            "avg_similarity": round(avg, 4),
            "median_similarity": round(med, 4) if sims else None,
            "p90_similarity": round(p90, 4) if p90 is not None else None,
            "pct_over_threshold": round(ratio, 2)
        },
        "top_k_most_similar": topk,
        "top_k_least_similar": worstk
    }
    out_dir = Path("validate/json")
    out_dir.mkdir(parents=True, exist_ok=True)

    # extract PO filename (ex: guide.po → guide)
    po_basename = pb.stem
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    pout = out_dir / f"{po_basename}_{timestamp}.json"

    # --- write json file ---
    pout.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(f"Saved: {pout}")
    if sims:
        print(
            f"Pairs={len(sims)} | "
            f"Avg={avg:.4f} | "
            f"Med={med:.4f} | "
            f"≥{args.threshold} = {ratio:.2f}%"
        )
    else:
        print("No comparable pairs found.")

    # 8) experiments.csv 업데이트
    csv_path = Path(args.experiments_csv)
    if csv_path.exists():
        target_po_abs = str(pb.resolve())
        target_po_name = pb.name

        with csv_path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            fields = reader.fieldnames or []

        # 칼럼
        need_cols = ["Avg_sim", "Med_sim", "sim_over_0.8(≥0.8)"]
        for c in need_cols:
            if c not in fields:
                fields.append(c)

        updated = False
        for r in rows:
            po_field = (r.get("po_file") or "").strip()
            if not po_field:
                continue
            try:
                same = (str(Path(po_field).resolve()) == target_po_abs) or (Path(po_field).name == target_po_name)
            except Exception:
                same = (Path(po_field).name == target_po_name)
            if same:
                r["Avg_sim"] = f"{avg:.4f}" if sims else "0.0000"
                r["Med_sim"] = f"{med:.4f}" if sims else "0.0000"
                r["sim_over_0.8(≥0.8)"] = f"{ratio:.2f}"
                updated = True

        if not updated:
            rows.append({
                "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M"),
                "model": args.model,
                "pot_file": "",
                "po_file": target_po_abs,
                "duration_sec": "",
                "git_commit": "",
                "git_branch": "",
                "Avg_sim": f"{avg:.4f}" if sims else "0.0000",
                "Med_sim": f"{med:.4f}" if sims else "0.0000",
                "sim_over_0.8(≥0.8)": f"{ratio:.2f}",
            })
            # 누락보정
            for k in ["timestamp", "model", "pot_file", "duration_sec", "git_commit", "git_branch"]:
                if k not in fields:
                    fields.append(k)

        with csv_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        print(f"[quality] experiments.csv updated: {csv_path}")
    else:
        print(f"[quality] experiments.csv not found, skip update: {csv_path}")


if __name__ == "__main__":
    main()
