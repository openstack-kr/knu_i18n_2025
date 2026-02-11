import os
import json
import subprocess
import configparser
import re
import logging
from datetime import datetime
import requests
from babel.messages import pofile
import csv

class TranslationUtils:
    def __init__(self, project_dir, glossary_url=None):
        self.project_dir = project_dir
        self.glossary_url = glossary_url or (
            "https://opendev.org/openstack/i18n"
            "/raw/branch/master/glossary/locale/{lang}/LC_MESSAGES/glossary.po"
        )
        self._setup_logging()

    def _setup_logging(self):
        logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
        self.logger = logging.getLogger(__name__)

    def _download_file(self, url, dest_path, label):
        """URL에서 파일을 다운로드하여 dest_path로 저장한다. 실패 시 False 반환."""
        self.logger.info(f"Downloading {label} from {url}...")
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            with open(dest_path, "wb") as f:
                f.write(response.content)
            self.logger.info(f"Successfully downloaded and saved to {dest_path}\n")
            return True
        except requests.exceptions.RequestException as e:
            self.logger.warning(f"Warning: Could not download {label}: {e}\n")
            return False

    def get_modulename(self, project):
        """
        project명과 project 폴더명이 불일치 하는 경우가 있다.
        setup.cfg / pyproject.toml에서 pybabel 스캔할 폴더명을 조회한다.

        우선순위 (upstream get-modulename.py와 동일, pyproject.toml 추가):
          1. setup.cfg  [openstack_translations] python_modules
          2. setup.cfg  [files] packages
          3. pyproject.toml [tool.setuptools] packages
          4. fallback: project name 그대로
        """
        # --- setup.cfg ---
        setup_cfg = os.path.join(self.project_dir, "setup.cfg")
        if os.path.isfile(setup_cfg):
            parser = configparser.ConfigParser()
            parser.read(setup_cfg)

            if parser.has_option("openstack_translations", "python_modules"):
                modules = [
                    m.strip() for m in parser.get(
                        "openstack_translations",
                        "python_modules").split("\n") if m.strip()]
                if modules:
                    return modules[0]

            if parser.has_option("files", "packages"):
                modules = [m.strip() for m in
                           parser.get("files", "packages").split("\n")
                           if m.strip()]
                if modules:
                    return modules[0]

        # --- pyproject.toml ---
        # [tool.setuptools] packages = ["pkg_a", "pkg_b", ...]
        pyproject = os.path.join(self.project_dir, "pyproject.toml")
        if os.path.isfile(pyproject):
            with open(pyproject, "r", encoding="utf-8") as f:
                text = f.read()
            match = re.search(
                r'\[tool\.setuptools\].*?packages\s*=\s*\[(.*?)\]',
                text, re.DOTALL
            )
            if match:
                packages = re.findall(r'"([^"]+)"', match.group(1))
                if packages:
                    return packages[0]

        return project

    def load_glossary(self, lang, glossary_dir="./glossary", glossary_po_file="glossary.po", glossary_json_file="glossary.json"):
        """
        특정 언어의 glossary.po 파일을 다운로드/로드하고 JSON 백업을 생성/로드한다.

        Args:
            lang (str): 처리할 언어 코드
            glossary_dir (str): 용어집 최상위 디렉터리
            glossary_po_file (str): glossary PO 파일명
            glossary_json_file (str): glossary JSON 캐시 파일명

        Returns:
            dict: Glossary key-value 매핑 (id → string)
        """
        lang_dir = os.path.join(glossary_dir, lang)
        os.makedirs(lang_dir, exist_ok=True)

        glossary_po_path = os.path.join(lang_dir, glossary_po_file)
        glossary_json_path = os.path.join(lang_dir, glossary_json_file)
        glossary_url = self.glossary_url.format(lang=lang)

        G = {}

        # Download Glossary PO if needed
        if not os.path.exists(glossary_po_path):
            if not self._download_file(
                    glossary_url,
                    glossary_po_path,
                    f"glossary for [{lang}]"):
                return G

        if os.path.exists(glossary_json_path):
            self.logger.info(f"Loading cached glossary for [{lang}]...")
            try:
                with open(glossary_json_path, "r", encoding="utf-8") as f:
                    G = json.load(f)
                self.logger.info(f"Glossary for [{lang}] loaded with {len(G)} terms.\n")
            except Exception as e:
                self.logger.warning(f"Warning: Failed to load JSON cache for [{lang}]: {e}")

        else:
            if os.path.exists(glossary_po_path):
                self.logger.info(f"Building glossary for [{lang}]...")
                try:
                    with open(glossary_po_path, "rb") as f:
                        glossary_po = pofile.read_po(f)
                    G = {
                        entry.id.strip().lower(): entry.string.strip()
                        for entry in glossary_po
                        if entry.id and entry.string
                    }
                    self.logger.info(f"Glossary for [{lang}] loaded with {len(G)} terms.\n")
                    with open(glossary_json_path, "w", encoding="utf-8") as f:
                        json.dump(G, f, ensure_ascii=False, indent=2)
                    self.logger.info(f"Backup JSON written to {glossary_json_path}\n")
                except Exception as e:
                    self.logger.error(f"Error reading Glossary PO file for [{lang}]: {e}\n")

        return G

    def load_examples(self, lang, url_template, example_file, example_dir):
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
            return examples

        lang_dir = os.path.join(example_dir, lang)
        os.makedirs(lang_dir, exist_ok=True)

        example_path = os.path.join(lang_dir, example_file)
        example_url = url_template.format(lang=lang)

        # Download Example PO if needed
        if not os.path.exists(example_path):
            if not self._download_file(
                    example_url,
                    example_path,
                    f"examples for [{lang}]"):
                return examples

        if os.path.exists(example_path):
            self.logger.info(
                f"Loading few-shot examples from "
                f"{os.path.basename(example_path)} for [{lang}]..."
            )
            try:
                with open(example_path, "rb") as f:
                    example_po = pofile.read_po(f)

                for entry in example_po:
                    if entry.id and entry.string:
                        examples.append((entry.id, entry.string))
                self.logger.info(f"Loaded {len(examples)} examples for [{lang}].\n")
            except Exception as e:
                self.logger.warning(
                    f"Warning: Error reading example PO file for [{lang}]: {e}\n")
                examples = []

        return examples

    def load_fixed_examples(self, lang_code, example_dir, fixed_example_json, example_url, example_file):
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
                self.logger.info(
                    f"Loaded {len(language_examples)} fixed examples "
                    f"from '{example_path}'."
                )
                return [(ex['msgid'], ex['msgstr']) for ex in language_examples]

        except FileNotFoundError:
            self.logger.info(f"'{example_path}' not found. Attempting fallback.")
        except Exception as e:
            self.logger.warning(f"WARNING: Error loading '{example_path}': {e}.")

        self.logger.info(f"Loading default examples (top 2) from '{example_file}' instead.")

        try:
            all_examples_from_po = self.load_examples(
                lang_code, example_url, example_file, example_dir
            )

            if not all_examples_from_po:
                self.logger.warning(f"WARNING: Could not load .po examples for [{lang_code}].")
                return []

            num_to_sample = min(len(all_examples_from_po), 2)
            example_data = all_examples_from_po[0:num_to_sample]

            self.logger.info(f"Loaded top {len(example_data)} examples from .po file.")
            return example_data

        except Exception as e:
            self.logger.error(f"ERROR: Failed to load .po file: {e}")
            return []

    def save_experiment_log(self, model_name: str, pot_file: str, po_file: str, duration_sec: float, language: str, accuracy: float | None = None, results_csv_path: str = "./experiments.csv"):
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

            self.logger.info(f"실험 로그 추가 완료: {results_csv_path}")
        except Exception as e:
            self.logger.warning(f"Warning: 실험 로그 저장 실패: {e}")

    @staticmethod
    def is_untranslated(entry) -> bool:
        """msgstr(또는 복수형 msgstr_plural) 중 하나라도 채워져 있으면 '번역됨'으로 판단."""
        if entry.msgid == "":
            return False
        if entry.obsolete:
            return False
        if entry.msgid_plural:
            return not any(s.strip() for s in entry.msgstr_plural.values())
        return not bool(entry.msgstr.strip())