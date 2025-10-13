#!/usr/bin/env python3
# scripts/translate_chunk.py
import json, sys, time, re, unicodedata
import requests

MODEL = "llama3.2:3b-instruct-q4_K_M"
URL   = "http://127.0.0.1:11434/api/generate"

# --- 안정성 옵션(재현성/성능) ---
CONNECT_TIMEOUT = 10
READ_TIMEOUT    = 300
RETRIES         = 3
BACKOFF_SEC     = 3

# 팀 공통: 항상 포함(언어별 msgstr로 맞춰둬도 됨)
ALWAYS = {
  "OpenStack":"OpenStack","Nova":"Nova","Swift":"Swift","Keystone":"Keystone",
  "Glance":"Glance","Horizon":"Horizon","Cinder":"Cinder","API":"API",
  "Instance":"인스턴스","Flavor":"플레이버","Availability Zone":"가용 영역"
}

def norm(s: str) -> str:
    return unicodedata.normalize("NFKC", s or "").strip()

# 간단 토큰화 + 소문자 포함검색 + 경계 정규식 보조
def contains_term(text_lc: str, term: str) -> bool:
    t = term.lower().strip()
    if not t: return False
    if t in text_lc:  # 빠른 경로
        return True
    # 단어 경계 매칭(영문/숫자 위주)
    pat = r'(?<!\w)' + re.escape(t) + r'(?!\w)'
    return re.search(pat, text_lc) is not None

def pick_terms(glossary: dict, text: str, max_terms: int = 30) -> dict:
    picked = dict(ALWAYS)  # ① 항상 포함
    low = norm(text).lower()
    # ② 실제 등장하는 용어만 선별
    for k, v in glossary.items():
        k_n = norm(k)
        if not k_n or k_n in ALWAYS:  # 이미 포함된 것은 skip
            continue
        if contains_term(low, k_n):
            picked[k_n] = norm(v)
            if len(picked) >= max_terms:
                break
    return picked

def call_ollama(payload: dict) -> str:
    for i in range(1, RETRIES + 1):
        try:
            r = requests.post(URL, json=payload,
                              timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
            r.raise_for_status()
            return r.json().get("response", "").strip()
        except Exception as e:
            if i == RETRIES:
                raise
            time.sleep(BACKOFF_SEC)

def translate_msgid(msgid: str, glossary: dict) -> str:
    slim = pick_terms(glossary, msgid, max_terms=30)
    system = (
        "You are a professional technical translator.\n"
        "Output ONLY the translation (no extra text).\n"
        "Preserve placeholders (%s, %(name)s, {name}, <tags>), punctuation, and line breaks.\n"
        "Use a consistent, professional, neutral tone.\n"
    )
    prompt = (
        f"{system}\n"
        f"Glossary (must respect; don't invent translations):\n"
        f"{json.dumps(slim, ensure_ascii=False)}\n\n"
        f"SOURCE:\n{msgid}\n"
    )
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "keep_alive": "30m",
        "options": {
            # 재현성(누가 돌려도 동일)
            "temperature": 0,
            "top_p": 1,
            "top_k": 0,
            "seed": 1234
        }
    }
    return call_ollama(payload)

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: translate_chunk.py chunk.json glossary.json out.json")
        sys.exit(1)

    entries   = json.load(open(sys.argv[1], encoding="utf-8"))
    glossary  = json.load(open(sys.argv[2], encoding="utf-8"))
    out_path  = sys.argv[3]

    out = []
    t0  = time.time()
    for e in entries:
        msgid = norm(e.get("msgid", ""))
        if not msgid:
            e["msgstr"] = ""
        else:
            try:
                e["msgstr"] = translate_msgid(msgid, glossary)
            except Exception as ex:
                e["msgstr"] = f"[ERROR:{ex}]"
        out.append(e)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"✅ Done {sys.argv[1]} -> {out_path} in {round(time.time()-t0,1)}s")
