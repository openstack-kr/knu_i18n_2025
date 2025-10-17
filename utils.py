import os
import json
import subprocess
from datetime import datetime


def save_experiment_log(
    model_name: str,
    pot_file: str,
    po_file: str,
    duration_sec: float,
    accuracy: float | None = None,
    results_json_path: str = "./experiments.json",
):
    """
    실험 결과를 JSON 파일로 누적 저장하는 함수
    Git 버전 정보와 timestamp를 자동으로 포함한다.

    Args:
        model_name (str): 사용한 LLM 모델 이름
        pot_file (str): 번역 대상 pot 파일 경로
        po_file (str): 생성된 po 파일 경로
        duration_sec (float): 번역 소요 시간(초)
        accuracy (float | None): 평가 정확도 (선택)
        results_json_path (str): 결과 저장 경로 (기본 './experiments.json')
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
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.DEVNULL
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

    # JSON 파일에 누적 저장
    try:
        if os.path.exists(results_json_path):
            with open(results_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, list):
                    data = [data]
        else:
            data = []

        data.append(result_entry)

        with open(results_json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"실험 로그 추가 완료: {results_json_path}")
    except Exception as e:
        print(f"Warning: 실험 로그 저장 실패: {e}")