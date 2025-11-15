# knu_i18n_2025

## Overview

## Key Features

## How It Works
<img width="1655" height="808" alt="tox Build virtual environment (2)" src="https://github.com/user-attachments/assets/67961759-cfb4-4566-8320-36d15c0cbad0" />

We will add Automation Pipeline Soon!

## Getting Started
### 1. Clone The Repository & Install Tox
```bash
# Option A) SSH (recommended)
git clone git@github.com:openstack-kr/knu_i18n_2025.git
# Option B) HTTPS 
git clone https://github.com/openstack-kr/knu_i18n_2025.git
```
```bash
cd knu_i18n_2025
# if you troule in upgrading pip, we recommend to use venv
python -m pip install --upgrade pip
pip install tox
curl -fsSL https://ollama.com/install.sh | sh
```
### 2-1. Use tox environment
For convenience, we provide a tox environment that automatically sets up dependencies and runs the workflow in an isolated environment.
```bash
tox -e i18n -vv
```

### 2-2. or Run Locally
```bash
pip install -r requirements.txt
```

```bash
bash main.sh
```

## 3. Edit main.sh

Please find your target Languages in below.
```python
LANG_MAP = {
    "vi_VN": "Vietnamese (Vietnam)",
    "ur": "Urdu",
    "tr_TR": "Turkish (Turkey)",
    "Th": "Thai",
    "te_IN": "Telugu (India)",
    "ta": "Tamil",
    "es_MX": "Spanish (Mexico)",
    "es": "Spanish",
    "sl_SI": "Slovenian (Slovenia)",
    "sr": "Serbian",
    "ru": "Russian",
    "Ro": "Romanian",
    "pa_IN": "Punjabi (India)",
    "pt_BR": "Portuguese (Brazil)",
    "pt": "Portuguese",
    "pl_PL": "Polish (Poland)",
    "fa": "Persian",
    "ne": "Nepali",
    "mr": "Marathi",
    "mni": "Manipuri",
    "mai": "Maithili",
    "lo": "Lao",
    "ko_KR": "Korean (South Korea)",
    "kok": "Konkani",
    "ks": "Kashmiri",
    "kn": "Kannada",
    "ja": "Japanese",
    "it": "Italian",
    "id": "Indonesian",
    "hu": "Hungarian",
    "hi": "Hindi",
    "he": "Hebrew",
    "gu": "Gujarati",
    "el": "Greek",
    "de": "German",
    "ka_GE": "Georgian (Georgia)",
    "fr": "French",
    "fi_FI": "Finnish (Finland)",
    "fil": "Filipino",
    "eo": "Esperanto",
    "en_US": "English (United States)",
    "en_GB": "English (United Kingdom)",
    "en_AU": "English (Australia)",
    "nl_NL": "Dutch (Netherlands)",
    "cs": "Czech",
    "zh_TW": "Chinese (Taiwan)",
    "zh_CN": "Chinese (China)",
    "ca": "Catalan",
    "bg_BG": "Bulgarian (Bulgaria)",
    "brx": "Bodo",
    "bn_IN": "Bengali (India)",
    "as": "Assamese",
    "ar": "Arabic",
    "sq": "Albanian",
}
```

```bash
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
  --example_dir ./po-example \
  --pot_url "https://tarballs.opendev.org/openstack/translation-source/swift/master/releasenotes/source/locale/releasenotes.pot" \
  --target_pot_file "i18n-docs-source-locale.pot" \
  --glossary_url "https://opendev.org/openstack/i18n/raw/commit/129b9de7be12740615d532591792b31566d0972f/glossary/locale/{lang}/LC_MESSAGES/glossary.po" \
  --glossary_po_file "glossary.po" \
  --glossary_json_file "glossary.json" \
  --example_url "https://opendev.org/openstack/nova/raw/branch/master/nova/locale/{lang}/LC_MESSAGES/nova.po" \
  --example_file "nova-nova-locale.po" \
  --fixed_example_json "fixed_examples.json" \
  --batch-size "5" \
  --languages "ko_KR"
```

## 5. How to Improve Performance?

You can adjust Few Shot Example and Language Specific Promopt.
Please refer CONTRIBUTING.md

## 6. Code Quality Check
We use [tox](https://tox.wiki) to ensure code consistency and quality.
1. PEP8 Style Check 
```bash
tox -e pep8
```

2. Ansible Playbook Check
```bash
tox -e ansible
```

3. Fix Style Errors with autopep8
You can correct fix all style issues in the repository by running the command below:
```bash
autopep8 --in-place --aggressive --aggressive -r .
```
This will recursively format all Python files in the current directory according to the PEP8 style guide.
However, few errors can not be fixed with this command and you have to fix them manually.


## 7. Paper-Experiments Reproducibility

## Team

## Getting in Touch
