"""Shared utilities for the AI translation pipeline."""
import os
import configparser
import re
import logging

import yaml


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
