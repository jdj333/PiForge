#!/usr/bin/env bash
# shellcheck source=scripts/common.sh
source "$(dirname "$0")/common.sh"
[[ $(uname -s) == Linux && $(uname -m) == aarch64 ]] || die "Use a native ARM64 Linux host/VM"
[[ $EUID -eq 0 ]] || die "Run with sudo on a dedicated build host"
if [[ ${1:-} != --in-mount-namespace ]]; then
    [[ $# -eq 0 ]] || die "Usage: build-image.sh"
    exec unshare --mount --propagation private "$0" --in-mount-namespace
fi
[[ $# -eq 1 ]] || die "Unexpected arguments"
for tool in curl xz sha256sum sfdisk losetup blkid e2fsck resize2fs tune2fs mount umount \
    chroot truncate python3 git flock findmnt; do
    command -v "$tool" >/dev/null || die "Missing host tool: $tool"
done
mkdir -p "$PIFORGE_ROOT/build" "$PIFORGE_ROOT/dist"
exec 9> "$PIFORGE_ROOT/build/.lock"
flock -n 9 || die "Another PiForge build is running"
[[ -z $(git -C "$PIFORGE_ROOT" status --porcelain) ]] || die "Commit changes first: image provenance requires a clean checkout"
PIFORGE_COMMIT=$(git -C "$PIFORGE_ROOT" rev-parse HEAD)
BUILD_DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ)
export PIFORGE_COMMIT BUILD_DATE
WORK=$(mktemp -d "$PIFORGE_ROOT/build/run.XXXXXX")
ROOTFS="$WORK/rootfs"
IMAGE="$WORK/$OUTPUT_IMAGE_NAME.img"
ARTIFACT_DIR="$PIFORGE_ROOT/dist/${OUTPUT_IMAGE_NAME}-${BUILD_VERSION}-${PIFORGE_COMMIT:0:12}-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir "$ARTIFACT_DIR"
exec > >(tee "$ARTIFACT_DIR/build.log") 2>&1
log "Build $BUILD_VERSION, PiForge $PIFORGE_COMMIT; work directory $WORK"
LOOP='' DNS_CHANGED=0 POLICY_CHANGED=0
MOUNTS=()
restore_guest() {
    if [[ $DNS_CHANGED == 1 ]]; then
        rm -f "$ROOTFS/etc/resolv.conf" || return 1
        cp -a "$ROOTFS/run/piforge-backup/resolv.conf" "$ROOTFS/etc/resolv.conf" || return 1
        DNS_CHANGED=0
    fi
    if [[ $POLICY_CHANGED == 1 ]]; then
        rm -f "$ROOTFS/usr/sbin/policy-rc.d" || return 1
        if [[ -e $ROOTFS/run/piforge-backup/policy-rc.d ]]; then
            cp -a "$ROOTFS/run/piforge-backup/policy-rc.d" "$ROOTFS/usr/sbin/policy-rc.d" || return 1
        fi
        POLICY_CHANGED=0
    fi
}
unmount_image() {
    local index
    for ((index=${#MOUNTS[@]}-1; index>=0; index--)); do
        umount "${MOUNTS[index]}" || return 1
        unset 'MOUNTS[index]'
    done
    if [[ -n $LOOP ]]; then losetup -d "$LOOP" || return 1; LOOP=; fi
}
cleanup() {
    local status=$?
    trap - EXIT INT TERM
    set +e
    if [[ -d $ROOTFS/var/log/piforge ]]; then
        mkdir -p "$ARTIFACT_DIR/guest-logs"
        cp -R --no-preserve=ownership "$ROOTFS/var/log/piforge/." "$ARTIFACT_DIR/guest-logs/" || status=1
    fi
    if ! restore_guest; then status=1; log "Failed to restore guest temporary configuration"; fi
    if ! unmount_image; then
        status=1
        log "Cleanup failed. Inspect $WORK and $LOOP; no forced/lazy unmount was attempted."
    fi
    [[ $status -eq 0 ]] || log "Build failed ($status); retained work and logs at $WORK and $ARTIFACT_DIR"
    exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'printf "[PiForge] Failed at line %s: %s\n" "$LINENO" "$BASH_COMMAND" >&2' ERR
bash "$PIFORGE_ROOT/scripts/download-base-image.sh" "$PIFORGE_ROOT/build/cache"
xz --decompress --stdout "$PIFORGE_ROOT/build/cache/$BASE_IMAGE_SHA256.img.xz" > "$IMAGE"
source "$PIFORGE_ROOT/scripts/prepare-image.sh"
prepare_image
guest() {
    chroot "$ROOTFS" /usr/bin/env -i PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
        HOME=/root TERM=linux LC_ALL=C.UTF-8 DEBIAN_FRONTEND=noninteractive \
        PIFORGE_COMMIT="$PIFORGE_COMMIT" BUILD_DATE="$BUILD_DATE" \
        /bin/bash "/opt/piforge/scripts/$1"
}
guest install-retropie.sh
guest install-emulators.sh
guest configure-pi5.sh
guest run-smoke-tests.sh
guest finalize-image.sh
cp "$ROOTFS/etc/piforge-build-info.json" "$ARTIFACT_DIR/$OUTPUT_IMAGE_NAME.build-info.json"
mkdir -p "$ARTIFACT_DIR/guest-logs"
cp -R --no-preserve=ownership "$ROOTFS/var/log/piforge/." "$ARTIFACT_DIR/guest-logs/"
restore_guest
sync
unmount_image
source "$PIFORGE_ROOT/scripts/shrink-image.sh"
shrink_image
log "Compress image and generate SHA256"
xz -T "$BUILD_JOBS" -6 --stdout "$IMAGE" > "$ARTIFACT_DIR/$OUTPUT_IMAGE_NAME.img.xz.partial"
mv "$ARTIFACT_DIR/$OUTPUT_IMAGE_NAME.img.xz.partial" "$ARTIFACT_DIR/$OUTPUT_IMAGE_NAME.img.xz"
(
    cd "$ARTIFACT_DIR" || exit
    sha256sum "$OUTPUT_IMAGE_NAME.img.xz" "$OUTPUT_IMAGE_NAME.build-info.json" > "$OUTPUT_IMAGE_NAME.sha256"
    sha256sum --check "$OUTPUT_IMAGE_NAME.sha256"
)
rm "$IMAGE"
log "Image artifacts ready: $ARTIFACT_DIR"
