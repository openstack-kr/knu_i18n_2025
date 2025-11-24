# AI-based Translation System for OpenStack

A lightweight, user-friendly AI translation system for OpenStack i18n.
This tool helps contributors translate `.pot` / `.po` files into 54 languages using CPU-friendly LLMs such as **Ollama**, as well as GPT, Claude, and Gemini.

If you're new to OpenStack i18n, see the official [OpenStack i18n guide](https://docs.openstack.org/i18n/latest/index.html).

# Quick Start (5 steps)

The fastest way to run your first translation.<br>

## **Step 1 — Clone the repository**

```bash
git clone https://github.com/openstack-kr/knu_i18n_2025.git
cd knu_i18n_2025
```

## **Step 2 — Install dependencies**

### Option A) Use tox (recommended)

```bash
python -m pip install --upgrade pip
pip install tox
curl -fsSL https://ollama.com/install.sh | sh

# prepare environment
tox -e i18n -vv
```

### Option B) Run locally

```bash
python -m pip install --upgrade pip
curl -fsSL https://ollama.com/install.sh | sh

pip install -r requirements.txt
bash loca.sh
```

## **Step 3 — Run translation**

```bash
tox -e i18n --vv
# or
bash local.sh
```

And that's it! Your translated .po file(in ./po/) is ready.

## **Step 4 — Human Review**

To be written

## **Step 5  — Merge your translation to origin po**

```bash
python merge_po.py --config config.yaml
```

After reviewing AI translation, you can merge translation to origin .po.

# Choose Your Options

You can customize **target file**, **model**, **language**, and **performance settings** in [config.yaml](./config.yaml)
## **1. Choose Target File**

you can manually download the latest translated POT or PO files directly from the Weblate interface.

Steps
1. Go to the Weblate translation dashboard for the project [Example](https://openstack.weblate.cloud/projects/horizon/)
2. Select the project (e.g., Nova, horizon, etx.)
3. Navigate to 
```bash
project-> languages-> <Your Language>
```
4. Click Download translation
5. The target file for the selected languages will be downloaded
6. The target file must be placed under the data/target firectory

```bash
files:
  ...
  # Please add path your origin_po(download from weblate)
  origin_po: "./data/target/{project}/{lang}/LC_MESSAGES/{project}.po
```

## **2. Choose Your Language**

Please insert your language code in [this link](docs/language_support.md).
We support **54 languages**

```bash
languages:
# Add your language.
  - "ko_KR"
  - "ja"
```

## **3. Choose Your Model**
### **Open-source models (default)**

Uses **Ollama**. Browse available models [HERE](https://ollama.com/library).

### **Closed-source models (GPT / Claude / Gemini)**

When you use closed-source model, please edit the backend using `llm.mode`: [`ollama` (default), `gpt`, `claude`, `gemini`]

```bash
# You can tune these arguments for performance / partial translation:
llm:
  model: "llama3.2:3b"
  mode: "ollama"   #   --mode  : Choose your LLM mode[`ollama` (default), `gpt`, `claude`, `gemini`]
  workers: 1       #   --workers   : number of parallel threads (default: 1)
  start: 0         #   --start/end : entry index range to translate (default: 0 ~ all)
  end: -1
  batch_size: 5    #   --batch-size: entries per LLM call (default: 5)
```

# How the System Works (Simple Overview)

The system automatically:

1. Loads the `.pot` file
2. Splits text into batches
3. Applies the **general prompt** or a **language-specific prompt (if available)**
4. Adds **few-shot examples** when reference translations exist
5. Generates draft `.po` translations

Draft translations are then pushed to Gerrit → reviewed → synced to Weblate.
For full architecture details in [**PAPER.md**](docs/PAPER.md).

# Assist in Improving Translation Quality

You can tune two major components:

- **Few-shot examples** (`/examples/`)
- **Language-specific prompts** (`/prompts/`)

See [**CONTRIBUTING.md**](https://github.com/openstack-kr/knu_i18n_2025/blob/main/CONTRIBUTING.md) to learn how you can contribute.

# Code Formatting

Run PEP8 style checks:

```bash
tox -e pep8
```

Auto-fix style issues:

```bash
autopep8 --in-place --aggressive --aggressive -r .
```

# Team

- [Lee Juyeong](https://github.com/ale8ander) - Project Lead
- [Oh Jiwoo](https://github.com/5hjiwoo)
- [Jo Taeho](https://github.com/o-heat)
- [Chun Sihyeon](https://github.com/sihyeon22)
- [Hwang Jiyoung](https://github.com/imjyong)
