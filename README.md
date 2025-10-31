# knu_i18n_2025

## Overview

## Key Features

## How It Works

## Getting Started

### Using tox environment
For convenience, we provide a tox environment that automatically sets up dependencies and runs the workflow in an isolated environment.
```bash
tox -e i18n
```

### Run Locally

```bash
pip install -r requirements.txt
```

```bash
bash main.sh
```

## Code Quality Check
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

## Team

## Getting in Touch
