#!/usr/bin/env bash
# shellcheck source=scripts/common.sh
source "$(dirname "$0")/common.sh"
cache=${1:?Usage: download-base-image.sh CACHE_DIRECTORY}
mkdir -p "$cache"
image="$cache/$BASE_IMAGE_SHA256.img.xz"
verify() { printf '%s  %s\n' "$BASE_IMAGE_SHA256" "$1" | sha256sum --check --status; }
log "Download and verify official Raspberry Pi OS $BASE_IMAGE_VERSION"
if [[ -e $image ]]; then
    verify "$image" || die "Cached image checksum mismatch: $image (remove it and retry)"
else
    trap 'rm -f -- "$image.part"' EXIT
    curl --fail --location --retry 3 --proto '=https' --proto-redir '=https' \
        "$BASE_IMAGE_URL" -o "$image.part"
    verify "$image.part" || die "Downloaded image checksum mismatch"
    mv -- "$image.part" "$image"
fi
xz --test "$image"
log "Verified $image"
