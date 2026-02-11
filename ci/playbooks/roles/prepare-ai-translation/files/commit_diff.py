#!/usr/bin/env python3
"""
Detects translation changes between git commits.
Extracts new/modified msgid entries for incremental translation.
"""
import os
import subprocess
import argparse

from extract_pot import PotExtractor
from utils import TranslationUtils


class CommitDiffExtractor:
    """Git 커밋 간의 번역 변경 사항을 추출하는 클래스"""

    def __init__(self, utils: TranslationUtils, repo_dir: str, pot_dir: str):
        self.utils = utils
        self.repo_dir = repo_dir
        self.pot_dir = pot_dir
        self.logger = self.utils.logger
        self.pot_extractor = PotExtractor(self.utils)

    def run_git(self, args, cwd=None):
        """Run git command in specified directory."""
        subprocess.check_call(["git"] + args, cwd=cwd)

    def extract_diff(self, project: str, pot_file: str):
        """
        HEAD와 HEAD~1 커밋 간의 POT 파일을 추출하고 비교하여
        새롭거나 변경된 msgid를 추출합니다.
        """
        os.makedirs(self.pot_dir, exist_ok=True)

        # utils 객체를 사용하여 소스 디렉토리 판별
        source_dir = self.utils.get_modulename(project)

        # diff_pot 파일명은 modulename 기준 (translate, merge_po와 연결 키)
        target_file_name = source_dir

        # HEAD, HEAD~1 각각의 short hash를 tmp pot 파일명에 사용
        current_head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.repo_dir
        ).decode().strip()
        base_head = subprocess.check_output(
            ["git", "rev-parse", "HEAD~1"], cwd=self.repo_dir
        ).decode().strip()
        
        new_short = current_head[:8]
        old_short = base_head[:8]

        new_pot = os.path.abspath(os.path.join(self.pot_dir, f"HEAD_{target_file_name}.pot"))
        old_pot = os.path.abspath(os.path.join(self.pot_dir, f"HEAD~1_{target_file_name}.pot"))
        diff_pot = os.path.abspath(os.path.join(self.pot_dir, pot_file))

        try:
            # 1. Extract POT from HEAD (current commit)
            self.logger.info(f"\n[1/3] Checkout Target: HEAD ({new_short})")
            self.run_git(["checkout", "HEAD"], cwd=self.repo_dir)
            self.pot_extractor.run_pybabel_extract(new_pot, self.repo_dir, project, source_dir)

            # 2. Extract POT from HEAD~1 (base commit)
            self.logger.info(f"\n[2/3] Checkout Base: HEAD~1 ({old_short})")
            self.run_git(["checkout", "HEAD~1"], cwd=self.repo_dir)
            self.pot_extractor.run_pybabel_extract(old_pot, self.repo_dir, project, source_dir)

        finally:
            # Restore to original HEAD
            self.logger.info(f"\n[*] Restoring HEAD to {current_head}")
            self.run_git(["checkout", current_head], cwd=self.repo_dir)

        # 3. Compare and extract diff
        self.logger.info(f"\n[3/3] Extracting new/modified entries...")
        count = self.pot_extractor.compare_pot_files(new_pot, old_pot, diff_pot)

        if count > 0:
            self.logger.info(f"\n[SUCCESS] Generated {diff_pot} with {count} new entries.")
        else:
            self.logger.info("\n[INFO] No translation changes found between commits.")


def get_args():
    """
    Ansible `tasks/main.yaml`에서 넘겨주는 인자들을 파싱합니다.
    기본값은 Ansible `defaults`에 위임하고, 수신 여부와 타입만 지정합니다.
    """
    parser = argparse.ArgumentParser(description="Extract msgid from commit diff")
    
    # 필수 인자 (Ansible에서 주입)
    parser.add_argument("--repo-dir", required=True, help="Path to cloned repo")
    
    # Ansible 구조에 맞춰 선택적으로 받을 수 있는 인자들
    parser.add_argument("--project", default="unknown_project", help="OpenStack project name (Fallback if setup.cfg parsing fails)")
    parser.add_argument("--pot_dir", default="./pot", help="Directory to save extracted POT files")
    parser.add_argument("--pot_file", required=True, help="Final diff POT filename")

    return parser.parse_args()


def main():
    args = get_args()

    # utils 초기화
    utils = TranslationUtils(args.repo_dir)
    
    # Extractor 초기화 및 실행
    extractor = CommitDiffExtractor(utils, args.repo_dir, args.pot_dir)
    extractor.extract_diff(args.project, args.pot_file)


if __name__ == "__main__":
    main()