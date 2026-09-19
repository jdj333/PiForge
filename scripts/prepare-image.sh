#!/usr/bin/env bash
# Variables are shared with the orchestrator and shrink phase.
# shellcheck disable=SC2034
# Sourced by build-image.sh: the caller owns LOOP, MOUNTS, and the cleanup trap.
prepare_image() {
    log "Expand and mount disposable image"
    [[ -f $IMAGE && ! -L $IMAGE ]] || die "Image must be a regular file"
    sfdisk --json "$IMAGE" > "$WORK/layout.json"
    ROOT_START=$(python3 "$PIFORGE_ROOT/scripts/image-layout.py" < "$WORK/layout.json")
    [[ $(stat -c %s "$IMAGE") -lt $((IMAGE_SIZE_GIB * 1024**3)) ]] || die "Configured image size is too small"
    truncate -s "${IMAGE_SIZE_GIB}G" "$IMAGE"
    printf ',+\n' | sfdisk --no-reread -N 2 "$IMAGE"
    LOOP=$(losetup --find --show --partscan "$IMAGE")
    wait_loop_partitions "$LOOP"
    [[ $(blkid -s TYPE -o value "${LOOP}p1") == vfat ]] || die "Boot filesystem is not FAT"
    [[ $(blkid -s TYPE -o value "${LOOP}p2") == ext4 ]] || die "Root filesystem is not ext4"
    check_ext4 "${LOOP}p2"
    resize2fs "${LOOP}p2"
    mkdir -p "$ROOTFS"
    mount "${LOOP}p2" "$ROOTFS"; MOUNTS+=("$ROOTFS")
    mkdir -p "$ROOTFS/boot/firmware"
    mount "${LOOP}p1" "$ROOTFS/boot/firmware"; MOUNTS+=("$ROOTFS/boot/firmware")
    [[ -f $ROOTFS/etc/os-release ]] || die "Base image is missing os-release"
    # Private /run avoids host systemd and D-Bus sockets. Private /dev avoids
    # exposing the host's disks to maintainer scripts inside the chroot.
    mount -t tmpfs -o mode=755 tmpfs "$ROOTFS/run"; MOUNTS+=("$ROOTFS/run")
    mount -t tmpfs -o mode=755 tmpfs "$ROOTFS/dev"; MOUNTS+=("$ROOTFS/dev")
    for device in null zero random urandom tty; do
        touch "$ROOTFS/dev/$device"
        mount --bind "/dev/$device" "$ROOTFS/dev/$device"; MOUNTS+=("$ROOTFS/dev/$device")
    done
    mkdir -p "$ROOTFS/dev/pts" "$ROOTFS/dev/shm"
    mount -t devpts -o newinstance,ptmxmode=0666,mode=0620 devpts "$ROOTFS/dev/pts"
    MOUNTS+=("$ROOTFS/dev/pts")
    ln -s pts/ptmx "$ROOTFS/dev/ptmx"
    ln -s /proc/self/fd "$ROOTFS/dev/fd"
    mount -t proc proc "$ROOTFS/proc"; MOUNTS+=("$ROOTFS/proc")
    mount --bind /sys "$ROOTFS/sys"; MOUNTS+=("$ROOTFS/sys")
    mount -o remount,bind,ro "$ROOTFS/sys"
    touch "$ROOTFS/run/piforge-build-guest"
    mkdir -p "$ROOTFS/opt/piforge" "$ROOTFS/var/log/piforge"
    cp -a "$PIFORGE_ROOT/scripts" "$PIFORGE_ROOT/configs" "$ROOTFS/opt/piforge/"
    cp -a "$ROOTFS/etc/resolv.conf" "$WORK/resolv.conf"
    rm "$ROOTFS/etc/resolv.conf"
    cp -L /etc/resolv.conf "$ROOTFS/etc/resolv.conf"
    DNS_CHANGED=1
    if [[ -e $ROOTFS/usr/sbin/policy-rc.d ]]; then
        cp -a "$ROOTFS/usr/sbin/policy-rc.d" "$WORK/policy-rc.d"
    fi
    printf '#!/bin/sh\nexit 101\n' > "$ROOTFS/usr/sbin/policy-rc.d"
    chmod 755 "$ROOTFS/usr/sbin/policy-rc.d"
    POLICY_CHANGED=1
}
