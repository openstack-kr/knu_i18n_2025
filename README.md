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
# Choose LLM
MODEL=${1:-"llama3.2:3b"}

# Arguments we recommend to change
#  --pot_url "" \ (You can download target pot by URL)
#  --target_pot_file "" \ (If you download it manually, you
#  --languages "ko_KR, ja, ru" (Please set the languages code you want)
```

## 5. How to Improve Performance?

You can adjust (b) Few Shot Example and Language (c) Specific Promopt.
Please refer [CONTRIBUTING.md](./CONTRIBUTING.md)

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

To validate how our pipeline works well, we did ablation study. <br>
In this pipeline, we applied 3 methods, (a) Batch-Method, (b) Few-Shot Example, (c) Language Specific Prompt. <br>
In this study, we test how (a) and (b) powerful. <br>

### Environment

- OS: Ubuntu 22.04
- Hardware: 8-core CPU, 16GB memory
- Python: 3.10
- Full Dependencies: Check [requirements.txt](https://github.com/openstack-kr/knu_i18n_2025/blob/main/requirements.txt)
- LLM Framework: ollama (Python package, v0.6.0)
- LLM: Llama 3.2 (3B)
- target file: https://opendev.org/openstack/i18n/src/branch/master/doc/source/locale

### Evalution Metric

We measured the similarity between the AI-generated preliminary translation (.po) and the human-translated .po for each target file.<br>
Similarity was computed using the mean-pooling method of the SentenceTransformer library.<br>

### Result

| Korean | Avg | Median |≥0.8|time|
| --- | --- | --- | --- | --- |
|without a, b(%)|	68.06|	75.23|	42.80|	1250.69s|
|with a, b(%)| 	84.25|	89.98|	76.00|	742.78s|	
				
| Japanese | Avg | Median |≥0.8|time|
| --- | --- | --- | --- | --- |
|without a, b(%)|	68.76|	74.02|	40.88|	751.5s|
|with a, b(%)|	84.19|	88.97|	69.38|	744.13s|
			
				
| Chinese(China) | Avg | Median |≥0.8|time|
| --- | --- | --- | --- | --- |
|without a, b(%)|	75.96|	84.63|	54.71|	928.96s|
|with a, b(%)|	89.30|	93.46|	85.94|	927.74s|

| Russian | Avg | Median |≥0.8|time|
| --- | --- | --- | --- | --- |
|without a, b(%)|	844.2|	92.03|	72.81|	1432.77s|
|with a, b(%)|	90.20|	96.25|	82.71|	1647.99s|			

For Korean, translation quality improved by 16.19%, and across four languages, the average improvement was 12.68%.

### Reproducibility

1. Chekout to branch: testA or testB:
```bash
git checkout TestA
```
testA: pipeline before a, b
testB: pipeline after a, b

2-1. Use the provided tox environment for isolated setup and execution:
```bash
tox -e i18n -vv
```
2-2. (Optional) Running the Prototype
- Execute the translation system via main.sh:
```bash
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
