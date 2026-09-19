#!/usr/bin/env bash
# Sourced only after unmounting; preserves the DOS disk identifier/PARTUUIDs.
shrink_image() {
    log "Shrink root filesystem with ${SHRINK_HEADROOM_MIB} MiB free headroom"
    LOOP=$(losetup --find --show --partscan "$IMAGE")
    wait_loop_partitions "$LOOP"
    check_ext4 "${LOOP}p2"
    resize2fs -M "${LOOP}p2"
    local blocks block_size target_blocks sectors image_bytes
    blocks=$(tune2fs -l "${LOOP}p2" | awk '/^Block count:/ {print $3}')
    block_size=$(tune2fs -l "${LOOP}p2" | awk '/^Block size:/ {print $3}')
    target_blocks=$((blocks + SHRINK_HEADROOM_MIB * 1024 * 1024 / block_size))
    resize2fs "${LOOP}p2" "$target_blocks"
    check_ext4 "${LOOP}p2"
    sectors=$((target_blocks * block_size / 512))
    losetup -d "$LOOP"; LOOP=
    printf '%s,%s\n' "$ROOT_START" "$sectors" | sfdisk --no-reread -N 2 "$IMAGE"
    image_bytes=$(((ROOT_START + sectors) * 512))
    truncate -s "$image_bytes" "$IMAGE"
    sfdisk --verify "$IMAGE"
}
