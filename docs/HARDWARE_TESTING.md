# Physical Raspberry Pi 5 validation

Hardware validation is a separate milestone. A native ARM64 chroot or QEMU
can verify architecture, file presence, linkage and some CLI behavior. Neither
proves Pi 5 firmware boot, V3D acceleration, KMS ownership, HDMI audio, USB/Bluetooth
input, thermal behavior or emulator performance.

## Record the test system

Retain the image checksum and `/etc/piforge-build-info.json`, Pi model and RAM,
EEPROM version, storage medium, power supply, cooling, display/cable/HDMI port,
controller models, and test date. Use a spare device/card. Check the published
SHA256 before writing. Record results separately from build-time metadata.

## Acceptance checks

1. Boot the exact artifact on Pi 5. Confirm first boot expands the root
   filesystem and prompts for a new local `pi` password. Reboot; provisioning
   must not repeat. Confirm no shared password, unexpected autologin or SSH.
2. Record `uname -a`, `dpkg --print-architecture`, `/etc/os-release`,
   `/proc/device-tree/model`, `lsblk -f`, and `df -h /`. Expect ARM64 Bookworm,
   BCM2712 Pi 5 and a Pi 5 kernel. Check `journalctl -b -p warning` for errors.
   Record `getconf PAGE_SIZE`; test the dynarec cores with the stock Pi 5
   kernel's page size rather than assuming a 4 KiB kernel.
3. Check `lsmod` for vc4/v3d and `/dev/dri` for card/render nodes. Run
   `/opt/retropie/supplementary/kmsxx/kmsprint`; record connected connectors
   and modes. Do not assume the display card is always `card0`.
4. Launch `emulationstation` as `pi` from the physical VT. Confirm SDL2 KMSDRM,
   accelerated Mesa rendering, readable menus, no llvmpipe/software fallback,
   and clean transitions between EmulationStation and RetroArch. Capture
   application logs, renderer strings, and EGL/GL capabilities. `glxinfo` alone
   is not a valid test on an image without an X server.
5. Run `vulkaninfo --summary`, capture stderr as well as output, and identify
   the Broadcom V3DV physical GPU. A loader library or software Vulkan device
   is insufficient. This image's upstream RetroArch recipe disables Vulkan;
   that is intentional and independent of V3DV enumeration.
6. Test HDMI audio on both ports, volume, reconnect behavior, a USB controller,
   keyboard exit/hotkeys, save states, and return to the frontend. Record any
   Bluetooth pairing tests separately; none are implied by USB success.
7. Test every configured core independently with self-authored or explicitly
   redistributable homebrew fixtures: SNES, Mega Drive, Game Boy, NES, GBA,
   PlayStation and N64. Record fixture license/checksum and whether it needs
   a BIOS. Use privately supplied lawful BIOS files only on the test device;
   never upload them or modified ROM directories as public artifacts.
8. Record frame pacing, audio underruns, crash logs and temperature/throttling
   during a 30-minute session. Test reboot and clean shutdown. N64/PSX behavior
   needs its own evidence; success in a simpler 2D core does not imply it.

No games are bundled just to make the frontend list systems. An empty-library
message on the pristine image is distinct from a graphics/boot failure.

## Future self-hosted runner

Use a trusted, private workflow and labels such as `self-hosted, linux, ARM64,
pi5-hardware`. Do not schedule untrusted fork PRs on hardware with credentials
or a flash-capable controller. Use an independent control machine to download
and verify artifacts, flash a specifically allowlisted removable target,
control power, and collect serial/SSH results from an isolated network.

Flashing/rebooting the runner's own active root disk is not a reliable test
harness. Provision a separate DUT or an A/B boot arrangement with out-of-band
recovery. Bind results to the image SHA256 and PiForge commit, upload sanitized
logs/screenshots and a per-core result JSON, and keep ROMs/BIOS/network credentials
outside artifact paths. Require the hardware report before enabling release
automation. This repository does not yet include a destructive flashing job.
