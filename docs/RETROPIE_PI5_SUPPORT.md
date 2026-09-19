# RetroPie upstream Raspberry Pi 5 support

Inspected 2026-09-18 at RetroPie-Setup commit
[`664d2537d310edea267994097f800f82387f1a5d`](https://github.com/RetroPie/RetroPie-Setup/tree/664d2537d310edea267994097f800f82387f1a5d)
(2026-09-16, setup version 4.8.12). These are source-inspection findings,
not claims that an image has booted or that every emulator has passed hardware tests.

## Platform and operating system

* [`system.sh`](https://github.com/RetroPie/RetroPie-Setup/blob/664d2537d310edea267994097f800f82387f1a5d/scriptmodules/system.sh):
  `get_rpi_model` reads the revision from `/proc/cpuinfo`, decodes processor
  bits 12–15, and maps value 4 (BCM2712) to `rpi5`. It does not depend on a
  literal BCM2712 string in cpuinfo. `platform_rpi5` selects Cortex-A76,
  `rpi gles gles3 gles31`. `cpu_armv8` adds `aarch64` for 64-bit userspace;
  the separate 32-bit path adds `arm armv8 neon` and ARM32 FPU flags.
* `get_os_version` accepts Debian 12. ARM64 Raspberry Pi OS identifies as
  Debian; the presence of the official Raspberry Pi APT repository makes
  upstream treat it as Raspbian. Package indexes must exist before setup.
  Bookworm binary availability is enabled for both 32-bit and 64-bit; this
  is an eligibility rule, not proof that every binary archive exists.
* Upstream already has an [ARM64 Bookworm image definition](https://github.com/RetroPie/RetroPie-Setup/blob/664d2537d310edea267994097f800f82387f1a5d/scriptmodules/admin/image/dists/rpios-bookworm-64.ini)
  listing `rpi3 rpi4 rpi5`. PiForge uses that definition's official
  2026-04-13 Bookworm Lite image, verified against its [published SHA256](https://downloads.raspberrypi.com/raspios_oldstable_lite_arm64/images/raspios_oldstable_lite_arm64-2026-04-14/2026-04-13-raspios-bookworm-arm64-lite.img.xz.sha256).
  The `oldstable` URL is intentional: current Raspberry Pi OS and Bookworm
  are no longer synonymous.
* Off-device builds must explicitly select `__platform=rpi5`; otherwise
  setup detects the build host. This is an existing upstream environment
  input, not a fabricated Pi device tree.

## Graphics and dependencies

* `get_rpi_video` enables Mesa/KMS by default in a chroot on Debian 11+.
  On hardware it checks the loaded `vc4` module. ARM64 does not get the
  legacy DispmanX flag. PiForge explicitly selects KMS for its chroot.
* Preserve full `dtoverlay=vc4-kms-v3d` in `/boot/firmware/config.txt`.
  [Raspberry Pi documents](https://www.raspberrypi.com/documentation/computers/config_txt.html)
  this boot path and overlay. Do not substitute FKMS, `/opt/vc` userland
  libraries, `gpu_mem`, Pi 4 HDMI tuning, overclocking, or a 32-bit kernel.
* [Mesa's V3D/V3DV documentation](https://docs.mesa3d.org/drivers/v3d.html)
  distinguishes the OpenGL/GLES driver from the Vulkan driver. Install
  distribution Mesa EGL/GL/GLES, GBM, DRM, and DRI libraries. V3DV Vulkan
  support is separate from an application's Vulkan build options.
* [`retroarch.sh`](https://github.com/RetroPie/RetroPie-Setup/blob/664d2537d310edea267994097f800f82387f1a5d/scriptmodules/emulators/retroarch.sh)
  enables SDL2, KMS/EGL, GLES3/3.1, and disables legacy VideoCore for
  Pi/Mesa. **Pi 5's platform flags do not include `vulkan`: RetroArch is
  built with `--disable-vulkan`.** PiForge retains that behavior. The image
  includes `mesa-vulkan-drivers`, `libvulkan1`, and `vulkan-tools` for
  hardware diagnostics, not a promise of a Vulkan RetroArch renderer.
* [`emulationstation.sh`](https://github.com/RetroPie/RetroPie-Setup/blob/664d2537d310edea267994097f800f82387f1a5d/scriptmodules/supplementary/emulationstation.sh)
  builds Pi/Mesa using `RPI=On`, `GL=On`, `USE_GL21=On`. Its SDL2 dependency
  therefore needs KMSDRM plus EGL/OpenGL support for a console session.
  Other dependencies include FreeImage, FreeType, curl, ALSA, VLC, RapidJSON,
  and python3-sdl2. Headless CI cannot establish DRM master access.
* [`helpers.sh`](https://github.com/RetroPie/RetroPie-Setup/blob/664d2537d310edea267994097f800f82387f1a5d/scriptmodules/helpers.sh)
  supports `own_sdl2 = "0"` in `configs/all/retropie.cfg`. PiForge uses
  distribution SDL2 through this supported option, avoiding the custom
  SDL2 binary/source download path. Verify the installed SDL has KMSDRM in
  build tests and test its actual video output on hardware.
* Upstream adds `gldriver-test` for Pi 5 on Raspberry Pi OS; its kernel
  header mapping selects `linux-headers-rpi-2712`. `runcommand` pulls in
  `kmsxx` utilities. These are not reasons to install Pi 4 kernel packages.

## Requested components

Each recipe below is under [scriptmodules](https://github.com/RetroPie/RetroPie-Setup/tree/664d2537d310edea267994097f800f82387f1a5d/scriptmodules).
All requested modules are enabled for Pi 5 ARM64 in this revision. This
establishes recipe support; successful compilation and runtime compatibility
remain separate tests. PiForge builds each from a locked source commit.

| Component | Upstream behavior relevant to Pi 5 ARM64 |
| --- | --- |
| RetroArch | RetroPie `retropie-v1.19.0` source branch; KMS/EGL/GLES path above |
| EmulationStation | `stable` branch on Bookworm; SDL2 and desktop OpenGL via Mesa |
| lr-snes9x | Generic 64-bit build; ARM32 `platform=armv` is not applied |
| lr-genesis-plus-gx | Generic `Makefile.libretro`; no ARM64 exclusion |
| lr-gambatte | Generic `Makefile.libretro`; installs a text color palette, not a BIOS |
| lr-fceumm | Generic `Makefile.libretro`; FDS BIOS is user-supplied |
| lr-mgba | CMake `BUILD_LIBRETRO=ON`, `LIBMGBA_ONLY=ON` |
| lr-pcsx-rearmed | Explicit `ARCH=aarch64 DYNAREC=ari64`; threaded rendering disabled |
| lr-mupen64plus-next | GLES3; ARM64 avoids ARM32 platform and FPU parameters; ParaLLEl RDP/RSP enabled only for x86 by this recipe |

## Workarounds, exclusions, and inherited assumptions

* `lr-mupen64plus-next` has `-mfp16-format=ieee` for **32-bit** ARMv8
  Bookworm. It is not appropriate to copy that flag to ARM64.
* Standalone `mupen64plus` removes `-ffast-math` for its Cortex-A76 build
  issue. It is a different module from the requested libretro core.
* `lr-mupen64plus` (older core), `np2pi`, and `lr-kronos` explicitly exclude
  aarch64. `gamecondriver` and `mkarcadejoystick` explicitly exclude Pi 5.
  They are outside the initial set; PiForge does not force-enable them.
* N64 configuration still applies broad `rpi` defaults: threaded GL,
  disabled hybrid filter/overscan, native resolution factor 1. Keep those
  defaults until hardware measurements justify changing them.
* EmulationStation's crash message still recommends `gpu_split`; that
  legacy diagnostic is not guidance for configuring Pi 5 KMS.
* Upstream's general `admin/image.sh` currently forces `kernel8.img` for
  64-bit builds (4 KiB pages). PiForge preserves the official Pi 5 kernel
  selection, including `kernel_2712.img`; physical tests must cover the
  resulting page size and each core's dynamic recompiler. This difference
  is explicit and is not evidence that 16 KiB pages pass every emulator.
* That image builder also sets initramfs-tools `MODULES=most` because a
  chroot cannot discover its physical root device. PiForge's first real
  package-install attempt reproduced `mkinitramfs: failed to determine
  device for /`; the same documented configuration is applied before APT.
  This is an image-build requirement, not an emulator compatibility patch.
* No inspected requested module is known here to require a new PiForge
  compatibility patch. No new failures are claimed without build evidence.
  Source compilation is PiForge's pinning policy, not a claim that upstream
  has no Bookworm ARM64 binaries. Do not silently omit a failed core.

## Evidence boundaries

Pinning RetroPie-Setup alone does not pin its child repositories, optional
assets, or APT packages. PiForge additionally locks downloaded Git sources
and records installed package versions. Distribution APT repositories still
move; until an immutable package archive is maintained, this is a traceable
repeatable recipe, not bit-for-bit image reproducibility. No QEMU or chroot
test establishes physical Pi 5 boot, GPU, audio, or controller compatibility.
