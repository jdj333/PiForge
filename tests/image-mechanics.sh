#!/usr/bin/env bash
# Privileged Linux test using only a disposable synthetic disk, no downloads.
# shellcheck source=scripts/common.sh
source "$(dirname "$0")/../scripts/common.sh"
[[ $EUID == 0 && $(uname -s) == Linux ]] || die "Needs root on Linux"
if [[ ${1:-} != --private ]]; then exec unshare --mount --propagation private "$0" --private; fi
WORK=$(mktemp -d)
IMAGE="$WORK/test.img" ROOTFS="$WORK/rootfs" LOOP=''
cleanup() {
    local status=$?
    trap - EXIT
    if mountpoint -q "$ROOTFS"; then umount "$ROOTFS" || exit 1; fi
    if [[ -n $LOOP ]]; then losetup -d "$LOOP" || exit 1; fi
    rm -rf "$WORK"
    exit "$status"
}
trap cleanup EXIT
truncate -s 1G "$IMAGE"
printf 'label: dos\nlabel-id: 0x1234abcd\nstart=2048,size=65536,type=c\nstart=67584,type=83\n' | sfdisk "$IMAGE"
sfdisk --json "$IMAGE" > "$WORK/layout.json"
export ROOT_START
ROOT_START=$(python3 "$PIFORGE_ROOT/scripts/image-layout.py" < "$WORK/layout.json")
LOOP=$(losetup --find --show --partscan "$IMAGE")
wait_loop_partitions "$LOOP"
mkfs.vfat "${LOOP}p1"
mkfs.ext4 -F "${LOOP}p2"
mkdir "$ROOTFS"
mount "${LOOP}p2" "$ROOTFS"
printf 'preserve this payload\n' > "$ROOTFS/payload"
umount "$ROOTFS"
before=$(blkid -s PARTUUID -o value "${LOOP}p2")
losetup -d "$LOOP"; LOOP=''
source "$PIFORGE_ROOT/scripts/shrink-image.sh"
shrink_image
[[ $(stat -c %s "$IMAGE") -lt $((1024**3)) ]] || die "Image did not shrink"
LOOP=$(losetup --find --show --partscan "$IMAGE")
wait_loop_partitions "$LOOP"
[[ $(blkid -s PARTUUID -o value "${LOOP}p2") == "$before" ]] || die "PARTUUID changed"
check_ext4 "${LOOP}p2"
mount "${LOOP}p2" "$ROOTFS"
[[ $(cat "$ROOTFS/payload") == 'preserve this payload' ]] || die "Payload damaged"
log "PASS synthetic image shrink, filesystem integrity, payload and PARTUUID preservation"
