#!/usr/bin/env bash
# Shared only by PiForge scripts; upstream RetroPie has its own shell semantics.
set -Eeuo pipefail
export LC_ALL=C.UTF-8
PIFORGE_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
export PIFORGE_ROOT
config_shell=$(python3 "$PIFORGE_ROOT/scripts/config.py" shell)
eval "$config_shell"
unset config_shell

log() { printf '\n[PiForge] %s\n' "$*"; }
die() { printf '[PiForge] ERROR: %s\n' "$*" >&2; exit 1; }
guest_only() {
    [[ $EUID -eq 0 && -f /run/piforge-build-guest ]] || die "Run through build-image.sh in its disposable chroot"
    [[ $(dpkg --print-architecture) == arm64 ]] || die "Expected ARM64 userspace"
    [[ $(uname -m) == aarch64 ]] || die "Native ARM64 Linux is required"
}
check_ext4() {
    local status=0
    e2fsck -fy "$1" || status=$?
    [[ $status -le 1 ]] || die "e2fsck failed on $1 (status $status)"
}
wait_loop_partitions() {
    local loop=$1 partition attempt sysdev major minor expected
    for partition in 1 2; do
        sysdev="/sys/class/block/${loop##*/}p$partition/dev"
        for ((attempt=0; attempt<50; attempt++)); do
            [[ -f $sysdev ]] && break
            sleep 0.1
        done
        [[ -f $sysdev ]] || die "Kernel did not expose partition $partition of $loop"
        # Minimal containers have no udev daemon to create partition nodes.
        # Use the device number reported by the kernel for this exact loop.
        IFS=: read -r major minor < "$sysdev"
        [[ $major =~ ^[0-9]+$ && $minor =~ ^[0-9]+$ ]] || die "Invalid kernel device number"
        printf -v expected '%x:%x' "$major" "$minor"
        if [[ -b ${loop}p$partition && $(stat -c '%t:%T' "${loop}p$partition") != "$expected" ]]; then
            rm "${loop}p$partition"
        fi
        if [[ ! -b ${loop}p$partition ]]; then
            mknod "${loop}p$partition" b "$major" "$minor"
        fi
    done
}
