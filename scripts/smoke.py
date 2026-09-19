#!/usr/bin/env python3
"""Build-time checks: no GPU, display, ROM, or physical Pi is assumed."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import xml.etree.ElementTree as ET

from boot_config import validate_boot
from config import CORES, load, require


def check_elf(path):
    with path.open("rb") as binary:
        header = binary.read(20)
    require(len(header) == 20 and header[:6] == b"\x7fELF\x02\x01"
            and struct.unpack("<H", header[18:20])[0] == 183,
            f"Not an ARM64 little-endian ELF: {path}")


def check_component(module, root=Path("/"), execute=True):
    if module == "retroarch":
        binary = root / "opt/retropie/emulators/retroarch/bin/retroarch"
    elif module == "emulationstation":
        binary = root / "opt/retropie/supplementary/emulationstation/emulationstation"
    else:
        binary = root / "opt/retropie/libretrocores" / module / CORES[module]
    require(binary.is_file() and binary.stat().st_size > 0, f"Missing component: {module}")
    check_elf(binary)
    if execute:
        linkage = subprocess.run(["ldd", str(binary)], text=True, capture_output=True, check=True)
        require("not found" not in linkage.stdout + linkage.stderr, f"Unresolved library: {module}")
        if module in CORES:
            core = ctypes.CDLL(str(binary), mode=os.RTLD_NOW)
            for symbol in ("retro_init", "retro_deinit", "retro_api_version", "retro_get_system_info"):
                require(hasattr(core, symbol), f"Missing libretro API {symbol}: {module}")
            core.retro_api_version.restype = ctypes.c_uint
            require(core.retro_api_version() == 1, f"Unexpected libretro API: {module}")
        elif module == "retroarch":
            subprocess.run([str(binary), "--version"], check=True)
        else:
            subprocess.run(["runuser", "-u", "pi", "--", str(binary), "--help"], check=True)
    print(f"PASS component {module}")


def check_content(root, palette_source):
    """Fail closed on any file in game directories; permit only the exact palette."""
    base = root / "home/pi/RetroPie"
    for directory in (base / "roms", base / "BIOS"):
        require(directory.is_dir() and not directory.is_symlink(), f"Missing/unsafe {directory}")
        for path in directory.rglob("*"):
            require(not path.is_symlink(), f"Unexpected content symlink: {path}")
            if path.is_dir():
                continue
            if path == base / "BIOS/palettes/default.pal":
                require(path.read_bytes() == palette_source.read_bytes(), "Unexpected palette content")
            else:
                raise ValueError(f"Unexpected ROM/BIOS directory content: {path}")


def package_installed(name):
    state = subprocess.check_output(
        ["dpkg-query", "-W", "-f=${db:Status-Status}", name], text=True
    )
    require(state == "installed", f"Missing package: {name}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--component", choices=["retroarch", "emulationstation", *CORES])
    args = parser.parse_args()
    config, _ = load()
    require(subprocess.check_output(["dpkg", "--print-architecture"], text=True).strip() == "arm64",
            "Wrong userspace architecture")
    if args.component:
        check_component(args.component)
        return
    release = dict(line.split("=", 1) for line in Path("/etc/os-release").read_text().splitlines() if "=" in line)
    require(release["VERSION_CODENAME"].strip('"') == config["os_release"], "Wrong OS release")
    require(Path("/etc/rpi-issue").is_file(), "Not Raspberry Pi OS")
    require(Path("/opt/RetroPie-Setup/retropie_packages.sh").is_file(), "Missing RetroPie setup")
    require(Path("/opt/retropie/supplementary/runcommand/runcommand.sh").is_file(), "Missing runcommand")
    require(Path("/opt/retropie/supplementary/kmsxx/kmsprint-rp").is_file(), "Missing KMS helper")
    for module in ["emulationstation", *config["emulators"]]:
        check_component(module)
    for package in ("libsdl2-2.0-0", "libegl1", "libgles2", "libgbm1", "libdrm2", "libgl1-mesa-dri", "libglx-mesa0"):
        package_installed(package)
    for library in ("libEGL.so.1", "libGLESv2.so.2", "libGL.so.1", "libgbm.so.1", "libdrm.so.2"):
        ctypes.CDLL(library)
    sdl = ctypes.CDLL("libSDL2-2.0.so.0")
    sdl.SDL_GetVideoDriver.restype = ctypes.c_char_p
    drivers = [sdl.SDL_GetVideoDriver(i).decode() for i in range(sdl.SDL_GetNumVideoDrivers())]
    require("KMSDRM" in drivers, f"SDL2 lacks KMSDRM: {drivers}")
    if config["vulkan_diagnostics"]:
        for package in ("libvulkan1", "mesa-vulkan-drivers", "vulkan-tools"):
            package_installed(package)
        ctypes.CDLL("libvulkan.so.1")
        require(Path("/usr/bin/vulkaninfo").is_file(), "Missing vulkaninfo")
        icds = list(Path("/usr/share/vulkan/icd.d").glob("*broadcom*.json"))
        require(icds, "Missing Broadcom V3DV ICD manifest")
        for icd in icds:
            ctypes.CDLL(json.loads(icd.read_text())["ICD"]["library_path"])
    validate_boot(Path("/boot/firmware"))
    require(Path("/boot/firmware/kernel_2712.img").is_file(), "Missing Pi 5 kernel")
    require(Path("/boot/firmware/bcm2712-rpi-5-b.dtb").is_file(), "Missing Pi 5 device tree")
    systems = ET.parse("/etc/emulationstation/es_systems.cfg").getroot()
    require(systems.tag == "systemList" and len(systems) > 0, "Invalid EmulationStation systems")
    palette = Path("/opt/RetroPie-Setup/scriptmodules/libretrocores/lr-gambatte/default.pal")
    check_content(Path("/"), palette)
    require(Path("/etc/systemd/system/multi-user.target.wants/piforge-firstboot.service").is_symlink(),
            "Missing first-boot account provisioning")
    print("PASS build-time image checks (hardware graphics/boot NOT tested)")


if __name__ == "__main__":
    main()
