# AI-based Translation System for OpenStack

This system is an open-source AI translation system developed for OpenStack, which supports multilingual translation using flexible LLMs, few-shot learning, and batch optimization.
<br> This is part of OpenStack i18n(internationalization). If you want to know it in detail, please refer [i18n guide](https://docs.openstack.org/i18n/latest/index.html)

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
# if you trouble in upgrading pip, we recommend to use venv
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

## 3. Select Your Option for User

Our code default option is as below.
    - LLM: Lamma3.2 (3B)
    - Language: Korean, Japanese
    - Target file: To be written...

### 3-1 Choose Model
1. Open-Src LLM
We use Ollama as LLM framework <br>
Please find your preferred LLM name in [this link](https://ollama.com/library).

2. Closed-Src LLM
You can use OpenAI, Claude, Gemini model in this code.<br>
You should give '--llm_mode' as an additional argument to change llm backend.<br>
    - default="ollama"<br>
    - choices=["ollama", "gpt", "claude", "gemini"]<br>

```bash
# Example
tox -e i18n -- "gpt-4o" "ko_KR" "gpt"
# or you can use
bash main.sh "gpt-4o" "ko_KR" "gpt"
```

To speed up translation, you can increase the --workers value(default: 1) in main.sh, which controls how many batches are processed in parallel.

### 3-2. Choose Languages
Please find your target Language code in below.
We support 54 languages.

```python
LANG_MAP = {
    # language code: language description
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

### 3-3 Chosse Target File

To be written...

### 3-4 Apply them

```bash
# Example
tox -e i18n -- "llama3.2:3b" "de,ru"
# or you can use
bash main.sh "llama3.2:3b" "de,ru"
```

You can tune these arguments for performance / partial translation:<br>
```bash
   --workers   : number of parallel threads (default: 1)
   --start/end : entry index range to translate (default: 0 ~ all)
   --batch-size: entries per LLM call (default: 5)
```
You can edit more options in detail in [main.sh](./main.sh)
## 5. How to Improve Performance?

You can adjust (b) Few Shot Example and Language (c) Specific Prompt.
Please refer [CONTRIBUTING.md](./CONTRIBUTING.md)

## 6. Code Quality Check
We use [tox](https://tox.wiki) to ensure code consistency and quality.
1. PEP8 Style Check 
```bash
tox -e pep8
```

2. Fix Style Errors with autopep8
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
	- We used the POT source files and four language-specific PO translation files from the openstack/openstack-i18n repository.<br>
	Each PO file consists of msgid–msgstr pairs. The baseline human translation (msgstr) was compared against the AI-generated draft translation to evaluate quality.<br>

### Evaluation Metric

We extracted sentence embeddings using the Mean Pooling method from the Sentence Transformers library, and computed cosine similarity (range: 0–1) based on vector dot products to quantitatively assess translation quality.

Similarity thresholds are defined as follows:
	- ≥ 0.8: semantically similar
	- ≥ 0.9: semantically almost identical

Using these criteria, we objectively compared and analyzed the quality of AI translations.

### Result

(a) Batch Method, (b) Few-Shot Example

* The >=0.8 column represents the percentage of msgid entries whose similarity score is 0.8 or higher, indicating how many sentences the model translated with strong semantic accuracy.

| Korean | Avg | Median |≥0.8|time|
| --- | --- | --- | --- | --- |
|without a, b|	0.6806|	0.7523|	42.80%|	1250.69s|
|with a, b| 	0.8425|	0.8998|	76.00%|	742.78s|	
				
| Japanese | Avg | Median |≥0.8|time|
| --- | --- | --- | --- | --- |
|without a, b|	0.6876|	0.7402|	40.88%|	751.5s|
|with a, b|	0.8419|	0.8897|	69.38%|	744.13s|
			
				
| Chinese(China) | Avg | Median |≥0.8|time|
| --- | --- | --- | --- | --- |
|without a, b|	0.7596|	0.8463|	54.71%|	928.96s|
|with a, b|	0.8930|	0.9346|	85.94%|	927.74s|

| Russian | Avg | Median |≥0.8|time|
| --- | --- | --- | --- | --- |
|without a, b|	0.8442|	0.9203|	72.81%|	1432.77s|
|with a, b|	0.9020|	0.9625|	82.71%|	1647.99s|			

For Korean, translation quality improved by 0.1619, and across four languages, the average improvement was 0.1268.

### Reproducibility

1. Checkout to branch: testA or testB:
```bash
git checkout TestA
```
testA: pipeline with a, b
testB: pipeline without a, b

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
