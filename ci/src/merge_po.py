#!/usr/bin/env python3
import polib
import os
from utils import is_untranslated, get_modulename
import argparse


def find_original_po(repo_dir, modulename, lang):
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project",
        required=True,
        help="OpenStack project name")
    parser.add_argument(
        "--repo-dir",
        required=True,
        help="Path to cloned repo. 원본 .po를 여기서 조회")
    parser.add_argument(
        "--lang",
        required=True,
        help="Language code (e.g., ko_KR, ja)")

    args = parser.parse_args()

    # Hardcoded model name for CI
    model = "llama3.2:3b"
    lang = args.lang

    # --- CI 모드: modulename이 파일명 키 ---
    modulename = get_modulename(args.repo_dir, args.project)
    target_file_name = modulename
    original_po_path = find_original_po(
        args.repo_dir, modulename, lang)

    if original_po_path:
        target_file_path = original_po_path
        print(
            "[merge_po] Using original .po from repo: "
            f"{target_file_path}")
    else:
        # 원본 .po 없음 (해당 언어 번역 미시작) → .pot을 기본 템플릿으로 사용
        target_file_path = os.path.join("./pot", f"{modulename}.pot")
        if not os.path.isfile(target_file_path):
            print(
                "[merge_po] ERROR: neither original .po nor .pot "
                f"found for {lang}. exiting.")
            return
        print(
            f"[merge_po] No original .po for {lang}; "
            f"using .pot as template: {target_file_path}")

    # PO 파일 로드
    original_po = polib.pofile(target_file_path)
    llm_path = f"./po/{model}/{lang}/{target_file_name}.po"
    llm = polib.pofile(llm_path)
    out_path = f"./data/result/{lang}/{target_file_name}.po"

    # 헤더(metadata) 백업
    original_metadata = original_po.metadata.copy()

    # LLM_PO에서 msgid -> POEntry 매핑
    llm_dict = {entry.msgid: entry for entry in llm}

    updated_count = 0
    print(f"[Lang: {lang}] [*] 번역 삽입 전/후 비교:")

    for entry in original_po:
        if entry.msgid in llm_dict:
            llm_entry = llm_dict[entry.msgid]

            # 이미 번역이 있으면 덮어쓰지 않음
            if is_untranslated(entry) and llm_entry.msgstr.strip():
                print(f"[Lang: {lang}]\n--- msgid: {entry.msgid}")
                print(f"[Lang: {lang}]- before: {entry.msgstr}")
                print(f"[Lang: {lang}]+ after : {llm_entry.msgstr}")

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

    print(f"[Lang: {lang}]\n[+] 총 {updated_count}개 항목이 업데이트되었습니다.")
    print(f"[Lang: {lang}][+] 결과 파일: {out_path}")


if __name__ == "__main__":
    main()
