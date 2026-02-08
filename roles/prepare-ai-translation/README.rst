Prepare AI Translation
======================

This role prepares the AI translation environment for OpenStack i18n projects.

It installs required Python packages and copies translation scripts to the node.

**Role Variables**

None required. Uses Zuul variables:
- ``zuul.project.short_name``: Project name to translate
- ``zuul.branch``: Branch to translate

Files copied to ``{{ ansible_user_dir }}/src/opendev.org/openstack/i18n/``:
- ``src/*.py``: Python translation scripts
- ``scripts/ci.sh``: CI pipeline script
- ``config.yaml``: Configuration template
- ``requirements.txt``: Python dependencies
