#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PO translator using a local LLM (Ollama) with glossary support.

Features
- Reads a .po file and writes translations back (in-place safe with backup)
- Only translate untranslated entries with --only-untranslated
- Preserves placeholders like {name}, %(var)s, {0}, %s, {link}`text`
- Handles plurals
- Parallel requests via multiprocessing
- Glossary guidance + hard post-replacements
- Works with Ollama HTTP API (http://localhost:11434)

Requirements
  pip install polib requests tqdm regex

Example
  python scripts/po_translate_local_llama.py \
    --src-lang en --tgt ko \
    --in po/ko_KR/releasenotes.po --out po/ko_KR/releasenotes.po \
    --workers 12 \
    --model llama3.2:3b-instruct-q4_K_M \
    --glossary glossary/glossary.json \
    --only-untranslated --verbose
"""

import argparse
import json
import os
import shutil
import time
from typing import Dict, List, Tuple

import polib
import requests
import regex as re
from multiprocessing import Pool, cpu_count
from tqdm import tqdm

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_ENDPOINT = f"{OLLAMA_HOST}/api/generate"

# Regex patterns to preserve tokens that must not be altered
PLACEHOLDER_PATTERNS = [
    r"%\([a-zA-Z0-9_]+\)s",  # Python named placeholders e.g., %(name)s
    r"%s", r"%d", r"%f",  # printf style
    r"\{[a-zA-Z0-9_]+\}",  # {name}
    r"\{\d+\}",  # {0}
    r"\{[a-zA-Z0-9_]+:[^}]+\}",  # format spec {var:>10}
    r"`[^`]+`_?",  # reST references `link`_
    r"\*\*[^*]+\*\*",  # **bold**
    r"\*[^*]+\*",  # *italic*
    r"``[^`]+``",  # ``code``
]
PLACEHOLDER_RE = re.compile("|".join(f"({p})" for p in PLACEHOLDER_PATTERNS))


def mask_placeholders(text: str) -> Tuple[str, List[str]]:
    """Replace placeholders with <PH_i> tokens and return masks for restoration."""
    masks = []
    def _sub(m):
        idx = len(masks)
        masks.append(m.group(0))
        return f"<PH_{idx}>"
    masked = PLACEHOLDER_RE.sub(_sub, text)
    return masked, masks


def unmask_placeholders(text: str, masks: List[str]) -> str:
    for i, val in enumerate(masks):
        text = text.replace(f"<PH_{i}>", val)
    return text


def load_glossary(path: str) -> Dict[str, str]:
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Normalize keys for exact match usage
    return {k.strip(): v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)}


def apply_hard_glossary(text: str, glossary: Dict[str, str]) -> str:
    # Replace full-word matches first, then substring fallback
    for k, v in sorted(glossary.items(), key=lambda kv: -len(kv[0])):
        # Word-boundary if purely word chars; otherwise simple replace
        if re.match(r"^[\w\- ]+$", k):
            text = re.sub(rf"(?<!\w){re.escape(k)}(?!\w)", v, text)
        else:
            text = text.replace(k, v)
    return text


SYSTEM_PROMPT_TMPL = (
    """
You are a professional technical translator for OpenStack release notes.
Translate from {src_lang} to {tgt_lang}.
STRICT RULES:
- Preserve placeholders and markup exactly (tokens like %s, %(name)s, {{var}}, {{0}}, ``code``, **bold**, *italic*, and reST references like `link`_).
- Do NOT add or remove sentences.
- Maintain punctuation, lists, and headings structure.
- Use glossary terms exactly when present.
- Tone: concise, formal technical Korean.
- If the source looks like a title or heading, translate naturally but keep capitalization minimal.
- If the text is already in the target language, return it unchanged.
Output ONLY the translated text with no explanations.
    """
)


def ollama_generate(model: str, prompt: str, system: str, retries: int = 3, timeout: int = 120) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "top_p": 0.9,
        },
    }
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            r = requests.post(OLLAMA_ENDPOINT, json=payload, timeout=timeout)
            r.raise_for_status()
            data = r.json()
            return data.get("response", "").strip()
        except Exception as e:
            last_err = e
            time.sleep(min(2**attempt, 6))
    raise RuntimeError(f"Ollama request failed after {retries} attempts: {last_err}")


def build_user_prompt(src_text: str, glossary: Dict[str, str]) -> str:
    glos_lines = [f"- {k} => {v}" for k, v in list(glossary.items())[:200]]  # avoid overly long
    glos_block = "\n".join(glos_lines)
    return (
        f"GLOSSARY (apply exactly when encountered):\n{glos_block}\n\n"
        f"SOURCE:\n{src_text}\n"
    )


def translate_unit(args_tuple) -> Tuple[int, str, Dict[int, str]]:
    """Translate one entry (singular or plural). Returns (index, translated, plurals_map)."""
    (idx, src_text, plural_src_map, model, system_prompt, glossary) = args_tuple

    if plural_src_map:  # plural
        out_map: Dict[int, str] = {}
        for n, srcn in plural_src_map.items():
            masked, masks = mask_placeholders(srcn)
            user_prompt = build_user_prompt(masked, glossary)
            resp = ollama_generate(model=model, prompt=user_prompt, system=system_prompt)
            resp = unmask_placeholders(resp, masks)
            resp = apply_hard_glossary(resp, glossary)
            out_map[n] = resp
        return idx, "", out_map
    else:
        masked, masks = mask_placeholders(src_text)
        user_prompt = build_user_prompt(masked, glossary)
        resp = ollama_generate(model=model, prompt=user_prompt, system=system_prompt)
        resp = unmask_placeholders(resp, masks)
        resp = apply_hard_glossary(resp, glossary)
        return idx, resp, {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src-lang", required=True)
    ap.add_argument("--tgt", required=True)
    ap.add_argument("--in", dest="infile", required=True)
    ap.add_argument("--out", dest="outfile", required=True)
    ap.add_argument("--model", default="llama3.2:3b-instruct-q4_K_M")
    ap.add_argument("--glossary", default=None)
    ap.add_argument("--workers", type=int, default=max(1, cpu_count() // 2))
    ap.add_argument("--only-untranslated", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    glossary = load_glossary(args.glossary)

    po = polib.pofile(args.infile)

    # backup
    if os.path.abspath(args.infile) == os.path.abspath(args.outfile):
        backup_path = args.outfile + ".bak"
        shutil.copyfile(args.infile, backup_path)
        if args.verbose:
            print(f"Backup written: {backup_path}")

    # Prepare work items
    work: List[Tuple[int, str, Dict[int, str], str, str, Dict[str, str]]] = []
    system_prompt = SYSTEM_PROMPT_TMPL.format(src_lang=args.src_lang, tgt_lang=args.tgt)

    for idx, e in enumerate(po):
        # Skip if not needed
        if args.only_untranslated:
            if e.obsolete:
                continue
            if e.translated():
                continue
        # singular vs plural
        if e.msgid_plural:
            plural_src_map = {}
            # nplurals are stored in msgstr_plural as {index: text}
            plural_src_map[0] = e.msgid
            plural_src_map[1] = e.msgid_plural
            work.append((idx, "", plural_src_map, args.model, system_prompt, glossary))
        else:
            work.append((idx, e.msgid, {}, args.model, system_prompt, glossary))

    if args.verbose:
        print(f"Total entries: {len(po)} | To translate: {len(work)} | workers={args.workers}")

    results: Dict[int, Tuple[str, Dict[int, str]]] = {}
    if work:
        with Pool(processes=args.workers) as pool:
            for idx, out_text, out_plural in tqdm(pool.imap_unordered(translate_unit, work), total=len(work)):
                results[idx] = (out_text, out_plural)

        # Write back
        for idx, (out_text, out_plural) in results.items():
            e = po[idx]
            if out_plural:
                for n, txt in out_plural.items():
                    e.msgstr_plural[n] = txt
            else:
                e.msgstr = out_text
            e.flags = [f for f in e.flags if f != 'fuzzy']

    po.save(args.outfile)
    if args.verbose:
        print(f"Saved: {args.outfile}")


if __name__ == "__main__":
    main()
