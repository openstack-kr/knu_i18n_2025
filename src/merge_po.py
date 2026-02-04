#!/usr/bin/env python3
import polib
import os
import configparser
import re
from config_loader import load_config
from utils import is_untranslated
import argparse


def get_modulename(repo_dir, project):
    """commit_diff.py와 동일한 로직: setup.cfg / pyproject.toml에서 폴더명 조회"""
    setup_cfg = os.path.join(repo_dir, "setup.cfg")
    if os.path.isfile(setup_cfg):
        parser = configparser.ConfigParser()
        parser.read(setup_cfg)
        if parser.has_option("openstack_translations", "python_modules"):
            modules = [m.strip() for m in
                       parser.get("openstack_translations", "python_modules").split("\n")
                       if m.strip()]
            if modules:
                return modules[0]
        if parser.has_option("files", "packages"):
            modules = [m.strip() for m in
                       parser.get("files", "packages").split("\n")
                       if m.strip()]
            if modules:
                return modules[0]

    pyproject = os.path.join(repo_dir, "pyproject.toml")
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


def find_original_po(repo_dir, modulename, lang):
    """ci 모드: cloned repo 안에서 원본 .po 경로를 조회.
    없으면 None 반환 → 호출측에서 .pot fallback 처리"""
    candidate = os.path.join(repo_dir, modulename, "locale", lang, "LC_MESSAGES", f"{modulename}.po")
    if os.path.isfile(candidate):
        return candidate
    return None


arg_parser = argparse.ArgumentParser()
arg_parser.add_argument(
    "--config",
    default="config.yaml",
    help="Path to config YAML (default: config.yaml)",
)
arg_parser.add_argument(
    "--repo-dir",
    default=None,
    help="(CI mode) path to cloned repo. 원본 .po를 여기서 조회",
)

args = arg_parser.parse_args()
cfg = load_config(args.config)
files_cfg = cfg.get("files", {})
model = cfg["llm"]["model"]

for lang in cfg["languages"]:

    target_file = files_cfg["target_file"]
    target_file_name, _ = os.path.splitext(target_file)

    if args.repo_dir:
        # --- CI 모드: cloned repo에서 원본 .po 조회 ---
        project = cfg["project"]
        modulename = get_modulename(args.repo_dir, project)
        original_po_path = find_original_po(args.repo_dir, modulename, lang)

        if original_po_path:
            target_file_path = original_po_path
            print(f"[merge_po] Using original .po from repo: {target_file_path}")
        else:
            # 원본 .po 없음 (해당 언어 번역 미시작) → .pot을 기본 템플릿으로 사용
            target_file_path = os.path.join("./pot", f"{target_file_name}.pot")
            if not os.path.isfile(target_file_path):
                print(f"[merge_po] ERROR: neither original .po nor .pot found for {lang}. skipping.")
                continue
            print(f"[merge_po] No original .po for {lang}; using .pot as template: {target_file_path}")
    else:
        # --- local 모드: 기존 동작 유지 ---
        target_file_path = os.path.join(f"./data/target/{lang}", target_file)
    # PO 파일 로드
    target_file = polib.pofile(target_file_path)
    llm_path = f"./po/{model}/{lang}/{target_file_name}.po"
    llm = polib.pofile(llm_path)
    out_path = f"./data/result/{lang}/{target_file_name}.po"
    
    # standard_po 헤더(metadata) 백업
    original_metadata = target_file.metadata.copy()

    # LLM_PO에서 msgid -> POEntry 매핑
    llm_dict = {entry.msgid: entry for entry in llm}

    updated_count = 0
    print(f"[Lang: {lang}] [*] 번역 삽입 전/후 비교:")

    for entry in target_file:
        if entry.msgid in llm_dict:
            llm_entry = llm_dict[entry.msgid]

            # standard_po에 이미 번역이 있으면 덮어쓰지 않음
            if is_untranslated(entry) and llm_entry.msgstr.strip():
                print(f"[Lang: {lang}]\n--- msgid: {entry.msgid}")
                print(f"[Lang: {lang}]- before: {entry.msgstr}")
                print(f"[Lang: {lang}]+ after : {llm_entry.msgstr}")

                # msgstr 갱신
                entry.msgstr = llm_entry.msgstr

                # comment, tcomment, flags, previous comments 유지
                if hasattr(llm_entry, 'comment') and llm_entry.comment:
                    entry.comment = llm_entry.comment
                if hasattr(llm_entry, 'tcomment') and llm_entry.tcomment:
                    entry.tcomment = llm_entry.tcomment
                if hasattr(llm_entry, 'flags') and llm_entry.flags:
                    entry.flags = llm_entry.flags

                if hasattr(llm_entry, 'references') and llm_entry.references:
                    entry.references = llm_entry.references

                updated_count += 1

    # 저장 전에 헤더 복원
    target_file.metadata = original_metadata

    # 결과 저장
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    target_file.save(out_path)

    print(f"[Lang: {lang}]\n[+] 총 {updated_count}개 항목이 업데이트되었습니다.")
    print(f"[Lang: {lang}][+] 결과 파일: {out_path}")
