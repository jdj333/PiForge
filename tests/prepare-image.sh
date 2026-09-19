#!/usr/bin/env bash
# Exercise the real preparation phase and reverse-order teardown on a tiny base.
# shellcheck source=scripts/common.sh
source "$(dirname "$0")/../scripts/common.sh"
[[ $EUID == 0 && $(uname -s) == Linux ]] || die "Needs root on Linux"
if [[ ${1:-} != --private ]]; then exec unshare --mount --propagation private bash "$0" --private; fi
WORK=$(mktemp -d)
IMAGE="$WORK/base.img" ROOTFS="$WORK/rootfs" LOOP=''
MOUNTS=()
DNS_CHANGED=0 POLICY_CHANGED=0
cleanup() {
    local status=$? index
    trap - EXIT
    for ((index=${#MOUNTS[@]}-1; index>=0; index--)); do
        umount "${MOUNTS[index]}" || exit 1
    done
    if [[ -n $LOOP ]]; then losetup -d "$LOOP" || exit 1; fi
    rm -rf "$WORK"
    exit "$status"
}
trap cleanup EXIT
truncate -s 512M "$IMAGE"
printf 'label: dos\nstart=2048,size=65536,type=c\nstart=67584,type=83\n' | sfdisk "$IMAGE"
LOOP=$(losetup --find --show --partscan "$IMAGE")
wait_loop_partitions "$LOOP"
mkfs.vfat "${LOOP}p1"
mkfs.ext4 -F "${LOOP}p2"
mkdir "$ROOTFS"
mount "${LOOP}p2" "$ROOTFS"; MOUNTS+=("$ROOTFS")
mkdir -p "$ROOTFS"/{etc,dev,sys,proc,run,usr/sbin}
printf 'VERSION_CODENAME=bookworm\n' > "$ROOTFS/etc/os-release"
printf 'nameserver 192.0.2.1\n' > "$ROOTFS/etc/resolv.conf"
printf '#!/bin/sh\nexit 42\n' > "$ROOTFS/usr/sbin/policy-rc.d"
chmod 751 "$ROOTFS/usr/sbin/policy-rc.d"
umount "$ROOTFS"; MOUNTS=()
losetup -d "$LOOP"; LOOP=''
export IMAGE_SIZE_GIB=1
mkdir -p "$PIFORGE_ROOT/build/cache/git"
source "$PIFORGE_ROOT/scripts/prepare-image.sh"
prepare_image
[[ $DNS_CHANGED == 1 && $POLICY_CHANGED == 1 ]] || die "Missing preparation state"
[[ $(cat "$ROOTFS/run/piforge-backup/resolv.conf") == 'nameserver 192.0.2.1' ]] || die "DNS backup lost"
[[ $(stat -c %a "$ROOTFS/run/piforge-backup/policy-rc.d") == 751 ]] || die "Policy mode lost"
[[ -f $ROOTFS/run/piforge-build-guest ]] || die "Guest marker missing"
[[ ! -e $ROOTFS/dev/loop-control ]] || die "Host disk control exposed in guest"
[[ ! -S $ROOTFS/run/systemd/private ]] || die "Host service socket exposed in guest"
[[ $(findmnt -n -o OPTIONS --target "$ROOTFS/var/cache/piforge-git") == *ro* ]] || die "Source cache is writable in guest"
mountpoint -q "$ROOTFS/boot/firmware"
[[ $(findmnt -n -o OPTIONS --target "$ROOTFS/sys") == *ro* ]] || die "Guest sysfs is writable"
log "PASS real image expansion, mounts, isolated run/dev, read-only sysfs and configuration backup"
# EXIT deliberately performs the same reverse-order teardown required on error.
