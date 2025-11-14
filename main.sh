#!/bin/bash
set -e

MODEL=${1:-"llama3.2:3b"}

# 1) make sure the model is available in local ollama
if command -v ollama >/dev/null 2>&1; then
  echo "[main.sh] pulling model: $MODEL ..."
  # if the model already exists, this is a quick no-op
  ollama pull $MODEL || echo "[main.sh] warning: could not pull model (ollama daemon running?)"
else
  echo "[main.sh] warning: ollama is not installed or not in PATH. skipping model pull."
fi

declare -A POT_MAP
POT_MAP["ko_KR"]="i18n-docs-source-locale-ko_KR.pot"
POT_MAP["ru"]="i18n-docs-source-locale-ru.pot"
POT_MAP["ja"]="i18n-docs-source-locale-ja.pot"
POT_MAP["zh_CN"]="i18n-docs-source-locale-zh_CN.pot"

for lang in "${!POT_MAP[@]}"; do

  pot_file="${POT_MAP[$lang]}"

  python translate.py \
    --model $MODEL \
    --workers 4 \
    --start 0 --end 200 \
    --pot_dir ./pot \
    --po_dir ./po \
    --glossary_dir ./glossary \
    --pot_url "https://tarballs.opendev.org/openstack/translation-source/swift/master/releasenotes/source/locale/releasenotes.pot" \
    --target_pot_file "$pot_file" \
    --glossary_url "https://opendev.org/openstack/i18n/raw/commit/129b9de7be12740615d532591792b31566d0972f/glossary/locale/{lang}/LC_MESSAGES/glossary.po" \
    --glossary_po_file "glossary.po" \
    --glossary_json_file "glossary.json" \
    --languages "$lang"
done
