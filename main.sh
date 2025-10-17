#!/bin/bash
set -e

python translate_ollama.py \
  --model llama3.2:3b \
  --workers 4 \
  --start 0 --end 200 \
  --pot_dir ./pot \
  --po_dir ./po \
  --glossary_dir ./glossary \
  --pot_url "https://tarballs.opendev.org/openstack/translation-source/swift/master/releasenotes/source/locale/releasenotes.pot" \
  --target_pot_file "sample.pot" \
  --glossary_url "https://opendev.org/openstack/i18n/raw/commit/129b9de7be12740615d532591792b31566d0972f/glossary/locale/ko_KR/LC_MESSAGES/glossary.po" \
  --glossary_po_file "glossary_ko.po" \
  --glossary_json_file "glossary_ko.json"