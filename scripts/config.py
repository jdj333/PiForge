#!/usr/bin/env python3
"""Validate data before exposing it to privileged shell code."""
import argparse
import json
from pathlib import Path
import re
import shlex
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
CORES = {
    "lr-snes9x": "snes9x_libretro.so",
    "lr-genesis-plus-gx": "genesis_plus_gx_libretro.so",
    "lr-gambatte": "gambatte_libretro.so",
    "lr-fceumm": "fceumm_libretro.so",
    "lr-mgba": "mgba_libretro.so",
    "lr-pcsx-rearmed": "pcsx_rearmed_libretro.so",
    "lr-mupen64plus-next": "mupen64plus_next_libretro.so",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(config, lock):
    fields = {
        "schema_version", "build_version", "os_release", "base_image_version",
        "base_image_url", "base_image_sha256", "retropie_repository",
        "retropie_commit", "emulators", "output_image_name", "image_size_gib",
        "shrink_headroom_mib", "build_jobs", "vulkan_diagnostics",
    }
    require(set(config) == fields, "unknown or missing configuration fields")
    require(config["schema_version"] == lock["schema_version"] == 1, "schema version")
    require(config["os_release"] == "bookworm", "only Bookworm is supported")
    for key in ("output_image_name", "build_version", "base_image_version"):
        require(isinstance(config[key], str) and
                re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}", config[key]), key)
    for key, length in (("base_image_sha256", 64), ("retropie_commit", 40)):
        require(re.fullmatch(r"[0-9a-f]{%d}" % length, config[key]), key)
    url = urlparse(config["base_image_url"])
    require(url.scheme == "https" and url.netloc == "downloads.raspberrypi.com"
            and url.path.endswith("-bookworm-arm64-lite.img.xz")
            and not url.query and not url.fragment, "official Bookworm ARM64 base URL required")
    require(config["retropie_repository"] == "https://github.com/RetroPie/RetroPie-Setup.git",
            "official RetroPie repository required")
    emulators = config["emulators"]
    require(isinstance(emulators, list) and emulators and emulators[0] == "retroarch",
            "RetroArch must be the first emulator")
    require(len(emulators) == len(set(emulators)) and
            set(emulators) <= {"retroarch", *CORES}, "unsupported or duplicate emulator")
    for key, low, high in (("image_size_gib", 8, 128), ("shrink_headroom_mib", 256, 4096),
                           ("build_jobs", 1, 16)):
        require(type(config[key]) is int and low <= config[key] <= high, key)
    require(type(config["vulkan_diagnostics"]) is bool, "vulkan_diagnostics must be boolean")
    sources = lock["sources"]
    required = set(emulators) | {"emulationstation", "kmsxx", "common-shaders", "core-info",
                               "joypad-autoconfig", "retroarch-assets",
                               "es-theme-carbon", "es-theme-carbon-2021"}
    require(required <= set(sources), "missing source locks")
    urls = set()
    for name, source in sources.items():
        require(re.fullmatch(r"[a-z0-9-]+", name), "invalid source name")
        require(set(source) == {"url", "branch", "commit"}, "invalid source fields")
        require(re.fullmatch(r"https://github.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git",
                             source["url"]), "source must be an HTTPS GitHub repository")
        require(re.fullmatch(r"[0-9a-f]{40}", source["commit"]), "source commit must be immutable")
        require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", source["branch"]), "source branch")
        canonical = source["url"].lower().removesuffix(".git")
        require(canonical not in urls, "duplicate repository lock")
        urls.add(canonical)


def load(root=ROOT):
    config = json.loads((root / "configs/build.json").read_text())
    lock = json.loads((root / "configs/sources.lock.json").read_text())
    validate(config, lock)
    return config, lock


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["validate", "shell", "emulators", "lookup"])
    parser.add_argument("url", nargs="?")
    args = parser.parse_args()
    config, lock = load()
    if args.command == "shell":
        for key, value in config.items():
            if not isinstance(value, list):
                value = str(int(value)) if isinstance(value, bool) else str(value)
                print(f"{key.upper()}={shlex.quote(value)}")
    elif args.command == "emulators":
        print("\n".join(config["emulators"]))
    elif args.command == "lookup":
        wanted = (args.url or "").lower().removesuffix(".git").rstrip("/")
        for source in lock["sources"].values():
            if source["url"].lower().removesuffix(".git") == wanted:
                print(source["commit"])
                break
        else:
            raise SystemExit(f"Unpinned Git repository: {args.url}")
    else:
        print("Configuration and source locks are valid")


if __name__ == "__main__":
    main()
