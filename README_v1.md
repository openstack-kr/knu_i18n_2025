# AI-based Translation System for OpenStack

A lightweight, user-friendly AI translation system for OpenStack i18n.
This tool helps contributors translate `.pot` / `.po` files into 54 languages using CPU-friendly LLMs such as **Ollama**, as well as GPT, Claude, and Gemini.

If you're new to OpenStack i18n, see the official [OpenStack i18n guide](https://docs.openstack.org/i18n/latest/index.html).

# 🚀 1. Quick Start (3 steps)

The fastest way to run your first translation.

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
pip install -r requirements.txt
bash main.sh
```

## **Step 3 — Run translation**

```bash
tox -e i18n -- "llama3.2:3b" "ko_KR"
# or
bash main.sh "llama3.2:3b" "ko_KR"
```

That’s it — your translated `.po` file is generated.

# 🌐 2. Supported Languages

We supports [**54 languages**](docs/language_support.md).

# ⚙️ 3. Choose Your Options

You can customize **model**, **language**, **target file**, and **performance settings**.

## **3-1. Choose LLM Model**

### **Open-source models (default)**

Uses **Ollama**. Browse available models [**HERE**](https://ollama.com/library).

```bash
bash main.sh "llama3.2:3b" "de"
```

### **Closed-source models (GPT / Claude / Gemini)**

Add the backend using `--llm_mode`:

```bash
bash main.sh "gpt-4o" "ko_KR" "gpt"
```

Supported modes:

- `ollama` (default)
- `gpt`
- `claude`
- `gemini`

## **3-2. Choose Languages**

Use comma-separated codes:

```bash
bash main.sh "llama3.2:3b" "de,ru,ja"
```

## **3-3. Choose Target File**

This section will be added.

## **3-4. Performance Options**

You can control translation speed & scale:

```bash
--workers     # parallel threads (default: 1)
--batch-size  # entries per LLM call (default: 5)
--start/end   # translate only part of the file
```

Example:

```bash
bash main.sh "llama3.2:3b" "es" --workers 4 --batch-size 10
```

# 🧠 4. How the System Works (Simple Overview)

The system automatically:

1. Loads the `.pot` file
2. Splits text into batches
3. Applies the **general prompt** or a **language-specific prompt (if available)**
4. Adds **few-shot examples** when reference translations exist
5. Generates draft `.po` translations

Draft translations are then pushed to Gerrit → reviewed → synced to Weblate.
For full architecture details in [**PAPER.md**](docs/PAPER.md).

# 🚀 5. Improving Translation Quality

You can tune two major components:

- **Few-shot examples** (`/examples/`)
- **Language-specific prompts** (`/prompts/`)

Details are documented in [**CONTRIBUTING.md**](https://github.com/openstack-kr/knu_i18n_2025/blob/main/CONTRIBUTING.md).

# 🧼 6. Code Quality

Run PEP8 style checks:

```bash
tox -e pep8
```

Auto-fix style issues:

```bash
autopep8 --in-place -r .
```

# 👥 Team

- [Lee Juyeong](https://github.com/ale8ander)
- [Oh Jiwoo](https://github.com/5hjiwoo)
- [Jo Taeho](https://github.com/o-heat)
- [Chun Sihyeon](https://github.com/sihyeon22)
- [Hwang Jiyoung](https://github.com/imjyong)