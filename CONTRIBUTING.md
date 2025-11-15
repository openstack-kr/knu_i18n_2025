## Contirbute to Few Shot Example

## Contirbute to Language Specific Prmopt

## Run Validation Code

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
