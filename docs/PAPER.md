# OpenStack AI Translation System — Experiments & Reproducibility

This extended documentation provides detailed information on the AI-based translation system for OpenStack i18n, including experiments, evaluation, and instructions for reproducing results.

## 1. Overview

This system is a CPU-friendly AI translation pipeline that leverages **LLMs**, **few-shot learning**, and **batch optimization** to translate `.pot` / `.po` files across multiple languages.

Key features:
- Supports 54 languages.
- Flexible LLM selection: Ollama, GPT, Claude, Gemini.
- Few-shot examples improve translation quality.
- Batch optimization for faster translation.
- Full reproducibility for evaluation.

⚠️ The full automation pipeline will be added in the near future to enable workflow automation.

## 2. System Architecture

The system workflow:

1. Load `.pot` files.
2. Split text into batches.
3. Apply general or language-specific prompts.
4. Integrate few-shot examples if references exist.
5. Generate draft `.po` translations.
6. Upload drafts to Gerrit → human review → merge to Weblate.

**Figure 1. System Workflow**

<img width="1655" height="808" alt="tox Build virtual environment (2)" src="https://github.com/user-attachments/assets/67961759-cfb4-4566-8320-36d15c0cbad0" />

The system uses the lightweight LLM framework **Ollama** and a **tox** virtual environment to perform initial AI-assisted translations.

Users can select the target language, LLM, and `.pot` files to be translated via `main.sh`.

1. During execution, `.pot` files that have not yet been translated in **Weblate** are downloaded from a specified URL.
2. For documents containing hundreds or thousands of lines, multiple sentences are divided into **(a) batches** and input into the LLM.
3. By default, a general prompt is applied, and if a **(c) language-specific prompt** exists for the target language, it is used instead.
4. When reference documents are available, a few examples are provided using the **(b) few-shot learning** method. The system also refers to the OpenStack **glossary** during translation.

## 3. Experimental Setup

### 3-1. Environment

- OS: Ubuntu 22.04  
- CPU: 8-core, 16GB memory  
- Python: 3.10  
- LLM Framework: Ollama v0.6.0  
- Target files: OpenStack i18n POT and PO files from four languages  

### 3-2. Pipeline Methods

| Method | Description |
|--------|-------------|
| a | Batch translation |
| b | Few-shot examples |
| c | Language-specific prompts |

## 4. Evaluation Method

- Sentence embeddings extracted with **Sentence Transformers** (Mean Pooling).  
- Cosine similarity computed for msgid → msgstr comparison.  
- Similarity thresholds:
  - ≥0.8: semantically similar  
  - ≥0.9: semantically almost identical  

## 5. Results

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

> Note: Korean translation quality improved by +0.1619, average improvement across four languages: +0.1268.