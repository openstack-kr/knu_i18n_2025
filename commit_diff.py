import os
import subprocess
import shutil
import argparse
from babel.messages import pofile, Catalog
from config_loader import load_config

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
    args = parser.parse_args()

    cfg = load_config(args.config)

    project = cfg["project"]
    
    repo_url = cfg['git']['repo_url'].format(project=project)
    work_dir = cfg['git']['work_dir']
    repo_dir = os.path.join(work_dir, project)
    
    target_commit = cfg['compare']['target_commit']
    base_commit = cfg['compare']['base_commit']

    pot_dir = cfg['files']['pot_dir']
    diff_name = cfg['files']['target_pot'].format(project=project)
    source_dir = cfg['output'].get('source_dir', ".").format(project=project)

    project_name = project

    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(pot_dir, exist_ok=True)

    # 1. Git 저장소 준비
    if os.path.isdir(os.path.join(repo_dir, ".git")):
        print(f"Updating existing repo at {repo_dir}...")
        run_git(["reset", "--hard", "HEAD"], cwd=repo_dir)
        run_git(["checkout", "master"], cwd=repo_dir)
        run_git(["pull"], cwd=repo_dir)
    else:
        print(f"Cloning repo to {repo_dir}...")
        if os.path.exists(repo_dir): shutil.rmtree(repo_dir)
        run_git(["clone", repo_url, repo_dir])

    current_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_dir).decode().strip()

    new_pot = os.path.abspath(os.path.join(pot_dir, f"new_{target_commit}.pot"))
    old_pot = os.path.abspath(os.path.join(pot_dir, f"old_{target_commit}.pot"))
    diff_pot = os.path.abspath(os.path.join(pot_dir, diff_name))

    try:
        # 2. New POT 생성 (Target Commit)
        print(f"Checkout Target: {target_commit}")
        run_git(["checkout", target_commit], cwd=repo_dir)
        run_pybabel(new_pot, repo_dir, project_name, source_dir)

        # 3. Old POT 생성 (Base Commit)
        print(f"Checkout Base: {base_commit}")
        run_git(["checkout", base_commit], cwd=repo_dir)
        run_pybabel(old_pot, repo_dir, project_name, source_dir)

    finally:
        # 4. 복구
        print(f"Restoring HEAD to {current_head}")
        run_git(["checkout", current_head], cwd=repo_dir)

    # 5. 결과 추출
    count = extract_diff(new_pot, old_pot, diff_pot)

    if count > 0:
        print(f"\nGenerated {diff_pot} with {count} new messages.")
    else:
        print("\nNo translation changes found between these commits.")

if __name__ == "__main__":
    main()