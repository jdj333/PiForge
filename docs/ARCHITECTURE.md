# PiForge image architecture

## Initial implementation plan

Start from the official checksum-pinned Raspberry Pi OS Lite ARM64 Bookworm
disk image, preserving its partition UUIDs, boot firmware, and first-boot
filesystem expansion. Replace the base's account-renaming dialog with a
local password prompt for the fixed RetroPie owner `pi`. Use a native ARM64
Linux host and a chroot for the smallest
initial execution path. GitHub's ARM64 Ubuntu runner can build without CPU
emulation; macOS users need an ARM64 Linux VM. QEMU is not required for this
milestone and is not hardware validation.

One root-owned build process owns its disposable image, loop device, mount
namespace, and cleanup trap. It expands only a regular image file, verifies
the expected DOS/FAT/ext4 two-partition layout, grows the root partition and
filesystem, and mounts the boot partition at `/boot/firmware`. Never accept
a block device as an output target. Bind only required pseudo-filesystems;
prevent daemon startup during package installation. On failure, retain
logs and the work image, unmount in reverse order, and detach only the loop
device allocated by that process.

Install the exact requested modules separately through upstream's module
functions. A small build-only adapter initializes the same module system as
`retropie_packages.sh`, supplies Pi 5/chroot/user inputs, and enforces a Git
source lock at the existing `gitPullOrClone` boundary. It must fail on an
unlocked repository. Use distribution SDL2 via upstream's configuration
switch. No permanent RetroPie fork or Pi 5 compatibility patches are planned.

Run build-time checks inside the image, record source revisions, package
versions, kernel files/packages, architecture, base checksum, build date,
and PiForge revision. Remove source/build caches and temporary service/DNS
changes, check the unmounted filesystem, shrink with ext4 tooling plus
headroom, then compress and checksum. Copy metadata out of the image before
unmounting. Upload logs on failures; publish image artifacts only on success.

## Boundaries

* Configuration: `configs/build.json` and `configs/sources.lock.json`.
* Orchestration: `scripts/build-image.sh`, with phase scripts under `scripts/`.
* Generated work: ignored `build/`; distributable artifacts: ignored `dist/`.
* Validation: unprivileged unit/static tests plus privileged Linux image
  mechanics tests; image content tests execute in ARM64 userspace.
* Runtime: console login, EmulationStation, RetroArch, seven libretro cores.
  A locked `pi` account owns RetroPie data; first-boot provisioning must set
  its password. No default credential, network service, or automatic login.
* Hardware: a separate test plan covers Pi 5 boot, KMS/Mesa rendering,
  Vulkan enumeration, input, audio, and emulator behavior with legal content.

## Reproducibility contract

The base image and Git sources are immutable inputs. APT authenticates
packages against distribution repositories, and metadata records exact
installed versions. Those repositories are not an immutable snapshot; build
timestamps, filesystem identifiers/content ordering, and compiler behavior
also prevent a bit-identical guarantee. A stable release milestone needs a
successful full image build, package snapshot strategy, and hardware evidence.
Local lint/unit success alone must not be presented as that milestone.
