#!/usr/bin/env python3
import polib
import os
import argparse

# utils.py에서 공통 유틸리티 클래스 임포트
from utils import TranslationUtils


class POMerger:
    """AI 번역 결과를 원본 PO 파일 또는 POT 템플릿에 병합하는 클래스"""

    def __init__(self, utils: TranslationUtils):
        self.utils = utils
        self.logger = self.utils.logger

    def find_original_po(self, repo_dir, modulename, lang):
        """ci 모드: cloned repo 안에서 원본 .po 경로를 조회.
        없으면 None 반환 → 호출측에서 .pot fallback 처리"""
        candidate = os.path.join(
            repo_dir,
            modulename,
            "locale",
            lang,
            "LC_MESSAGES",
            f"{modulename}.po")
        if os.path.isfile(candidate):
            return candidate
        return None

    def run_merge(self, project, repo_dir, lang, model, pot_dir, po_dir, output_dir):
        # --- CI 모드: modulename이 파일명 키 ---
        modulename = self.utils.get_modulename(project)
        target_file_name = modulename
        original_po_path = self.find_original_po(repo_dir, modulename, lang)

        if original_po_path:
            target_file_path = original_po_path
            self.logger.info(
                "[merge_po] Using original .po from repo: "
                f"{target_file_path}")
        else:
            # 원본 .po 없음 (해당 언어 번역 미시작) → .pot을 기본 템플릿으로 사용
            target_file_path = os.path.join(pot_dir, f"HEAD_{modulename}.pot")
            if not os.path.isfile(target_file_path):
                self.logger.error(
                    "[merge_po] ERROR: neither original .po nor .pot "
                    f"found for {lang}. exiting.")
                return
            self.logger.info(
                f"[merge_po] No original .po for {lang}; "
                f"using .pot as template: {target_file_path}")

        # PO 파일 로드
        original_po = polib.pofile(target_file_path)
        llm_path = os.path.join(po_dir, model, lang, f"{target_file_name}.po")
        
        # LLM 번역본이 존재하는지 안전 체크 추가
        if not os.path.isfile(llm_path):
            self.logger.error(f"[merge_po] ERROR: Translated PO not found at {llm_path}")
            return
            
        llm = polib.pofile(llm_path)
        out_path = os.path.join(output_dir, lang, f"{target_file_name}.po")

        # 헤더(metadata) 백업
        original_metadata = original_po.metadata.copy()

        # LLM_PO에서 msgid -> POEntry 매핑
        llm_dict = {entry.msgid: entry for entry in llm}

        updated_count = 0
        self.logger.info(f"[Lang: {lang}] [*] 번역 삽입 전/후 비교:")

        for entry in original_po:
            if entry.msgid in llm_dict:
                llm_entry = llm_dict[entry.msgid]

                # 이미 번역이 있으면 덮어쓰지 않음
                if self.utils.is_untranslated(entry) and llm_entry.msgstr.strip():
                    self.logger.info(f"[Lang: {lang}]\n--- msgid: {entry.msgid}")
                    self.logger.info(f"[Lang: {lang}]- before: {entry.msgstr}")
                    self.logger.info(f"[Lang: {lang}]+ after : {llm_entry.msgstr}")

                    entry.msgstr = llm_entry.msgstr

                    for attr in ('comment', 'tcomment', 'flags', 'references'):
                        val = getattr(llm_entry, attr, None)
                        if val:
                            setattr(entry, attr, val)

                    updated_count += 1

        # 헤더 복원
        original_po.metadata = original_metadata

        # 결과 저장
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        original_po.save(out_path)

        self.logger.info(f"[Lang: {lang}]\n[+] 총 {updated_count}개 항목이 업데이트되었습니다.")
        self.logger.info(f"[Lang: {lang}][+] 결과 파일: {out_path}")


def get_args():
    """Ansible에서 명시적으로 넘겨받는 인자들 (default 제거)"""
    parser = argparse.ArgumentParser(description="Merge translated PO files with original or POT template")
    parser.add_argument("--project", required=True, help="OpenStack project name")
    parser.add_argument("--repo-dir", required=True, help="Path to cloned repo. 원본 .po를 여기서 조회")
    
    # Ansible 연동을 위한 인자 추가
    parser.add_argument("--model", required=True, help="LLM model name")
    parser.add_argument("--languages", required=True, help="Comma-separated language codes")
    parser.add_argument("--pot_dir", required=True, help="Directory containing POT files")
    parser.add_argument("--po_dir", required=True, help="Directory containing translated PO files")
    parser.add_argument("--output_dir", required=True, help="Directory to save merged PO files")

    return parser.parse_args()


def main():
    args = get_args()
    
    # Utils 및 Merger 인스턴스 초기화
    utils = TranslationUtils(args.repo_dir)
    merger = POMerger(utils)

    # 문자열로 들어온 언어 목록 파싱 ("ko,ja" -> ["ko", "ja"])
    languages_to_merge = [lang.strip() for lang in args.languages.split(",") if lang.strip()]

    for lang in languages_to_merge:
        merger.run_merge(
            project=args.project,
            repo_dir=args.repo_dir,
            lang=lang,
            model=args.model,
            pot_dir=args.pot_dir,
            po_dir=args.po_dir,
            output_dir=args.output_dir
        )


if __name__ == "__main__":
    main()