# AI-based Translation System for OpenStack

This system is an open-source AI translation system developed for OpenStack, which supports multilingual translation using flexible LLMs, few-shot learning, and batch optimization.

## Overview

We have built a prototype translation system that runs on CPU environments and provides a foundation for OpenStack’s internationalization needs. It integrates few-shot learning and batch-size optimization to improve translation efficiency.

⚠️ The full automation pipeline will be added in the near future to enable workflow automation.

## Key Features

- **Open-source**: Fully built on open-source AI models
- **Multilingual Support**: Supports multilingual translation
- **Flexible LLM Usage**: Can experiment with and switch between different LLM models on CPU environments
- **Few-shot Learning**: Improves translation quality with minimal examples
- **Batch-size Optimization**: Enhances translation efficiency for large-scale datasets
- **Scalable Architecture**: Provides a foundation for future workflow automation and full pipeline integration

## How It Works
<img width="1655" height="808" alt="tox Build virtual environment (2)" src="https://github.com/user-attachments/assets/67961759-cfb4-4566-8320-36d15c0cbad0" />

The system uses the lightweight LLM framework **Ollama** and a **tox** virtual environment to perform initial AI-assisted translations.

Users can select the target language, LLM, and `.pot` files to be translated via `main.sh`.

1. During execution, `.pot` files that have not yet been translated in **Weblate** are downloaded from a specified URL.
2. For documents containing hundreds or thousands of lines, multiple sentences are divided into **(a) batches** and input into the LLM.
3. By default, a general prompt is applied, and if a **(c) language-specific prompt** exists for the target language, it is used instead.
4. When reference documents are available, a few examples are provided using the **(b) few-shot learning** method. The system also refers to the OpenStack **glossary** during translation.

Initial translation results are exported as `.po` files, uploaded to **Gerrit**, reviewed by human translators, and then merged into **Weblate**.

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

###  Environment

- OS: Ubuntu 22.04
- Hardware: 8-core CPU, 16GB memory
- Python: 3.10
- Full Dependencies: Check [requirements.txt](https://github.com/openstack-kr/knu_i18n_2025/blob/main/requirements.txt)
- LLM Framework: ollama (Python package, v0.6.0)
- LLM: Llama 3.2 (3B)

### Setup & Installation

1. Clone the repository:
```bash
git clone https://github.com/openstack-kr/knu_i18n_2025.git
cd knu_i18n_2025
```
2. Upgrade pip and install dependencies:
```
python -m pip install --upgrade pip
pip install -r requirements.txt
```
3. Install Ollama:
```
curl -fsSL https://ollama.com/install.sh | sh
```
4. (Optional) Use the provided tox environment for isolated setup and execution:
```
tox -e i18n -vv
```
5. Running the Prototype
- Execute the translation system via main.sh:
```
bash main.sh
```

📝 **Notes**

- All URLs for .pot, glossary, and example files are specified in main.sh for reproducibility.

## Team

- [Lee Juyeong](https://github.com/ale8ander)
- [Oh Jiwoo](https://github.com/5hjiwoo)
- [Jo Taeho](https://github.com/o-heat)
- [Chun Sihyeon](https://github.com/sihyeon22)
- [Hwang Jiyoung](https://github.com/imjyong)
