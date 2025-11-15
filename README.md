# knu_i18n_2025

## Overview

## Key Features

## How It Works
<img width="1655" height="808" alt="tox Build virtual environment (1)" src="https://github.com/user-attachments/assets/73f875bd-2f9a-45a0-8fa7-4f319ed966be" />

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

## 3. Code Quality Check
We use [tox](https://tox.wiki) to ensure code consistency and quality.
1. PEP8 Style Check 
```bash
tox -e pep8
```

### 4. Run Validation Code

```bash
# Options:
# --model MODEL_NAME        (default: princeton-nlp/sup-simcse-roberta-base)
#  --batch-size N            (default: 64)
#  --threshold 0.80          (report %≥threshold)
#  --only-translated         (skip empty msgstr)
#  --skip-fuzzy              (skip entries with 'fuzzy' flag)
#  --normalize-text          (strip + collapse spaces before embedding)
#  --lowercase               (lowercase before embedding)
#  --topk 20                 (how many best/worst pairs to store in JSON)

python po_quality_check.py --a "answer.po" --b "ko.po" --out result_ko.json --model BM-K/KoSimCSE-roberta-multitask --only-translated --normalize-text
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

## Paper-Experiments Reproducibility

## Team

## Getting in Touch
