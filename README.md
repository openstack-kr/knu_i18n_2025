# OpenStack i18n LLM Translator (Local CPU)

## Structure
## Usage
```bash
msginit --no-translator --input=pots/swift/doc-admin.pot \
  --locale=ko_KR --output-file=po/ko_KR/doc-admin.po

python scripts/po_translate_local_llama.py \
  --src-lang en --tgt ko \
  --in po/ko_KR/doc-admin.po --out po/ko_KR/doc-admin.po \
  --workers 12 \
  --model llama3.2:3b-instruct-q4_K_M \
  --glossary glossary/glossary.json
