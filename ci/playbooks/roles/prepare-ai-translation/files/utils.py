import os
import json
import subprocess
import configparser
import re
import logging
from datetime import datetime

import requests
import yaml
from babel.messages import pofile
import csv


def load_config(config_path="config.yaml"):
    """Load configuration from a YAML file.

    Args:
        config_path: Path to the YAML config file.
            Defaults to 'config.yaml' in the current directory.

    Returns:
        dict: Parsed configuration dictionary.
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


class TranslationUtils:
    def __init__(self, project_dir, glossary_url=None):
        self.project_dir = project_dir
        self.glossary_url = glossary_url
        self._setup_logging()

    def _setup_logging(self):
        logging.basicConfig(
            level=logging.INFO, format='%(levelname)s: %(message)s')
        self.logger = logging.getLogger(__name__)

    def _download_file(self, url, dest_path, label):
        """Download a file from URL and save to dest_path.

        Returns:
            bool: True on success, False on failure.
        """
        self.logger.info(f"Downloading {label} from {url}...")
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            with open(dest_path, "wb") as f:
                f.write(response.content)
            self.logger.info(
                f"Successfully downloaded and saved to {dest_path}\n")
            return True
        except requests.exceptions.RequestException as e:
            self.logger.warning(
                f"Warning: Could not download {label}: {e}\n")
            return False

    def get_modulename(self, project):
        """Resolve the actual Python module directory name for a project.

        The project name and source directory may differ.
        Looks up the scan target in setup.cfg / pyproject.toml.

        Priority (matches upstream get-modulename.py):
          1. setup.cfg  [openstack_translations] python_modules
          2. setup.cfg  [files] packages
          3. pyproject.toml [tool.setuptools] packages
          4. Fallback: project name as-is
        """
        setup_cfg = os.path.join(self.project_dir, "setup.cfg")
        if os.path.isfile(setup_cfg):
            parser = configparser.ConfigParser()
            parser.read(setup_cfg)

            if parser.has_option(
                    "openstack_translations", "python_modules"):
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

    def load_glossary(self, lang, glossary_dir,
                      glossary_po_file="glossary.po",
                      glossary_json_file="glossary.json"):
        """Download/load a glossary PO file and build a JSON cache.

        Args:
            lang: Language code to process.
            glossary_dir: Root directory for glossary files.
            glossary_po_file: Glossary PO filename.
            glossary_json_file: Glossary JSON cache filename.

        Returns:
            dict: Glossary mapping (English term -> translated term).
        """
        lang_dir = os.path.join(glossary_dir, lang)
        os.makedirs(lang_dir, exist_ok=True)

        glossary_po_path = os.path.join(lang_dir, glossary_po_file)
        glossary_json_path = os.path.join(lang_dir, glossary_json_file)
        glossary_url = self.glossary_url.format(lang=lang)

        glossary = {}

        if not os.path.exists(glossary_po_path):
            if not self._download_file(
                    glossary_url,
                    glossary_po_path,
                    f"glossary for [{lang}]"):
                return glossary

        if os.path.exists(glossary_json_path):
            self.logger.info(f"Loading cached glossary for [{lang}]...")
            try:
                with open(glossary_json_path, "r", encoding="utf-8") as f:
                    glossary = json.load(f)
                self.logger.info(
                    f"Glossary for [{lang}] loaded "
                    f"with {len(glossary)} terms.\n")
            except Exception as e:
                self.logger.warning(
                    f"Warning: Failed to load JSON cache "
                    f"for [{lang}]: {e}")
        else:
            if os.path.exists(glossary_po_path):
                self.logger.info(f"Building glossary for [{lang}]...")
                try:
                    with open(glossary_po_path, "rb") as f:
                        glossary_po = pofile.read_po(f)
                    glossary = {
                        entry.id.strip().lower(): entry.string.strip()
                        for entry in glossary_po
                        if entry.id and entry.string
                    }
                    self.logger.info(
                        f"Glossary for [{lang}] loaded "
                        f"with {len(glossary)} terms.\n")
                    with open(
                            glossary_json_path, "w", encoding="utf-8") as f:
                        json.dump(glossary, f, ensure_ascii=False, indent=2)
                    self.logger.info(
                        f"Backup JSON written to {glossary_json_path}\n")
                except Exception as e:
                    self.logger.error(
                        f"Error reading Glossary PO file "
                        f"for [{lang}]: {e}\n")

        return glossary

    def load_examples(self, lang, url_template, example_file, example_dir):
        """Download/load a language-specific example PO file.

        Args:
            lang: Language code to process.
            url_template: URL template for downloading the PO file.
            example_file: Example PO filename.
            example_dir: Root directory for example files.

        Returns:
            list: List of (msgid, msgstr) tuples.
        """
        examples = []

        if not url_template:
            return examples

        lang_dir = os.path.join(example_dir, lang)
        os.makedirs(lang_dir, exist_ok=True)

        example_path = os.path.join(lang_dir, example_file)
        example_url = url_template.format(lang=lang)

        if not os.path.exists(example_path):
            if not self._download_file(
                    example_url,
                    example_path,
                    f"examples for [{lang}]"):
                return examples

        if os.path.exists(example_path):
            self.logger.info(
                f"Loading few-shot examples from "
                f"{os.path.basename(example_path)} for [{lang}]...")
            try:
                with open(example_path, "rb") as f:
                    example_po = pofile.read_po(f)

                for entry in example_po:
                    if entry.id and entry.string:
                        examples.append((entry.id, entry.string))
                self.logger.info(
                    f"Loaded {len(examples)} examples for [{lang}].\n")
            except Exception as e:
                self.logger.warning(
                    f"Warning: Error reading example PO file "
                    f"for [{lang}]: {e}\n")
                examples = []

        return examples

    def load_fixed_examples(self, lang_code, example_dir,
                            fixed_example_json, example_url, example_file):
        """Load fixed translation examples from JSON, with PO fallback.

        Tries to load curated examples from a JSON file first.
        Falls back to the top 2 entries from a PO file on failure.

        Args:
            lang_code: Language code to process.
            example_dir: Root directory for example files.
            fixed_example_json: Fixed examples JSON filename.
            example_url: Fallback PO download URL template.
            example_file: Fallback PO filename.

        Returns:
            list: List of (msgid, msgstr) tuples.
        """
        example_path = os.path.join(
            example_dir, lang_code, fixed_example_json)

        try:
            with open(example_path, 'r', encoding='utf-8') as f:
                language_examples = json.load(f)

            if language_examples:
                self.logger.info(
                    f"Loaded {len(language_examples)} fixed examples "
                    f"from '{example_path}'.")
                return [
                    (ex['msgid'], ex['msgstr'])
                    for ex in language_examples
                ]

        except FileNotFoundError:
            self.logger.info(
                f"'{example_path}' not found. Attempting fallback.")
        except Exception as e:
            self.logger.warning(
                f"WARNING: Error loading '{example_path}': {e}.")

        self.logger.info(
            f"Loading default examples (top 2) from "
            f"'{example_file}' instead.")

        try:
            all_examples = self.load_examples(
                lang_code, example_url, example_file, example_dir)

            if not all_examples:
                self.logger.warning(
                    f"WARNING: Could not load .po examples "
                    f"for [{lang_code}].")
                return []

            num_to_sample = min(len(all_examples), 2)
            example_data = all_examples[:num_to_sample]

            self.logger.info(
                f"Loaded top {len(example_data)} examples from .po file.")
            return example_data

        except Exception as e:
            self.logger.error(f"ERROR: Failed to load .po file: {e}")
            return []

    def save_experiment_log(self, model_name, pot_file, po_file,
                            duration_sec, language, accuracy=None,
                            results_csv_path="./experiments.csv"):
        """Append experiment results to a CSV log file.

        Records translation run metadata including model, duration,
        language, and git information.

        Args:
            model_name: LLM model name used for translation.
            pot_file: Path to the source POT file.
            po_file: Path to the generated PO file.
            duration_sec: Translation duration in seconds.
            language: Target language code.
            accuracy: Optional translation accuracy score.
            results_csv_path: Path to the CSV log file.
        """
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

            self.logger.info(
                f"Experiment log saved to: {results_csv_path}")
        except Exception as e:
            self.logger.warning(
                f"Warning: Failed to save experiment log: {e}")

    @staticmethod
    def is_untranslated(entry):
        """Check whether a PO entry is untranslated.

        Returns True if msgstr (or all msgstr_plural values) are empty.
        """
        if entry.msgid == "":
            return False
        if entry.obsolete:
            return False
        if entry.msgid_plural:
            return not any(
                s.strip() for s in entry.msgstr_plural.values())
        return not bool(entry.msgstr.strip())
