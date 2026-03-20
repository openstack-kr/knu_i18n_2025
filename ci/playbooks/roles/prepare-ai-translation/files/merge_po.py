#!/usr/bin/env python3
"""Merge AI-translated PO files with original PO or POT templates.

Inserts AI translations into untranslated entries of the original
PO file, preserving existing human translations.
"""
import os
import argparse

import polib

from utils import logger, load_config, get_modulename


class POMerger:
    @staticmethod
    def find_original_po(repo_dir, modulename, lang):
        """Return path to the original PO file in the repo, or None."""
        path = os.path.join(
            repo_dir, modulename, "locale", lang,
            "LC_MESSAGES", f"{modulename}.po")
        return path if os.path.isfile(path) else None

    @staticmethod
    def is_untranslated(entry):
        """Check whether a PO entry is untranslated.

        Returns:
            True if msgstr (or all msgstr_plural values) are empty.
        """
        if entry.msgid == "" or entry.obsolete:
            return False
        if entry.msgid_plural:
            return not any(
                s.strip() for s in entry.msgstr_plural.values())
        return not bool(entry.msgstr.strip())

    def merge(self, modulename, repo_dir, lang, model,
              pot_dir, po_dir, output_dir):
        """Merge AI translations into the original PO for one language.

        If the original PO file exists in the repo, uses it as the base.
        Otherwise falls back to the POT template.
        Only untranslated entries are filled with AI translations.
        """
        original_po_path = POMerger.find_original_po(
            repo_dir, modulename, lang)

        if original_po_path:
            logger.info(
                f"[{lang}] Using original .po from repo: {original_po_path}")
        else:
            original_po_path = os.path.join(
                pot_dir, f"current_{modulename}.pot")
            if not os.path.isfile(original_po_path):
                logger.error(
                    f"[{lang}] Neither original .po nor .pot found. Skipping.")
                return
            logger.info(
                f"[{lang}] No original .po; "
                f"using .pot as template: {original_po_path}")

        original_po = polib.pofile(original_po_path)
        llm_path = os.path.join(po_dir, model, lang, f"{modulename}.po")

        if not os.path.isfile(llm_path):
            logger.error(f"[{lang}] Translated PO not found at {llm_path}")
            return

        llm_dict = {e.msgid: e for e in polib.pofile(llm_path)}
        original_ids = {entry.msgid for entry in original_po}
        out_path = os.path.join(output_dir, lang, f"{modulename}.po")

        # Update existing untranslated entries
        updated_count = 0
        logger.info(f"[{lang}] Comparing entries for merge...")

        for entry in original_po:
            llm_entry = llm_dict.get(entry.msgid)
            if (llm_entry and self.is_untranslated(entry)
                    and llm_entry.msgstr.strip()):
                logger.info(
                    f"[{lang}] msgid: {entry.msgid}\n"
                    f"  before: {entry.msgstr}\n"
                    f"  after:  {llm_entry.msgstr}")

                entry.msgstr = llm_entry.msgstr

                for attr in ('comment', 'tcomment', 'flags', 'occurrences'):
                    val = getattr(llm_entry, attr, None)
                    if val:
                        setattr(entry, attr, val)

                updated_count += 1

        # Add new entries from AI translation not present in original PO
        added_count = 0
        for msgid, llm_entry in llm_dict.items():
            if (msgid and msgid not in original_ids
                    and llm_entry.msgstr.strip()):
                original_po.append(polib.POEntry(
                    msgid=msgid,
                    msgstr=llm_entry.msgstr,
                    occurrences=llm_entry.occurrences,
                    comment=llm_entry.comment,
                    tcomment=llm_entry.tcomment,
                    flags=llm_entry.flags,
                ))
                added_count += 1

        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        original_po.save(out_path)

        logger.info(
            f"[{lang}] {updated_count} entries updated, "
            f"{added_count} new entries added. Output: {out_path}")


def get_args():
    parser = argparse.ArgumentParser(
        description="Merge AI-translated PO files with originals")
    parser.add_argument(
        "--config", default="config.yaml",
        help="Path to config YAML file (default: config.yaml)")
    return parser.parse_args()


def main():
    config = load_config(get_args().config)
    project_dir = config['project']['dir']
    modulename = get_modulename(project_dir, config['project']['name'])
    merger = POMerger()

    for lang in config['languages']:
        merger.merge(
            modulename=modulename,
            repo_dir=project_dir,
            lang=lang,
            model=config['ai']['model'],
            pot_dir=config['paths']['pot_dir'],
            po_dir=config['paths']['po_dir'],
            output_dir=config['paths']['output_dir'],
        )


if __name__ == "__main__":
    main()
