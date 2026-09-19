# PiForge

PiForge builds an experimental, flashable **Raspberry Pi 5 / BCM2712,
ARM64, Raspberry Pi OS Lite Bookworm** image from official upstream sources.
It installs RetroPie, EmulationStation, RetroArch, and these libretro cores:

* lr-snes9x
* lr-genesis-plus-gx
* lr-gambatte
* lr-fceumm
* lr-mgba
* lr-pcsx-rearmed
* lr-mupen64plus-next

The source and base-image pins are in `configs/`. Each component is built and
checked separately. Output includes `.img.xz`, SHA256 checksums, JSON provenance
(also `/etc/piforge-build-info.json` inside the image), and build logs.

**Status:** initial implementation; a successful GitHub Actions image build
and physical Pi 5 validation are still required. Source inspection, static
tests, and Linux filesystem tests are not proof of hardware compatibility.
The base and Git inputs are pinned, but moving distribution APT repositories
mean builds are not yet bit-for-bit reproducible.

## Build

Use a dedicated native ARM64 Linux machine/VM with root access, loop devices,
at least 4 GiB RAM (8 GiB recommended), and at least 30 GiB free workspace.
The builder expands a disposable image file; it does not flash a device.

```bash
sudo apt-get update
sudo apt-get install -y git curl python3 xz-utils util-linux fdisk e2fsprogs dosfstools shellcheck
bash scripts/validate.sh
# Commit any local configuration changes before building.
sudo bash scripts/build-image.sh
```

For GitHub Actions, push the repository to GitHub, select **Actions → Build
experimental Pi 5 image → Run workflow**, then download `piforge-image-*` and
`piforge-logs-*`. The workflow uses `ubuntu-24.04-arm`; check your repository's
runner availability and quota. Builds are manual, and no Release is published.
See [BUILDING](docs/BUILDING.md) for container use and build details.

## Flash and use

Extract the artifact archive and run `sha256sum --check *.sha256` from the
directory containing the image and metadata. On macOS, use
`shasum -a 256 -c NAME.sha256`. Open Raspberry Pi Imager, choose **Use custom**,
select the `.img.xz`, and carefully select the intended microSD/USB device.
Flashing erases that selected device. The image builder itself never flashes.

Connect a keyboard and display to the Pi 5. The first local boot prompts for
a password for the `pi` account. Log in and run `emulationstation` on the local
console. There is no shared password, SSH enablement, automatic login, or
bundled network credential. Empty systems may not appear in EmulationStation
until you supply your own legal content under `/home/pi/RetroPie/roms`.

No ROMs, console BIOS files, commercial game assets, or secrets are included.
Required OS firmware and licensed upstream application UI resources are
included. Emulator and resource licenses remain applicable; some emulator
licenses have noncommercial restrictions. This is not an official RetroPie
release or a Raspberry Pi compatibility certification.

## Documentation

* [Upstream Pi 5 support and source evidence](docs/RETROPIE_PI5_SUPPORT.md)
* [Build architecture and reproducibility limits](docs/ARCHITECTURE.md)
* [Local and CI builds](docs/BUILDING.md)
* [Hardware validation](docs/HARDWARE_TESTING.md)
* [Troubleshooting](docs/TROUBLESHOOTING.md)
