# AI-based Translation System for OpenStack

A lightweight, user-friendly AI translation system for OpenStack i18n.
This tool helps contributors translate `.pot` / `.po` files into 54 languages using CPU-friendly LLMs such as **Ollama**, as well as GPT, Claude, and Gemini.

If you're new to OpenStack i18n, see the official [OpenStack i18n guide](https://docs.openstack.org/i18n/latest/index.html).

## Requirements

- **Python 3.10 is needed**
- Designed for **local** and **CI environments**

# Quick Start (5 steps)

The fastest way to run your first translation.

By default, this system translates the **nova** project files into **Korean (ko_KR)** and **Japanese (ja)** using the **llama3.2:3b** model via Ollama.
You can customize the target project, model, and language in `config.yaml` (see [Choose Your Options](#choose-your-options) below).<br>

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

# Install Ollama
# For Linux:
curl -fsSL https://ollama.com/install.sh | sh
# For other operating systems (Windows, macOS):
# Please visit https://ollama.com/download and follow the installation instructions

# prepare environment
tox -e i18n -vv
```

### Option B) Run locally

```bash
python -m pip install --upgrade pip

# Install Ollama
# For Linux:
curl -fsSL https://ollama.com/install.sh | sh
# For other operating systems (Windows, macOS):
# Please visit https://ollama.com/download and follow the installation instructions

pip install -r requirements.txt
bash loca.sh
```

## **Step 3 — Run translation**

This will translate the file specified in `config.yaml` using the configured model and language.

```bash
tox -e i18n --vv
# or
bash local.sh
```

**What's happening:**
- The system reads your target `.pot` or `.po` file from `./data/target/` directory
- Uses the specified model (default: `llama3.2:3b` via Ollama)
- Translates into your chosen language (default: ko_KR, ja)
- Outputs a translated `.po` files to `./po/{model}/{lang}/` directory

## **Step 4 — Human Review**

After AI translation, **human review is essentail** to ensure accuracy and context appropriateness.
AI translations are drafts that require verification before proudction use.

Open the generated `.po` file in `./po/{model}/{lang}/` directory and review the translations manually for technical accuracy, natural language flow, and consistency with existing translations.

## **Step 5  — Merge your translation to origin po**

After reviewing AI translation, merge your reviewed translations back to the original `.po` file:

```bash
python merge_po.py --config config.yaml
```

This will merge your reviewed translations and save the final result to `./data/result` directory.

# Choose Your Options

You can customize **target file**, **model**, **language**, and **performance settings** in [config.yaml](./config.yaml)

## Choose Target File

### How it works:

1. Place your target `.pot` or `.po` file in the `./data/target/` directory
2. Specify the filename in `config.yaml`:
```yaml
files:
    # Set target file path. Please put file under ./data/target/
    target_file: "nova.po"
```

### File processing flow:

- **Input**: `./data/target/{your_file}.po` or `./data/target/{your_file}.pot`
- **Intermediate outputs**:
    - Extracted POT: `./pot/{your_file}.pot`
    - AI translations: `./po/{model}/{lang}/{your_file}.po`
- **Final output**: `./data/result/{your_file}.po` (merged translation)

### Downloading files from Weblate:

You can manually download the latest translated POT or PO files directly from the Weblate interface.

**Steps:**
1. Go to the Weblate translation dashboard for the project [Example](https://openstack.weblate.cloud/projects/horizon/)
2. Select the project (e.g., Nova, Horizon, etc.)
3. Navigate to: `project → languages → <Your Language>`
4. Click "Download translation"
5. Save the downloaded file to the `./data/target/` directory
6. Update the `target_file` name in `config.yaml`

## Choose Your Language

Please insert your language code from [this link](docs/language_support.md).
We support **54 languages**

```yaml
languages:
# Add your language.
  - "ko_KR"
  - "ja"
```

## Choose Your Model

### Open-source models (default)

Uses **Ollama**. Browse available models [HERE](https://ollama.com/library).

### Closed-source models (GPT / Claude / Gemini)

When using closed-source model, edit the backend using `llm.mode`: [`ollama` (default), `gpt`, `claude`, `gemini`]

```yaml
# You can tune these arguments for performance / partial translation:
llm:
  model: "llama3.2:3b"
  mode: "ollama"   # Choose your LLM mode: `ollama` (default), `gpt`, `claude`, `gemini`
  workers: 1       # number of parallel threads (default: 1)
  start: 0         # entry index range to translate (default: 0 ~ all)
  end: -1
  batch_size: 5    # entries per LLM call (default: 5)
```

# CI Integration

For automated translation in OpenStack's Zuul CI environment, use the provided CI script:

```bash
bash ci.sh
```

The script automatically uses `config.yaml` by default, or you can specify a different config file:

```bash
bash ci.sh my-config.yaml
```

**What ci.sh does:**

The script runs a 3-step pipeline:

1. **Find changed content**: Runs `commit_diff.py` to detect added or edited  msgid entries in your target file and extracts them to a `.pot` file
2. **Translate**: Executes `translate.py` to translate the extracted entries using your configured model
3. **Merge**: Uses `merge_po.py` to merge AI-translated content back into the original `.po` file

Results are saved to `./data/result/{project}.po`

**Usage in CI pipeline:**

```yaml
# Example Zuul job configuration
- job:
    name: translate-pot-files
    run: playbooks/translate.yaml

# In your playbook:
- name: Run AI Translation
    shell: bash ci.sh
```

The CI workflow is optimized to translate only changed content, making it efficient for continuous integration pipelines.

# How the System Works (Simple Overview)

The system automatically:

- Loads the `.pot` file
- Splits text into batches
- Applies the **general prompt** or a **language-specific prompt (if available)**
- Adds **few-shot examples** when reference translations exist
- Generates draft `.po` translations

Draft translations are then pushed to Gerrit → reviewed → synced to Weblate.
For full architecture details, see [**PAPER.md**](docs/PAPER.md).

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
