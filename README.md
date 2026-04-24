# AI-based Translation System for OpenStack

<img width="1881" height="804" alt="단락 텍스트" src="https://github.com/user-attachments/assets/d0ff9e64-8a24-42e5-af1d-f4e2d2879d96" />

A lightweight, user-friendly AI translation system for OpenStack i18n.
This repository provides a local translation workflow and a Zuul-oriented CI translation pipeline powered by LLMs such as **Ollama**, GPT, Claude, and Gemini.

If you're new to OpenStack i18n, see the official [OpenStack i18n guide](https://docs.openstack.org/i18n/latest/index.html).

## Project Structure

This repository provides two independent translation workflows:

- **[local/](local/)** - For local development and manual translation testing
- **[ci/](ci/)** - For automated CI/CD pipeline integration

## Requirements

- **Python 3.10 is needed**
- **Ollama** (for local LLM) or API keys for GPT/Claude/Gemini
- **Git** (for CI workflow)

---

# Local Translation Workflow

The fastest way to run your first translation on your local machine.

By default, this system translates the [**nova** project files](./local/data/target/ko_KR/example_nova.po) into **Korean (ko_KR)** and **Japanese (ja)** using the **llama3.2:3b** model via Ollama.
You can customize the target project, model, and language in `config.yaml` (see [Choose Your Options](#choose-your-options) below).

## Quick Start (5 steps)

### **Step 1 — Clone the repository**

```bash
git clone https://github.com/openstack-kr/knu_i18n_2025.git
cd knu_i18n_2025/local
```

### **Step 2 — Install dependencies**

#### Option A) Use tox (recommended)

```bash
# if you trouble in upgrading pip, we recommend to use venv
python -m pip install --upgrade pip
pip install tox

# Install Ollama
# For Linux:
curl -fsSL https://ollama.com/install.sh | sh
# For other operating systems (Windows, macOS):
# Please visit https://ollama.com/download and follow the installation instructions
```

#### Option B) Run locally

```bash
# if you trouble in upgrading pip, we recommend to use venv
python -m pip install --upgrade pip

# Install Ollama
# For Linux:
curl -fsSL https://ollama.com/install.sh | sh
# For other operating systems (Windows, macOS):
# Please visit https://ollama.com/download and follow the installation instructions

pip install -r requirements.txt
```

### **Step 3 — Run translation**

This will translate the file specified in `config.yaml` using the configured model and language.

```bash
tox -e i18n -vv
# or
bash scripts/local.sh
```

**What's happening:**
- The system reads your target `.pot` or `.po` file from `./data/target/{lang}` directory
- Uses the specified model (default: `llama3.2:3b` via Ollama)
- Translates into your chosen language (default: ko_KR)
- Outputs translated `.po` files to `./po/{model}/{lang}/` directory

### **Step 4 — Human Review**

After AI translation, **human review is essential** to ensure accuracy and context appropriateness.
AI translations are drafts that require human verification before production use.

Open the generated `.po` file in `./po/{model}/{lang}/` directory and review the translations manually for technical accuracy, natural language flow, and consistency with existing translations.

### **Step 5  — Merge your translation to origin po**

After reviewing AI translation, merge your reviewed translations back to the original `.po` file:

```bash
tox -e i18n-merge -vv
# or
python src/merge_po.py --config config.yaml
```

This will merge your reviewed translations and save the final result to `./data/result/{lang}` directory.

## Choose Your Options

You can customize **target file**, **model**, **language**, and **performance settings** in [local/config.yaml](./local/config.yaml)

### Choose Target File

#### How it works:

1. Place your target `.pot` or `.po` file in the `./data/target/{lang}` directory
2. Specify the filename in `config.yaml`:
```yaml
# Set target_file to translate (must be placed under ./data/target/{lang})
target_file: "test.po"
```

#### File processing flow:

- **Input**: `./data/target/{lang}/{target_file}.po` or `./data/target/{lang}/{target_file}.pot`
- **Intermediate outputs**:
    - Extracted POT: `./pot/{target_file}.pot`
    - AI translations: `./po/{model}/{lang}/{target_file}.po`
- **Final output**: `./data/result/{lang}/{target_file}.po` (merged translation)

#### Downloading files from Weblate:

You can manually download the latest translated POT or PO files directly from the Weblate interface.

**Steps:**
1. Go to the Weblate translation dashboard for the project [Example](https://openstack.weblate.cloud/projects/horizon/)
2. Select the project (e.g., Nova, Horizon, etc.)
3. Navigate to: `project → languages → <Your Language>`
4. Click "Download translation"
5. Save the downloaded file to the `./data/target/{lang}/` directory
6. Update the `target_file` name in `config.yaml`

### Choose Your Language

Please insert your language code from [this link](docs/language_support.md).
The local workflow documents **54 supported language codes**.

```yaml
# Please choose exactly ONE language for local translation.
languages: "ko_KR"
```

### Choose Your Model

#### Open-source models (default)

Uses **Ollama**. Browse available models [HERE](https://ollama.com/library).

#### Closed-source models (GPT / Claude / Gemini)

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

---

# CI Translation Workflow

For automated translation in OpenStack's Zuul CI environment.

The CI workflow is implemented as an Ansible playbook and role:

- Playbook: [`ci/playbooks/ai-translation.yaml`](ci/playbooks/ai-translation.yaml)
- Role: [`ci/playbooks/roles/prepare-ai-translation/`](ci/playbooks/roles/prepare-ai-translation/)

### CI Pipeline Overview

The CI pipeline performs the following steps:

1. Extract POT files from `HEAD` and `HEAD~1`
2. Compare the two POT files and identify newly added `msgid` entries
3. Generate AI draft translations for those new entries via Ollama
4. Merge AI-generated translations into the original PO files while preserving existing human translations

If no new entries are found, the translation and merge steps are skipped.

## CI Configuration

Default CI settings are defined in
[`ci/playbooks/roles/prepare-ai-translation/defaults/main.yaml`](ci/playbooks/roles/prepare-ai-translation/defaults/main.yaml):

- **Model**: `llama3.2:3b`
- **Backend**: `ollama`
- **Batch size**: `5`
- **Workers**: `4`
- **Configured target languages**: `44`

---

# How the System Works (Simple Overview)

The system automatically:

- Loads the source `.pot` file
- Splits text into batches
- Applies the general prompt or a language-specific prompt, if available
- Adds glossary context and few-shot examples when reference translations exist
- Generates draft `.po` translations
- Merges AI-generated translations into output PO files while preserving existing translations

In CI, the pipeline compares `HEAD` and `HEAD~1` to translate only newly added entries.
For full architecture details, see [**PAPER.md**](docs/PAPER.md).

# Assist in Improving Translation Quality

You can tune two major components:

- **Few-shot examples** (`/po-example/`)
- **Language-specific prompts** (`/prompts/`)

See [**CONTRIBUTING.md**](local/CONTRIBUTING.md) to learn how you can contribute.

# Code Formatting

Run PEP8 style checks:

```bash
cd local/  # or cd ci/
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
