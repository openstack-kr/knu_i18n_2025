#!/usr/bin/env python3
"""
Detects translation changes between git commits.
Extracts new/modified msgid entries for incremental translation.
"""
import os
import subprocess
import argparse
from utils import get_modulename
from extract_pot import run_pybabel_extract, compare_pot_files


def run_git(args, cwd=None):
    """Run git command in specified directory."""
    subprocess.check_call(["git"] + args, cwd=cwd)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project",
        required=True,
        help="OpenStack project name")
    parser.add_argument(
        "--repo-dir",
        required=True,
        help="path to already cloned repo (managed by ci.sh)")
    args = parser.parse_args()

    project = args.project
    repo_dir = args.repo_dir

    pot_dir = "./pot"
    os.makedirs(pot_dir, exist_ok=True)

    source_dir = get_modulename(repo_dir, project)

    # diff_pot 파일명은 modulename 기준 (translate, merge_po와 연결 키)
    target_file_name = source_dir

    # HEAD, HEAD~1 각각의 short hash를 tmp pot 파일명에 사용
    current_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo_dir
    ).decode().strip()
    base_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD~1"], cwd=repo_dir
    ).decode().strip()
    new_short = current_head[:8]
    old_short = base_head[:8]

    new_pot = os.path.abspath(os.path.join(pot_dir, f"HEAD_{new_short}.pot"))
    old_pot = os.path.abspath(os.path.join(pot_dir, f"HEAD~1_{old_short}.pot"))
    diff_pot = os.path.abspath(
        os.path.join(
            pot_dir,
            f"{target_file_name}.pot"))

    try:
        # 1. Extract POT from HEAD (current commit)
        print(f"\n[1/3] Checkout Target: HEAD ({new_short})")
        run_git(["checkout", "HEAD"], cwd=repo_dir)
        run_pybabel_extract(new_pot, repo_dir, project, source_dir)

        # 2. Extract POT from HEAD~1 (base commit)
        print(f"\n[2/3] Checkout Base: HEAD~1 ({old_short})")
        run_git(["checkout", "HEAD~1"], cwd=repo_dir)
        run_pybabel_extract(old_pot, repo_dir, project, source_dir)

    finally:
        # Restore to original HEAD
        print(f"\n[*] Restoring HEAD to {current_head}")
        run_git(["checkout", current_head], cwd=repo_dir)

    # 3. Compare and extract diff
    print(f"\n[3/3] Extracting new/modified entries...")
    count = compare_pot_files(new_pot, old_pot, diff_pot)

    if count > 0:
        print(f"\n[SUCCESS] Generated {diff_pot} with {count} new entries.")
    else:
        print("\n[INFO] No translation changes found between commits.")


if __name__ == "__main__":
    main()
