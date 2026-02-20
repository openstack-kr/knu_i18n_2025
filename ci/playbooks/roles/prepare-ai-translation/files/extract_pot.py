#!/usr/bin/env python3
"""
POT extraction utilities using pybabel Python API.
Extracts translatable strings from Python source code.
"""
import os
from babel.messages.extract import extract_from_dir, DEFAULT_KEYWORDS
from babel.messages import pofile, Catalog


class PotExtractor:
    """POT file extraction using pybabel Python API."""

    def __init__(self, utils):
        self.utils = utils
        self.logger = self.utils.logger

    def extract(self, output_file, run_dir, project_name, scan_target):
        """
        Extract translatable strings from source code and write a POT file.

        Args:
            output_file: Path to output .pot file
            run_dir: Working directory (project root)
            project_name: OpenStack project name
            scan_target: Directory to scan for translatable strings
        """
        keywords = dict(DEFAULT_KEYWORDS)
        keywords['_C'] = ((1, 'c'), 2)  # context=arg1, msgid=arg2
        keywords['_P'] = (1, 2)         # msgid=arg1, msgid_plural=arg2

        catalog = Catalog(
            project=project_name,
            msgid_bugs_address="https://bugs.launchpad.net/openstack-i18n/",
            charset='UTF-8'
        )

        scan_path = os.path.join(run_dir, scan_target)

        self.logger.info(
            f"[pybabel] Extracting strings from '{scan_target}' -> "
            f"{os.path.basename(output_file)}..."
        )

        for filename, lineno, message, comments, context in extract_from_dir(
            scan_path,
            comment_tags=['Translators:'],
            keywords=keywords,
            strip_comment_tags=True,
        ):
            catalog.add(
                message,
                locations=[(filename, lineno)],
                auto_comments=comments,
                context=context,
            )

        with open(output_file, 'wb') as f:
            pofile.write_po(f, catalog)
