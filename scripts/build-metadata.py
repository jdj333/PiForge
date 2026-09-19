#!/usr/bin/env python3
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess

from config import CORES, load


def sha256(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


config, lock = load()
package_lock_path = Path(__file__).resolve().parents[1] / "configs/packages.lock.json"
packages_locked = os.environ.get("PIFORGE_PACKAGE_BOOTSTRAP", "0") != "1"
packages = subprocess.check_output(
    ["dpkg-query", "-W", "-f=${binary:Package}\t${Version}\t${Architecture}\t${db:Status-Status}\n"],
    text=True,
)
package_versions = [dict(zip(("name", "version", "architecture", "status"), line.split("\t")))
                    for line in packages.splitlines()]
source_records = [json.loads(line) for line in Path("/var/log/piforge/sources.jsonl").read_text().splitlines()]
emulators = {}
for module in config["emulators"]:
    path = (Path("/opt/retropie/emulators/retroarch/bin/retroarch") if module == "retroarch" else
            Path("/opt/retropie/libretrocores") / module / CORES[module])
    emulators[module] = {**lock["sources"][module], "binary_sha256": sha256(path)}
metadata = {
    "schema_version": 1,
    "build_version": config["build_version"],
    "piforge_commit": os.environ["PIFORGE_COMMIT"],
    "retropie_setup_commit": config["retropie_commit"],
    "base_image": {key: config[key] for key in ("base_image_version", "base_image_url", "base_image_sha256", "os_release")},
    "build_date": os.environ["BUILD_DATE"],
    "build_architecture": platform.machine(),
    "target_architecture": "arm64",
    "kernel_versions": sorted(path.name for path in Path("/lib/modules").iterdir() if path.is_dir()),
    "kernel_images": {path.name: sha256(path) for path in Path("/boot/firmware").glob("kernel*.img")},
    "packages": package_versions,
    "emulators": emulators,
    "emulationstation": lock["sources"]["emulationstation"],
    "source_lock": lock,
    "package_lock": json.loads(package_lock_path.read_text()) if packages_locked else None,
    "resolved_sources": source_records,
    "build_configuration": config,
    "apt_sources": {str(path): path.read_text() for path in Path("/etc/apt").rglob("*")
                    if path.is_file() and path.suffix in {".list", ".sources"}},
    "validation": {"build_time": "passed", "physical_pi5": "not_run"},
    "reproducibility": {"base_and_git_sources_pinned": True, "package_versions_locked": packages_locked,
                        "apt_snapshot_pinned": False,
                        "bit_identical": False},
}
Path("/etc/piforge-build-info.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
