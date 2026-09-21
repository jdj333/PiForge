#!/usr/bin/env python3
import json
import os
from pathlib import Path
import subprocess
import sys

url, directory, commit = sys.argv[1:]
submodules = subprocess.check_output(
    ["git", "-c", f"safe.directory={directory}", "-C", directory, "submodule", "status", "--recursive"], text=True
).splitlines() if (Path(directory) / ".gitmodules").is_file() else []
if any(line[0] != " " for line in submodules):
    raise SystemExit("Submodule is missing or not at its pinned commit")
record = {"url": url, "commit": commit, "path": directory, "submodules": submodules}
# Some upstream trees contain unused gitlinks without a .gitmodules file.
# Preserve those references for provenance without inventing dependency URLs.
tree = subprocess.check_output(
    ["git", "-c", f"safe.directory={directory}", "-C", directory, "ls-tree", "-r", "HEAD"], text=True
)
record["gitlinks"] = [line for line in tree.splitlines() if line.startswith("160000 ")]
with (Path(os.environ.get("PIFORGE_LOG_DIR", "/var/log/piforge")) / "sources.jsonl").open("a") as output:
    output.write(json.dumps(record, sort_keys=True) + "\n")
