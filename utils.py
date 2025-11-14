import os
import json
import subprocess
from datetime import datetime
import argparse
import requests
from babel.messages import pofile
import csv


def parse_args():
    """
    명령줄 인자를 파싱하는 함수.
    Parses command-line arguments for the translation pipeline.

    Returns:
        argparse.Namespace: 파싱된 인자 객체 / Parsed arguments object
    """
    parser = argparse.ArgumentParser(
        description="AI-based translation pipeline")
    parser.add_argument(
        "--model",
        required=True,
        help="Model name to use (e.g., qwen2.5:1.5b)")
    parser.add_argument(
        "--pot_dir",
        default="./pot",
        help="Path to the POT file directory")
    parser.add_argument(
        "--po_dir",
        default="./po",
        help="Path to save the translated PO files")
    parser.add_argument(
        "--glossary_dir",
        default="./glossary",
        help="Path to the glossary directory")
    parser.add_argument(
        "--start",
        type=int,
        default=0,
        help="Start index for translation")
    parser.add_argument("--end", type=int, default=None,
                        help="End index for translation")
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Number of parallel worker threads")
    parser.add_argument(
        "--pot_url",
        required=True,
        help="URL for downloading the POT file")
    parser.add_argument(
        "--target_pot_file",
        required=True,
        help="Target POT filename")
    parser.add_argument(
        "--glossary_url",
        required=True,
        help="URL for downloading the glossary file")
    parser.add_argument(
        "--glossary_po_file",
        default="glossary.po",
        help="Glossary PO filename")
    parser.add_argument(
        "--glossary_json_file",
        default="glossary.json",
        help="Glossary JSON filename")
    parser.add_argument(
        "--languages",
        required=True,
        help="list of language codes")
    return parser.parse_args()


def init_environment(
    pot_dir,
    po_dir,
    glossary_dir,
    *,
    pot_url,
    target_pot_file,
):

    os.makedirs(pot_dir, exist_ok=True)
    os.makedirs(po_dir, exist_ok=True)
    os.makedirs(glossary_dir, exist_ok=True)

    pot_file_path = os.path.join(pot_dir, target_pot_file)

    # Download POT if needed
    if not os.path.exists(pot_file_path):
        print(f"Downloading pot file from {pot_url}...")
        try:
            response = requests.get(pot_url, timeout=30)
            response.raise_for_status()
            with open(pot_file_path, "wb") as f:
                f.write(response.content)
            print(f"Successfully downloaded and saved to {pot_file_path}")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Error downloading POT file: {e}")
    else:
        print(f"'{target_pot_file}' already exists. Skipping download.")

    return pot_file_path


def load_glossary(lang, url_template, glossary_file, json_file, glossary_dir):

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
