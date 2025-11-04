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

python translate.py \
  --model $MODEL \
  --workers 4 \
  --start 0 --end 200 \
  --pot_dir ./pot \
  --po_dir ./po \
  --glossary_dir ./glossary \
  --example_dir ./example \
  --pot_url "https://tarballs.opendev.org/openstack/translation-source/swift/master/releasenotes/source/locale/releasenotes.pot" \
  --target_pot_file "sample.pot" \
  --glossary_url "https://opendev.org/openstack/i18n/raw/commit/129b9de7be12740615d532591792b31566d0972f/glossary/locale/{lang}/LC_MESSAGES/glossary.po" \
  --glossary_po_file "glossary.po" \
  --glossary_json_file "glossary.json" \
  --example_url "https://opendev.org/openstack/nova/raw/branch/master/nova/locale/{lang}/LC_MESSAGES/nova.po" \
  --example_file "example.po" \
  --languages "ko_KR,ru,ja,zh_CN"