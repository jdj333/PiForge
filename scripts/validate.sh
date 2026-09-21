#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
python3 scripts/config.py validate
python3 scripts/packages.py validate
shellcheck -x scripts/*.sh tests/*.sh
for script in scripts/*.sh tests/*.sh; do bash -n "$script"; done
python3 -m unittest discover -s tests -v
git diff --check
