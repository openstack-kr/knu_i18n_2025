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
        default="glossary_ko.po",
        help="Glossary PO filename")
    parser.add_argument(
        "--glossary_json_file",
        default="glossary_ko.json",
        help="Glossary JSON filename")
    return parser.parse_args()


def init_environment(
    pot_dir,
    po_dir,
    glossary_dir,
    *,
    pot_url,
    target_pot_file,
    glossary_url,
    glossary_po_file,
    glossary_json_file,
):
    """
    번역 환경을 초기화하고 필요한 파일(POT, Glossary)을 다운로드한다.
    Initializes directories and downloads required files (POT and Glossary).

    Args:
        pot_dir (str): POT 파일 저장 디렉터리
        po_dir (str): PO 파일 저장 디렉터리
        glossary_dir (str): 용어집 디렉터리
        pot_url (str): POT 파일 다운로드 URL
        target_pot_file (str): POT 파일명
        glossary_url (str): Glossary 파일 다운로드 URL
        glossary_po_file (str): Glossary PO 파일명
        glossary_json_file (str): Glossary JSON 파일명

    Returns:
        tuple: (pot_file_path, glossary_po_path, glossary_json_path)
    """
    os.makedirs(pot_dir, exist_ok=True)
    os.makedirs(po_dir, exist_ok=True)
    os.makedirs(glossary_dir, exist_ok=True)

    pot_file_path = os.path.join(pot_dir, target_pot_file)
    glossary_po_path = os.path.join(glossary_dir, glossary_po_file)
    glossary_json_path = os.path.join(glossary_dir, glossary_json_file)

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

    # Download Glossary PO if needed
    if not os.path.exists(glossary_po_path):
        print(f"Downloading glossary file from {glossary_url}...")
        try:
            response = requests.get(glossary_url, timeout=30)
            response.raise_for_status()
            with open(glossary_po_path, "wb") as f:
                f.write(response.content)
            print(f"Successfully downloaded and saved to {glossary_po_path}\n")
        except requests.exceptions.RequestException as e:
            print(f"Warning: Could not download glossary file: {e}\n")
    else:
        print(f"'{glossary_po_file}' already exists. Skipping download.\n")

    return pot_file_path, glossary_po_path, glossary_json_path


def load_glossary(glossary_po_path, glossary_json_path):
    """
    glossary.po 파일을 로드하고 JSON 백업을 생성한다.
    Loads glossary from a .po file and writes a JSON backup.

    Args:
        glossary_po_path (str): Glossary PO 파일 경로
        glossary_json_path (str): Glossary JSON 백업 파일 경로

    Returns:
        dict: Glossary key-value 매핑 (id → string)
    """
    G = {}
    if os.path.exists(glossary_json_path):
        print(f"Loading glossary from cached JSON: {glossary_json_path}")
        try:
            with open(glossary_json_path, "r", encoding="utf-8") as f:
                G = json.load(f)
            print(f"Glossary loaded from JSON with {len(G)} term.\n")
        except Exception as e:
            print(f"Error reading glossary file: {e}\n")

    else:
        if os.path.exists(glossary_po_path):
            print("Converting glossary.po -> glossary.json...")
            try:
                with open(glossary_po_path, "rb") as f:
                    glossary_po = pofile.read_po(f)
                G = {
                    entry.id.strip().lower(): entry.string.strip()
                    for entry in glossary_po
                    if entry.id and entry.string
                }
                print(f"Glossary loaded with {len(G)} terms.")
                with open(glossary_json_path, "w", encoding="utf-8") as f:
                    json.dump(G, f, ensure_ascii=False, indent=2)
                print(f"Backup JSON written to {glossary_json_path}\n")
            except Exception as e:
                print(f"Error reading Glossary file: {e}\n")
    return G


def save_experiment_log(
    model_name: str,
    pot_file: str,
    po_file: str,
    duration_sec: float,
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
