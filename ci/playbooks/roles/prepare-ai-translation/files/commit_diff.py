#!/usr/bin/env python3
"""Compare two POT files and extract new/modified msgid entries.

Receives POT files generated from HEAD and HEAD~1 (extracted by the
playbook) and writes only the new/modified entries to the output POT file.
"""
import os
import argparse

from babel.messages import pofile, Catalog
from utils import logger, load_config


class CommitDiffer:
    def compare(self, new_pot, old_pot, output_diff):
        """Compare two POT files and extract only new/added msgid entries.

        Args:
            new_pot: Path to newer POT file (e.g., current_xxx.pot)
            old_pot: Path to older POT file (e.g., previous_xxx.pot)
            output_diff: Path to output diff POT file

        Returns:
            Number of new entries found
        """
        logger.info("Comparing POT files...")

        try:
            with open(new_pot, 'rb') as f:
                new_cat = pofile.read_po(f)
            with open(old_pot, 'rb') as f:
                old_cat = pofile.read_po(f)
        except FileNotFoundError as e:
            logger.error(f"Could not find POT file to compare: {e}")
            return 0

        old_ids = {entry.id for entry in old_cat if entry.id}

        diff_cat = Catalog(
            project=new_cat.project,
            version=new_cat.version,
            msgid_bugs_address=new_cat.msgid_bugs_address,
            copyright_holder=new_cat.copyright_holder,
            charset='UTF-8'
        )

        count = 0
        for entry in new_cat:
            if entry.id and entry.id not in old_ids:
                diff_cat.add(
                    entry.id,
                    entry.string,
                    locations=entry.locations,
                    flags=entry.flags,
                    user_comments=entry.user_comments,
                    auto_comments=entry.auto_comments
                )
                count += 1

        try:
            with open(output_diff, 'wb') as f:
                pofile.write_po(f, diff_cat)
        except Exception as e:
            logger.error(f"Failed to write diff POT file: {e}")
            return 0

        return count


def get_args():
    parser = argparse.ArgumentParser(
        description="Extract new/modified msgid entries from commit diff")
    parser.add_argument(
        "--config", default="config.yaml",
        help="Path to config YAML file (default: config.yaml)")
    parser.add_argument(
        "--new-pot", required=True,
        help="Path to POT file extracted from HEAD")
    parser.add_argument(
        "--old-pot", required=True,
        help="Path to POT file extracted from HEAD~1")
    return parser.parse_args()


def main():
    args = get_args()
    config = load_config(args.config)

    pot_dir = config['paths']['pot_dir']
    pot_file = config['files']['pot_file']

    diff_pot = os.path.join(pot_dir, pot_file)

    differ = CommitDiffer()
    count = differ.compare(args.new_pot, args.old_pot, diff_pot)

    if count > 0:
        logger.info(
            f"[SUCCESS] Generated {diff_pot} with {count} new entries.")
    else:
        logger.info("No translation changes found between commits.")


if __name__ == "__main__":
    main()
