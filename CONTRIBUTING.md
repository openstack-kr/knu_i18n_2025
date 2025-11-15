## 📝 Contribute to Few Shot Example

### Why contribute to this project?

AI models find it difficult to grasp the exact tone, style, and variable handling just from rules alone.

Providing 2-5 "role model" examples, selected by a contributor, helps the AI learn the specific style for your language, which dramatically improves translation quality and reduces errors.

### How to Add Your Language's Examples (4 Steps)

#### Step 1: Find the Source PO File

First, navigate to the `po-example/` folder in this repository and find your language's directory (e.g., `ja`, `ru`, `ko_KR`).

* **If the source `.po` file (e.g., `nova-nova-locale.po`) is already in the directory:**
    The file is already included in the Git repository. **You can proceed to Step 2.**

* **If your language folder or `.po` file is missing:**
    This means our repository does not yet have a source `.po` file for your language (e.g., for the 40+ languages not included in the Nova project).

    The script will run in **Zero-Shot** (no examples) mode for your language by default.

    **(Optional) To contribute and improve quality:**
    You must find a representative `.po` file for your language from *any* other OpenStack project.
    1.  Create your language folder (e.g., `po-example/vi_VN/`).
    2.  Save the `.po` file you found in that folder.
    3.  You can now use this file to proceed to Step 2.

#### Step 2: Select the 2-5 Best "Role Model" Examples

Open the source `.po` file (e.g., `po-example/ko_KR/nova-nova-locale.po`) in a text editor. Read through the hundreds of translation pairs and select 2 to 5 entries that are perfect "role models" for the AI.

**Criteria for Good Examples:**
* **Includes Variables:** Sentences with complex placeholders like `%(name)s` or `%s`.
* **Includes Syntax:** Sentences with RST (reStructuredText) syntax like `:ref:` or `::` that are correctly preserved.
* **Shows Tone:** Sentences that clearly show the standard, professional tone for your language.

#### Step 3: Create the `fixed_examples.json` File

In that same directory (e.g., `po-example/ko_KR/`), create a new file named **`fixed_examples.json`**.
*(The filename must match the `--fixed_example_json` argument in `main.sh`).*

#### Step 4: Format and Paste the Examples

Copy your chosen `msgid` and `msgstr` pairs **exactly** as they appear in the `.po` file and paste them into `fixed_examples.json` using this precise JSON List format:

```json
[
  {
    "msgid": "Binding failed for port %(port_id)s, please check neutron logs for more information.",
    "msgstr": "포트 %(port_id)s에 대해 바인딩에 실패했습니다. 자세한 정보는 neutron 로그를 확인하십시오. "
  },
  {
    "msgid": "Blank components",
    "msgstr": "비어 있는 구성요소"
  }
]
```

---

### Final Step: Submit a Pull Request

Commit your new files:

1. `fixed_examples.json` (Required)
2. The source `.po` file (e.g., `nova-nova-locale.po`) (if you added it in Step 1)

Open a Pull Request. The pipeline will now automatically detect and use your high-quality examples when translating for your language.

Thank you for your contribution!

## 📝 Contribute to Language Specific Prompt

### Why contribute to this project?

In the previous version, the same prompt was used for all target languages. Therefore, generating prompts that account for the grammar and linguistic characteristics of each target language is expected to improve performance and help maintain a more consistent translation tone.

⚠️ Caution

1. When the prompt was long, lower-parameter models showed weaker performance.
2. Lower-parameter models had poorer contextual understanding compared to larger models.
3. Even if a translation is contextually natural, it may be considered incorrect if its nuance does not match the expected answer.

### How to Contribute?

#### 1. Navigate to the `prompts` Folder

All language-specific prompt files are stored in the `prompts/` directory located at the project root

```
cd prompts
```

#### 2. Locate Your Language Code File

Inside the prompts folder, you will find prompt files named using language codes, such as:

```
en.txt
ko.txt
jp.txt
fr.txt
...
```

- If a file for your language already exists
  → Open it and update or improve the prompts inside.

- If the file does not exist
  → Create a new file using the appropriate language code (e.g., `de.txt`, `id.txt`, `it.txt`, etc.).

#### 3. Use the Korean Prompt as a Reference

When creating a new language-specific prompt, you may refer to the `ko_KR.txt` file.

This will help you understand:

- The overall structure
- Section formatting
- Tone and style

#### 4. Customize the Prompt for Your Language

Feel free to adapt and rewrite the prompt so that it fits naturally within your language.

You may adjust:

- Grammar and sentence structure
- Tone and formality
- Cultural or linguistic nuances

The goal is to create a prompt that produces natural and consistent translations in your language.

#### 5. Run Validation Code

By modifying `main.sh` as shown below, you can check how similar the translations produced by the updated prompt are to the reference (`answer.po`) files, allowing you to evaluate whether the prompt generates accurate and reliable translations.

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

