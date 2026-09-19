#!/usr/bin/env python3
"""Cache pinned Git objects between image builds; no source code runs on host."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys

from config import load


def cache_source(cache, source):
    directory = cache / (source["commit"] + ".git")
    if not directory.exists():
        subprocess.run(["git", "init", "--bare", "--quiet", str(directory)], check=True)
    present = subprocess.run(["git", "--git-dir", str(directory), "cat-file", "-e",
                              source["commit"] + "^{commit}"], capture_output=True).returncode == 0
    if not present:
        print(f"Fetch {source['url']} at {source['commit']}", flush=True)
        subprocess.run(["git", "--git-dir", str(directory), "fetch", "--depth=1", source["url"],
                        source["commit"]], check=True)
    # Keep a ref so ordinary Git maintenance cannot prune the pinned object.
    subprocess.run(["git", "--git-dir", str(directory), "update-ref", "refs/heads/pinned",
                    source["commit"]], check=True)
    subprocess.run(["git", "--git-dir", str(directory), "symbolic-ref", "HEAD", "refs/heads/pinned"], check=True)
    subprocess.run(["git", "--git-dir", str(directory), "fsck", "--connectivity-only", "--no-dangling"],
                   check=True, stdout=subprocess.DEVNULL)


if __name__ == "__main__":
    cache = Path(sys.argv[1]).resolve()
    cache.mkdir(parents=True, exist_ok=True)
    config, lock = load()
    sources = list(lock["sources"].values()) + [
        {"url": config["retropie_repository"], "commit": config["retropie_commit"]}]
    with ThreadPoolExecutor(max_workers=config["build_jobs"]) as workers:
        list(workers.map(lambda source: cache_source(cache, source), sources))
