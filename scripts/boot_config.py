#!/usr/bin/env python3
"""Conservative validator for the firmware configuration used by this image.

This validates text syntax and PiForge's supported configuration subset; only
firmware on physical hardware can validate every parameter's interpretation.
"""
from pathlib import Path
import re


def validate_boot(boot):
    seen = set()
    effective = {}
    overlays = []

    def parse(path, active=True):
        path = path.resolve()
        if not path.is_relative_to(boot.resolve()) or path in seen:
            raise ValueError("Unsafe or cyclic firmware include")
        seen.add(path)
        for number, raw in enumerate(path.read_text().splitlines(), 1):
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            if len(line) > 98:
                raise ValueError(f"Firmware line longer than 98 characters: {path}:{number}")
            if re.fullmatch(r"\[[^\[\]]+\]", line):
                section = line[1:-1]
                # Evaluate only the target model and unconditional settings.
                # Unknown conditional hardware filters need explicit review.
                if section not in {"all", "none", "pi0", "pi0w", "pi1", "pi2", "pi3", "pi3+",
                                   "pi4", "pi5", "cm4", "cm5"}:
                    raise ValueError(f"Unreviewed firmware conditional: {section}")
                active = section in {"all", "pi5"}
            elif line.startswith("include "):
                if active:
                    parse(boot / line[8:].strip(), active)
            elif re.fullmatch(r"[a-zA-Z0-9_:.]+\s*=.*", line):
                key, value = (part.strip() for part in line.split("=", 1))
                if active:
                    effective[key] = value
                    if key == "dtoverlay":
                        overlays.append(value.split(",", 1)[0])
            else:
                raise ValueError(f"Invalid firmware syntax: {path}:{number}: {line}")
        seen.remove(path)

    parse(boot / "config.txt")
    if overlays.count("vc4-kms-v3d") != 1 or any("fkms" in item for item in overlays):
        raise ValueError("Exactly one effective full KMS overlay is required; FKMS is unsupported")
    if effective.get("arm_64bit") != "1":
        raise ValueError("arm_64bit=1 is required")
    cmdline = (boot / "cmdline.txt").read_text().strip().splitlines()
    if len(cmdline) != 1 or len(re.findall(r"(?:^|\s)root=PARTUUID=[0-9a-fA-F-]+(?:\s|$)", cmdline[0])) != 1:
        raise ValueError("cmdline.txt must have one line and one PARTUUID root")
    return effective
