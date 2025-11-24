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
python -m pip install --upgrade pip
curl -fsSL https://ollama.com/install.sh | sh

pip install -r requirements.txt
bash main.sh
```

## **Step 3 — Run translation**

```bash
tox -e i18n -- "llama3.2:3b" "ko_KR"
# or
bash main.sh "llama3.2:3b" "ko_KR"
```

And that's it! Your translated .po file is ready.

# 🌐 2. Supported Languages

We support [**54 languages**](docs/language_support.md).

# ⚙️ 3. Choose Your Options

You can customize **model**, **language**, **target file**, and **performance settings**.

## **3-1. Choose LLM Model**

### **Open-source models (default)**

Uses **Ollama**. Browse available models [HERE](https://ollama.com/library).

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

## **3-3. Prepare Target File**

you can manually download the latest translated POT or PO files directly from the Weblate interface.

Steps
1. Go to the Weblate translation dashboard for the project
    (Example: https://openstack.weblate.cloud/projects/horizon/)
2. Select the project (e.g., Nova, horizon, etx.)
3. Navigate to 
```bash
project-> languages-> <Your Language>
```
4. Click Download translation
5. The target file for the selected languages will be downloaded
6. The target file must be placed under the data/target firectory

## **3-4. Performance Options**

You can adjust translation speed and scale:

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

# 🚀 5. Assist in Improving Translation Quality

You can tune two major components:

- **Few-shot examples** (`/examples/`)
- **Language-specific prompts** (`/prompts/`)

See [**CONTRIBUTING.md**](https://github.com/openstack-kr/knu_i18n_2025/blob/main/CONTRIBUTING.md) to learn how you can contribute.

# 💡 6. Code Formatting

Run PEP8 style checks:

```bash
tox -e pep8
```

Auto-fix style issues:

```bash
autopep8 --in-place --aggressive --aggressive -r .
```

# 👥 Team

- [Lee Juyeong](https://github.com/ale8ander) - Project Lead
- [Oh Jiwoo](https://github.com/5hjiwoo)
- [Jo Taeho](https://github.com/o-heat)
- [Chun Sihyeon](https://github.com/sihyeon22)
- [Hwang Jiyoung](https://github.com/imjyong)
