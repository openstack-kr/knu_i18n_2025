import os
import subprocess
import argparse
from babel.messages import pofile, Catalog
from utils import load_config, get_modulename


def run_git(args, cwd=None):
    subprocess.check_call(["git"] + args, cwd=cwd)


def run_pybabel(output_file, run_dir, project_name, scan_target):
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
        f"Running pybabel on '{scan_target}' -> "
        f"{os.path.basename(output_file)}...")
    subprocess.check_call(cmd, cwd=run_dir)


def extract_diff(new_pot, old_pot, output_diff):
    print("Comparing New vs Old POT...")
    try:
        with open(new_pot, 'rb') as f:
            new_cat = pofile.read_po(f)
        with open(old_pot, 'rb') as f:
            old_cat = pofile.read_po(f)
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

    with open(output_diff, 'wb') as f:
        pofile.write_po(f, diff_cat)
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument(
        "--repo-dir",
        required=True,
        help="path to already cloned repo (managed by ci.sh)")
    args = parser.parse_args()

    cfg = load_config(args.config)

    project = cfg["project"]
    repo_dir = args.repo_dir

    pot_dir = "./pot"
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
