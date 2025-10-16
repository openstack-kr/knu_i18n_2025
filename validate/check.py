import os, re, sys, json
from babel.messages.pofile import read_po
from langdetect import detect, DetectorFactory, LangDetectException
from io import open

DetectorFactory.seed = 0

MIN_HANGUL_RATIO = 0.4
GLOSSARY_PATH = "../glossary/glossary_ko.json"
BAD_OUTPUT = "bad_translations.txt"

TN_PATTERNS = [
    r'^\s*[\*\-\:\{\}\[\]\(\)\.`]+$',
    r'^\s*[\d\.\-]+$',
    r'^\s*`[^`]+`$',
    r'^\s*::\s*$',
    r'^\s*\.\.\s+\w+::',
    r'(?i)\b(/etc/|/usr/|/var/|\.conf|\.ini|\.yaml)\b',
    r'(?i)\bhttps?://[^\s]+',
]

def load_po(path):
    with open(path, 'r', encoding='utf-8') as f:
        catalog = read_po(f)
    return catalog

def load_glossary(path):
    if not os.path.exists(path):
        print(f"glossary not found: {path}")
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def hangul_ratio(text):
    total = sum(1 for ch in text if ch.isalpha() or '\uAC00' <= ch <= '\uD7A3')
    ko = sum(1 for ch in text if '\uAC00' <= ch <= '\uD7A3')
    return ko / total if total else 0.0

def is_korean(text):
    text = (text or "").strip()
    if not text:
        return False
    try:
        return detect(text) == "ko" or hangul_ratio(text) >= MIN_HANGUL_RATIO
    except LangDetectException:
        return hangul_ratio(text) >= MIN_HANGUL_RATIO

def is_tn(msgid):
    for pat in TN_PATTERNS:
        if re.search(pat, msgid):
            return True
    return False

def check_glossary(entry, glossary):
    missed = []
    for en, ko in glossary.items():
        if en.lower() in entry.id.lower() and ko not in entry.string:
            missed.append((en, ko))
    return missed

def check_end_mismatch(text):
    end = text.strip()[-3:]
    return not bool(re.search(r'(니다|합니다|됩니다|습니다|십시오)[\.\!]?$', end))

def classify(entry, glossary):
    msgid = entry.id.strip() if entry.id else ""
    msgstr = entry.string.strip() if entry.string else ""

    if not msgid:
        return "TN"
    if is_tn(msgid):
        return "TN"
    if not msgstr:
        return "FN"
    if not is_korean(msgstr):
        return "FN"

    gloss_miss = check_glossary(entry, glossary)
    if gloss_miss:
        return "FP"
    en_count = len(re.findall(r"[A-Za-z]{2,}", msgstr))
    if en_count > 8:
        return "FP"
    if check_end_mismatch(msgstr):
        return "FP"

    return "TP"

def metrics(tp, fp, fn, tn):
    total = tp + fp + fn + tn
    acc = (tp + tn) / total * 100 if total else 0
    return acc

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 check_babel.py path/to/file.po")
        sys.exit(1)

    po_path = sys.argv[1]
    glossary = load_glossary(GLOSSARY_PATH)

    try:
        po = load_po(po_path)
    except Exception as e:
        print(f"Error loading {po_path}: {e}")
        sys.exit(1)

    TP = FP = FN = TN = 0
    FP_ENTRIES = []

    for e in po:
        c = classify(e, glossary)
        if c == "TP": TP += 1
        elif c == "FP":
            FP += 1
            FP_ENTRIES.append((e.id, e.string))
        elif c == "FN": FN += 1
        elif c == "TN": TN += 1

    acc = metrics(TP, FP, FN, TN)

    print("\n--- Translation Quality Summary ---")
    print(f"True Positive (정확한 번역): {TP}")
    print(f"False Positive (잘못된 번역): {FP}")
    print(f"False Negative (누락/영문 유지): {FN}")
    print(f"True Negative (번역 불필요 영역): {TN}")
    print("------------------------------------")
    print(f"Accuracy (정확도): {acc:.2f}%")
    print("------------------------------------")

    # 잘못된 번역 저장
    if FP_ENTRIES:
        with open(BAD_OUTPUT, "w", encoding="utf-8") as f:
            for mid, msg in FP_ENTRIES:
                f.write(f"[EN] {mid}\n[KO] {msg}\n\n")
        print(f"\n잘못된 번역 {len(FP_ENTRIES)}개를 '{BAD_OUTPUT}' 파일로 저장했습니다.")
    else:
        print("\n잘못된 번역이 없습니다.")

if __name__ == "__main__":
    main()
