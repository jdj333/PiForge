#!/usr/bin/env bash
# shellcheck source=scripts/common.sh
source "$(dirname "$0")/common.sh"
guest_only
log "Prepare Bookworm ARM64 dependencies and RetroPie"
python3 - <<'PY'
from pathlib import Path
release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
if release.get('VERSION_CODENAME', '').strip('"') != 'bookworm':
    raise SystemExit('Wrong OS release')
PY
# initramfs-tools cannot discover a physical root device inside this chroot.
# Upstream admin/image.sh also selects MODULES=most for image construction.
mkdir -p /etc/initramfs-tools/conf.d
printf 'MODULES=most\n' > /etc/initramfs-tools/conf.d/piforge
apt-get -o APT::Update::Error-Mode=any update
apt-get install -y --no-install-recommends \
    ca-certificates git curl sudo locales lsb-release gnupg build-essential pkg-config \
    python3 python3-sdl2 python3-pyudev python3-urwid python3-uinput \
    libsdl2-dev libegl1-mesa-dev libgles2-mesa-dev libgl1-mesa-dri libglx-mesa0 \
    libgbm-dev libdrm-dev libasound2-dev libudev-dev libxkbcommon-dev binutils \
    cmake meson ninja-build gldriver-test
if [[ $VULKAN_DIAGNOSTICS == 1 ]]; then
    apt-get install -y --no-install-recommends libvulkan1 mesa-vulkan-drivers vulkan-tools
fi
if ! id pi >/dev/null 2>&1; then useradd --create-home --shell /bin/bash pi; fi
usermod -L pi
for group in audio video input render sudo; do
    getent group "$group" >/dev/null || groupadd --system "$group"
    usermod -a -G "$group" pi
done
mkdir -p /opt/retropie/configs/all /home/pi/RetroPie/roms /home/pi/RetroPie/BIOS
printf 'own_sdl2 = "0"\n' > /opt/retropie/configs/all/retropie.cfg
chown -R pi:pi /opt/retropie/configs /home/pi/RetroPie
git init /opt/RetroPie-Setup
git -C /opt/RetroPie-Setup remote add origin "$RETROPIE_REPOSITORY"
git -C /opt/RetroPie-Setup fetch --depth=1 origin "$RETROPIE_COMMIT"
git -C /opt/RetroPie-Setup checkout --detach "$RETROPIE_COMMIT"
[[ $(git -C /opt/RetroPie-Setup rev-parse HEAD) == "$RETROPIE_COMMIT" ]] || die "RetroPie commit mismatch"
python3 - <<'PY'
from pathlib import Path
root = Path('/opt/RetroPie-Setup')
entry = (root / 'retropie_packages.sh').read_text()
needle = '\nrp_registerAllModules\n'
if entry.count(needle) != 1:
    raise SystemExit('Upstream entry point changed; review the build adapter')
entry = entry.replace(needle, needle + '\nsource /opt/piforge/scripts/locked-sources.sh\n')
(root / 'piforge_packages.sh').write_text(entry)
PY
# Runcommand uses existing kmsxx when present. Build it first to keep the
# dependency path explicit and prevent automatic binary fallback.
bash "$PIFORGE_ROOT/scripts/retropie-module.sh" kmsxx
bash "$PIFORGE_ROOT/scripts/retropie-module.sh" runcommand _binary_
bash "$PIFORGE_ROOT/scripts/retropie-module.sh" emulationstation
