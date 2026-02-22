"""Shared utilities for the AI translation pipeline.

Provides configuration loading, logging setup, module name resolution,
glossary/example loading, and experiment logging used across scripts.
"""
import os
import json
import csv
import subprocess
import configparser
import re
import logging
from datetime import datetime

import requests
import yaml
from babel.messages import pofile


logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


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


def get_modulename(project_dir, project):
    """Resolve the actual Python module directory name for a project.

    The project name and source directory may differ.
    Looks up the scan target in setup.cfg / pyproject.toml.

    Priority (matches upstream get-modulename.py):
      1. setup.cfg  [openstack_translations] python_modules
      2. setup.cfg  [files] packages
      3. pyproject.toml [tool.setuptools] packages
      4. Fallback: project name as-is
    """
    setup_cfg = os.path.join(project_dir, "setup.cfg")
    if os.path.isfile(setup_cfg):
        parser = configparser.ConfigParser()
        parser.read(setup_cfg)

        for section, option in [
            ("openstack_translations", "python_modules"),
            ("files", "packages"),
        ]:
            if parser.has_option(section, option):
                modules = [m.strip() for m in
                           parser.get(section, option).split("\n")
                           if m.strip()]
                if modules:
                    return modules[0]

    pyproject = os.path.join(project_dir, "pyproject.toml")
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


def save_experiment_log(model_name, pot_file, po_file,
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
    def _run_git(*args):
        try:
            return subprocess.check_output(
                ["git", *args], stderr=subprocess.DEVNULL
            ).decode().strip()
        except Exception:
            return None

    git_commit = _run_git("rev-parse", "HEAD")
    git_branch = _run_git("rev-parse", "--abbrev-ref", "HEAD")

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
            writer = csv.DictWriter(
                csvfile, fieldnames=list(result_entry.keys()))

            if not file_exists:
                writer.writeheader()
            writer.writerow(result_entry)

        logger.info(f"Experiment log saved to: {results_csv_path}")
    except Exception as e:
        logger.warning(f"Failed to save experiment log: {e}")


class ResourceLoader:
    def __init__(self, glossary_url=None, prompt_dir=None):
        self.glossary_url = glossary_url
        self.prompt_dir = prompt_dir

    def _download_file(self, url, dest_path, label):
        """Download a file from URL and save to dest_path.

        Args:
            url: URL to download from.
            dest_path: Local path to save the downloaded file.
            label: Human-readable description used in log messages.

        Returns:
            bool: True on success, False on failure.
        """
        logger.info(f"Downloading {label} from {url}...")
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            with open(dest_path, "wb") as f:
                f.write(response.content)
            logger.info(
                f"Successfully downloaded and saved to {dest_path}")
            return True
        except requests.exceptions.RequestException as e:
            logger.warning(f"Could not download {label}: {e}")
            return False

    def load_support_prompt(self, language_code):
        """Load a language-specific custom prompt if available."""
        if not self.prompt_dir:
            return None
        prompt_path = os.path.join(self.prompt_dir, f"{language_code}.txt")
        if os.path.isfile(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        return None

    def load_glossary(self, lang, glossary_dir,
                      glossary_po_file="glossary.po"):
        """Download/load a glossary PO file.

        Args:
            lang: Language code to process.
            glossary_dir: Root directory for glossary files.
            glossary_po_file: Glossary PO filename.

        Returns:
            dict: Glossary mapping (English term -> translated term).
        """
        lang_dir = os.path.join(glossary_dir, lang)
        os.makedirs(lang_dir, exist_ok=True)

        glossary_po_path = os.path.join(lang_dir, glossary_po_file)

        if not os.path.exists(glossary_po_path):
            if not self._download_file(
                    self.glossary_url.format(lang=lang),
                    glossary_po_path,
                    f"glossary for [{lang}]"):
                return {}

        logger.info(f"Building glossary for [{lang}]...")
        try:
            with open(glossary_po_path, "rb") as f:
                glossary_po = pofile.read_po(f)
            glossary = {
                entry.id.strip().lower(): entry.string.strip()
                for entry in glossary_po
                if entry.id and entry.string
            }
            logger.info(
                f"Glossary for [{lang}] loaded "
                f"with {len(glossary)} terms.")
            return glossary
        except Exception as e:
            logger.error(
                f"Error reading Glossary PO file for [{lang}]: {e}")
            return {}

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
        if not url_template:
            return []

        lang_dir = os.path.join(example_dir, lang)
        os.makedirs(lang_dir, exist_ok=True)

        example_path = os.path.join(lang_dir, example_file)

        if not os.path.exists(example_path):
            if not self._download_file(
                    url_template.format(lang=lang),
                    example_path,
                    f"examples for [{lang}]"):
                return []

        logger.info(
            f"Loading few-shot examples from "
            f"{os.path.basename(example_path)} for [{lang}]...")
        try:
            with open(example_path, "rb") as f:
                example_po = pofile.read_po(f)
            examples = [
                (entry.id, entry.string)
                for entry in example_po
                if entry.id and entry.string
            ]
            logger.info(
                f"Loaded {len(examples)} examples for [{lang}].")
            return examples
        except Exception as e:
            logger.warning(
                f"Error reading example PO file for [{lang}]: {e}")
            return []

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
                logger.info(
                    f"Loaded {len(language_examples)} fixed examples "
                    f"from '{example_path}'.")
                return [
                    (ex['msgid'], ex['msgstr'])
                    for ex in language_examples
                ]

        except FileNotFoundError:
            logger.warning(
                f"'{example_path}' not found. Attempting fallback.")
        except Exception as e:
            logger.warning(f"Error loading '{example_path}': {e}")

        logger.info(
            f"Loading default examples (top 2) from "
            f"'{example_file}' instead.")
        return self.load_examples(
            lang_code, example_url, example_file, example_dir)[:2]
