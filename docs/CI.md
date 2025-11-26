# CI Configuration & Limitations

This document details the **configuration settings** (config.yaml) required for the **CI / Commit Diff** workflow and outlines **current limitations** regarding automated file fetching and project support.

Unlike the Local workflow which translates a specific `.po` file, this mode analyzes the git history to extract and translate changes.

## 1. Configuration (`config.yaml`)

For common settings like **target file**, **model**, **language**, and **performance settings**, please refer to the [**Choose Your Options**] section in the main `README.md`.

To run the CI workflow, you **must** configure the **`git`** section in `config.yaml`.

### Git Configuration Details

Locate the `git:` section in your `config.yaml`. Here, you specify the target project and the exact commit version you want to translate.

```yaml
# -----------------------------
#  Only for CI
# -----------------------------
git:
  # [1] Target Project Name
  # Used for the POT file header (Project-Id-Version) and folder naming.
  # Example: "nova", "cinder", "horizon"
  project: "nova"

  # [2] Target Commit Hash
  # The specific commit hash you want to translate.
  # The tool calculates the diff by comparing this commit with its parent (HEAD~1).
  # You can find this hash on GitHub.
  target_commit: "d6f5a30caa1a4a139dc67272a150d24e44892a91"

  # [3] Repository URL
  # The git URL to clone the source code from.
  # "{project}" will be automatically replaced by the value of [1].
  repo_url: "https://github.com/openstack/{project}.git"

  # [4] Working Directory
  # The local temporary folder where the source code will be cloned.
  # (Default: "./workspace")
  work_dir: "./workspace"
```

---

## 2. Current Limitations

> **CI integration currently works only for the nova project. Support for other projects will be added soon.**

While the *diff extraction* and *AI translation* steps are automated, the **Merge** step currently requires manual setup due to two main limitations.

### Limitation 1: No Automatic PO Fetching
The current script does **not** automatically download the existing human-translated `.po` files from translation platforms (like Weblate or Zanata) or the remote Git repository.
* Even for simple projects like `nova`, the script assumes the base `.po` file is already present locally.

### Limitation 2: Project Structure Complexity
For complex projects, simply downloading "the translation file" is not enough because multiple translation domains exist within a single repository. The script does not yet automatically detect **which** PO file corresponds to the code changes.

* **Simple Projects (e.g., Nova):** Single domain (`nova.po`).
* **Complex Projects (e.g., Horizon):** Multiple domains:
    * Python/HTML changes $\rightarrow$ need `django.po`
    * JavaScript changes $\rightarrow$ need `djangojs.po`
    * Release Notes $\rightarrow$ need `releasenotes.po`

**Current Status:** Users must manually download the correct `.po` file and place it in the `./data/target/{lang}/` directory and update `config.yaml`.