#!/usr/bin/env python3
"""
POT extraction utilities using pybabel.
Extracts translatable strings from Python source code.
"""
import os
import subprocess
from babel.messages import pofile, Catalog


def run_pybabel_extract(output_file, run_dir, project_name, scan_target):
    """
    Run pybabel extract command to generate POT file from source code.

    Args:
        output_file: Path to output .pot file
        run_dir: Working directory to run pybabel in
        project_name: OpenStack project name
        scan_target: Directory to scan for translatable strings
    """
    cmd = [
        "pybabel", "--quiet", "extract",
        "--add-comments", "Translators:",
        ("--msgid-bugs-address="
         "https://bugs.launchpad.net/openstack-i18n/"),
        f"--project={project_name}",
        "--version=",
        "-k", "_C:1c,2",
        "-k", "_P:1,2",
        "-o", output_file,
        scan_target
    ]
    print(
        f"[pybabel] Extracting strings from '{scan_target}' -> "
        f"{os.path.basename(output_file)}...")
    subprocess.check_call(cmd, cwd=run_dir)


def compare_pot_files(new_pot, old_pot, output_diff):
    """
    Compare two POT files and extract only new/added msgid entries.

    Args:
        new_pot: Path to newer POT file (e.g., HEAD)
        old_pot: Path to older POT file (e.g., HEAD~1)
        output_diff: Path to output diff POT file

    Returns:
        Number of new entries found
    """
    print("[pybabel] Comparing new vs old POT files...")
    try:
        with open(new_pot, 'rb') as f:
            new_cat = pofile.read_po(f)
        with open(old_pot, 'rb') as f:
            old_cat = pofile.read_po(f)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        return 0

    # Build set of old msgid entries
    old_ids = {entry.id for entry in old_cat if entry.id}

    # Create new catalog with only new entries
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

    # Write diff catalog to file
    with open(output_diff, 'wb') as f:
        pofile.write_po(f, diff_cat)

    return count
