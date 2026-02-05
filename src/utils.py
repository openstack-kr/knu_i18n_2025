import os
import json
import subprocess
from datetime import datetime
import requests
from babel.messages import pofile
import csv

def load_glossary(lang, url_template, glossary_file, json_file, glossary_dir):
    """
    특정 언어의 glossary.po 파일을 다운로드/로드하고 JSON 백업을 생성/로드한다.
    Loads/downloads a language-specific glossary .po file
    and loads/writes a JSON backup.

    Args:
        lang (str): 처리할 언어 코드
        url_template (str): 다운로드 URL 템플릿
        glossary_file (str): glossary .po 파일명
        json_file (str): glossary .json 파일명
        glossary_dir (str): 용어집 최상위 디렉터리

    Returns:
        dict: Glossary key-value 매핑 (id → string)
    """

    if not url_template:
        return

    lang_dir = os.path.join(glossary_dir, lang)
    os.makedirs(lang_dir, exist_ok=True)

    glossary_po_path = os.path.join(lang_dir, glossary_file)
    glossary_json_path = os.path.join(lang_dir, json_file)
    glossary_url = url_template.format(lang=lang)

    G = {}

    # Download Glossary PO if needed
    if not os.path.exists(glossary_po_path):
        print(f"Downloading glossary for [{lang}] from {glossary_url}...")
        try:
            response = requests.get(glossary_url, timeout=30)
            response.raise_for_status()
            with open(glossary_po_path, "wb") as f:
                f.write(response.content)
            print(f"Successfully downloaded and saved to {glossary_po_path}\n")
        except requests.exceptions.RequestException as e:
            print(f"Warning: Could not download glossary for [{lang}]: {e}\n")
            return G

    if os.path.exists(glossary_json_path):
        print(f"Loading cached glossary for [{lang}]...")
        try:
            with open(glossary_json_path, "r", encoding="utf-8") as f:
                G = json.load(f)
            print(f"Glossary for [{lang}] loaded with {len(G)} terms.\n")
        except Exception as e:
            print(f"Warning: Failed to load JSON cache for [{lang}]: {e}")

    else:
        if os.path.exists(glossary_po_path):
            print(f"Building glossary for [{lang}]...")
            try:
                with open(glossary_po_path, "rb") as f:
                    glossary_po = pofile.read_po(f)
                G = {
                    entry.id.strip().lower(): entry.string.strip()
                    for entry in glossary_po
                    if entry.id and entry.string
                }
                print(f"Glossary for [{lang}] loaded with {len(G)} terms.\n")
                with open(glossary_json_path, "w", encoding="utf-8") as f:
                    json.dump(G, f, ensure_ascii=False, indent=2)
                print(f"Backup JSON written to {glossary_json_path}\n")
            except Exception as e:
                print(f"Error reading Glossary PO file for [{lang}]: {e}\n")

    return G


def load_examples(lang, url_template, example_file, example_dir):
    """
    특정 언어의 번역 예시 .po 파일을 다운로드/로드하여 리스트로 반환한다.
    Loads/downloads a language-specific example .po file
    and returns a list of (id, str) tuples.

    Args:
        lang (str): 처리할 언어 코드
        url_template (str): 다운로드 URL 템플릿
        example_file (str): example .po 파일명
        example_dir (str): 예시 파일 최상위 디렉터리

    Returns:
        list: (msgid, msgstr) 튜플의 리스트
    """
    examples = []

    if not url_template:
        return

    lang_dir = os.path.join(example_dir, lang)
    os.makedirs(lang_dir, exist_ok=True)

    example_path = os.path.join(lang_dir, example_file)
    example_url = url_template.format(lang=lang)

    # Download Example PO if needed
    if not os.path.exists(example_path):
        print(f"Downloading examples for [{lang}] from {example_url}...")
        try:
            response = requests.get(example_url, timeout=30)
            response.raise_for_status()
            with open(example_path, "wb") as f:
                f.write(response.content)
            print(f"Successfully downloaded and saved to {example_path}\n")
        except requests.exceptions.RequestException as e:
            print(f"Warning: Could not download examples for [{lang}]: {e}\n")
            return examples

    if os.path.exists(example_path):
        print(
            f"Loading few-shot examples from "
            f"{os.path.basename(example_path)} for [{lang}]..."
        )
        try:
            with open(example_path, "rb") as f:
                example_po = pofile.read_po(f)

            for entry in example_po:
                if entry.id and entry.string:
                    examples.append((entry.id, entry.string))
            print(f"Loaded {len(examples)} examples for [{lang}].\n")
        except Exception as e:
            print(
                f"Warning: Error reading example PO file for [{lang}]: {e}\n")
            examples = []

    return examples


def load_fixed_examples(
        lang_code,
        example_dir,
        fixed_example_json,
        example_url,
        example_file):
    """
    고정된 번역 예시(JSON)를 로드하거나, 실패 시 기본 예시(.po)를 가져온다.
    Loads fixed translation examples (JSON) or falls back to default
    examples (.po) upon failure.

    Args:
        lang_code (str): 처리할 언어 코드
        example_dir (str): 예시 파일 최상위 디렉터리
        fixed_example_json (str): 고정 예시 JSON 파일명
        example_url (str): Fallback용 .po 파일 다운로드 URL
        example_file (str): Fallback용 .po 파일명

    Returns:
        list: (msgid, msgstr) 튜플의 리스트
    """
    example_path = os.path.join(example_dir, lang_code, fixed_example_json)

    try:
        with open(example_path, 'r', encoding='utf-8') as f:
            language_examples = json.load(f)

        if language_examples:
            print(
                f"Loaded {len(language_examples)} fixed examples "
                f"from '{example_path}'."
            )
            return [(ex['msgid'], ex['msgstr']) for ex in language_examples]

    except FileNotFoundError:
        print(f"'{example_path}' not found. Attempting fallback.")
    except Exception as e:
        print(f"WARNING: Error loading '{example_path}': {e}.")

    print(f"Loading default examples (top 2) from '{example_file}' instead.")

    try:
        all_examples_from_po = load_examples(
            lang_code, example_url, example_file, example_dir
        )

        if not all_examples_from_po:
            print(f"WARNING: Could not load .po examples for [{lang_code}].")
            return []

        num_to_sample = min(len(all_examples_from_po), 2)
        example_data = all_examples_from_po[0:num_to_sample]

        print(f"Loaded top {len(example_data)} examples from .po file.")
        return example_data

    except Exception as e:
        print(f"ERROR: Failed to load .po file: {e}")
        return []


def save_experiment_log(
    model_name: str,
    pot_file: str,
    po_file: str,
    duration_sec: float,
    language: str,
    accuracy: float | None = None,
    results_csv_path: str = "./experiments.csv",
):
    """
    실험 결과를 CSV 파일로 누적 저장하는 함수.
    Saves experiment results to a CSV log with Git metadata and timestamp.

    Args:
        model_name (str): 사용한 LLM 모델 이름
        pot_file (str): 번역 대상 POT 파일 경로
        po_file (str): 생성된 PO 파일 경로
        duration_sec (float): 번역 소요 시간(초)
        language (str): 번역 언어
        accuracy (float | None): 번역 품질 정확도 (선택)
        results_csv_path (str): 결과 저장 CSV 파일 경로 (기본 './experiments.csv')

    Returns:
        None
    """

    # Git 정보 수집
    try:
        git_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()
    except Exception:
        git_commit = None

    try:
        git_branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()
    except Exception:
        git_branch = None

    # 결과 entry 구성
    result_entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "model": model_name,
        "pot_file": os.path.abspath(pot_file),
        "po_file": os.path.abspath(po_file),
        "duration_sec": duration_sec,
        "language": language,
        "accuracy": accuracy,
        "git_commit": git_commit,
        "git_branch": git_branch,
    }

    # CSV 파일에 누적 저장
    try:
        file_exists = os.path.exists(results_csv_path)
        with open(results_csv_path,
                  "a",
                  newline="",
                  encoding="utf-8") as csvfile:
            fieldnames = [
                "timestamp",
                "model",
                "pot_file",
                "po_file",
                "duration_sec",
                "language",
                "accuracy",
                "git_commit",
                "git_branch",
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            if not file_exists:
                writer.writeheader()
            writer.writerow(result_entry)

        print(f"실험 로그 추가 완료: {results_csv_path}")
    except Exception as e:
        print(f"Warning: 실험 로그 저장 실패: {e}")


def is_untranslated(entry) -> bool:
    """msgstr(또는 복수형 msgstr_plural) 중 하나라도 채워져 있으면 '번역됨'으로 판단."""
    if entry.msgid == "":
        return False
    if entry.obsolete:
        return False
    if entry.msgid_plural:
        return not any(s.strip() for s in entry.msgstr_plural.values())
    return not bool(entry.msgstr.strip())
