import os
import subprocess
import argparse
import configparser
import re
from babel.messages import pofile, Catalog
from config_loader import load_config

def get_modulename(repo_dir, project):
    """
    project명과 project 폴더명이 불일치 하는 경우가 있다.
    setup.cfg / pyproject.toml에서 pybabel 스캔할 폴더명을 조회한다.

    우선순위 (upstream get-modulename.py와 동일, pyproject.toml 추가):
      1. setup.cfg  [openstack_translations] python_modules
      2. setup.cfg  [files] packages
      3. pyproject.toml [tool.setuptools] packages
      4. fallback: project name 그대로
    """
    # --- setup.cfg ---
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

    # --- pyproject.toml ---
    # [tool.setuptools] packages = ["pkg_a", "pkg_b", ...]
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

def run_git(args, cwd=None):
    subprocess.check_call(["git"] + args, cwd=cwd)

def run_pybabel(output_file, run_dir, project_name, scan_target):
    cmd = [
        "pybabel", "--quiet", "extract",
        "--add-comments", "Translators:",
        f"--msgid-bugs-address=https://bugs.launchpad.net/openstack-i18n/",
        f"--project={project_name}",
        "--version=",
        "-k", "_C:1c,2",
        "-k", "_P:1,2",
        "-o", output_file,
        scan_target
    ]
    print(f"Running pybabel on '{scan_target}' -> {os.path.basename(output_file)}...")
    subprocess.check_call(cmd, cwd=run_dir)

def extract_diff(new_pot, old_pot, output_diff):
    print(f"Comparing New vs Old POT...")
    try:
        with open(new_pot, 'rb') as f: new_cat = pofile.read_po(f)
        with open(old_pot, 'rb') as f: old_cat = pofile.read_po(f)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
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

    with open(output_diff, 'wb') as f: pofile.write_po(f, diff_cat)
    return count

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--repo-dir", required=True, help="path to already cloned repo (managed by ci.sh)")
    args = parser.parse_args()

    cfg = load_config(args.config)

    project = cfg["project"]
    repo_dir = args.repo_dir

    pot_dir = "./pot"
    source_dir = get_modulename(repo_dir, project)

    # target_file 기준으로 pot 저장 위함
    target_file = cfg['files']["target_file"]
    target_file_name, _ = os.path.splitext(target_file)

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
    diff_pot = os.path.abspath(os.path.join(pot_dir, f"{target_file_name}.pot"))

    try:
        # 1. New POT 생성 (HEAD)
        print(f"Checkout Target: HEAD ({new_short})")
        run_git(["checkout", "HEAD"], cwd=repo_dir)
        run_pybabel(new_pot, repo_dir, project, source_dir)

        # 2. Old POT 생성 (HEAD~1)
        print(f"Checkout Base: HEAD~1 ({old_short})")
        run_git(["checkout", "HEAD~1"], cwd=repo_dir)
        run_pybabel(old_pot, repo_dir, project, source_dir)

    finally:
        # 복구
        print(f"Restoring HEAD to {current_head}")
        run_git(["checkout", current_head], cwd=repo_dir)

    # 3. 결과 추출
    count = extract_diff(new_pot, old_pot, diff_pot)

    if count > 0:
        print(f"\nGenerated {diff_pot} with {count} new messages.")
    else:
        print("\nNo translation changes found between these commits.")

if __name__ == "__main__":
    main()