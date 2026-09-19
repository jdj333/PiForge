#!/usr/bin/env python3
"""Lock distribution package versions from a successful image's metadata.

Repositories still need to retain these versions. Unavailable locked versions
must fail a build; never silently substitute a newer package.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

from config import ROOT, load, require


def input_digest():
    config, sources = load()
    inputs = {"base_image_sha256": config["base_image_sha256"],
              "retropie_commit": config["retropie_commit"],
              "emulators": config["emulators"],
              "vulkan_diagnostics": config["vulkan_diagnostics"], "sources": sources}
    return hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()


def validate_lock(lock):
    require(lock["schema_version"] == 1, "package lock schema")
    require(lock["inputs_sha256"] == input_digest(), "package lock inputs changed; regenerate and review")
    require(isinstance(lock["packages"], dict) and lock["packages"], "empty package lock")
    for package, version in lock["packages"].items():
        require(re.fullmatch(r"[a-z0-9][a-z0-9+.-]*(?::(?:arm64|armhf))?", package), "invalid package name")
        require(re.fullmatch(r"[0-9][a-zA-Z0-9.+:~_-]*", version), "invalid package version")


def installed_packages():
    output = subprocess.check_output(
        ["dpkg-query", "-W", "-f=${binary:Package}\t${Version}\t${db:Status-Status}\n"], text=True
    )
    return {name: version for name, version, status in (line.split("\t") for line in output.splitlines())
            if status == "installed"}


def compare_packages(expected, actual):
    differences = {name: {"expected": expected.get(name), "actual": actual.get(name)}
                   for name in sorted(expected.keys() | actual.keys()) if expected.get(name) != actual.get(name)}
    require(not differences, "Package drift:\n" + json.dumps(differences, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["validate", "arguments", "preferences", "check", "from-metadata"])
    parser.add_argument("metadata", nargs="?", type=Path)
    args = parser.parse_args()
    path = ROOT / "configs/packages.lock.json"
    if args.command == "from-metadata":
        require(args.metadata is not None, "metadata path required")
        metadata = json.loads(args.metadata.read_text())
        require(metadata["validation"]["build_time"] == "passed", "metadata must report successful build-time tests")
        config, sources = load()
        require(metadata["source_lock"] == sources and metadata["build_configuration"] == config,
                "metadata does not match this configuration")
        packages = {item["name"]: item["version"] for item in metadata["packages"] if item["status"] == "installed"}
        lock = {"schema_version": 1, "inputs_sha256": input_digest(), "packages": packages}
        validate_lock(lock)
        path.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")
        print(f"Wrote {len(packages)} exact package versions to {path}")
        return
    lock = json.loads(path.read_text())
    validate_lock(lock)
    if args.command == "arguments":
        print("\n".join(f"{name}={version}" for name, version in sorted(lock["packages"].items())))
    elif args.command == "preferences":
        for name, version in sorted(lock["packages"].items()):
            print(f"Package: {name}\nPin: version {version}\nPin-Priority: 1001\n")
    elif args.command == "check":
        compare_packages(lock["packages"], installed_packages())
        print("PASS exact package versions and package inventory")
    else:
        print(f"Package lock is valid ({len(lock['packages'])} packages)")


if __name__ == "__main__":
    main()
