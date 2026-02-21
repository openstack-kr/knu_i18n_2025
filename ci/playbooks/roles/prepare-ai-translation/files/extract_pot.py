#!/usr/bin/env python3
"""Extract translatable strings from Python source code into a POT file.

Uses the pybabel Python API to scan the project source directory and
write a catalog of translatable strings to the specified output file.
"""
import os
import argparse

from babel.messages.extract import extract_from_dir, DEFAULT_KEYWORDS
from babel.messages import pofile, Catalog

from utils import logger, load_config, get_modulename


class PotExtractor:
    def extract(self, output_file, run_dir, project_name, scan_target):
        """Extract translatable strings from source code and write a POT file.

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

        logger.info(
            f"Extracting strings from '{scan_target}' -> "
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


def get_args():
    parser = argparse.ArgumentParser(
        description="Extract translatable strings from source code to POT"
    )
    parser.add_argument(
        "--config", default="config.yaml",
        help="Path to config YAML file (default: config.yaml)")
    parser.add_argument(
        "--output", required=True,
        help="Path to output .pot file")
    return parser.parse_args()


def main():
    args = get_args()
    config = load_config(args.config)

    project_name = config['project']['name']
    project_dir = config['project']['dir']

    source_dir = get_modulename(project_dir, project_name)

    extractor = PotExtractor()
    extractor.extract(args.output, project_dir, project_name, source_dir)


if __name__ == "__main__":
    main()
