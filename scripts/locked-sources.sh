#!/usr/bin/env bash
# Upstream supplies these variables and declares __mod_info as associative.
# shellcheck disable=SC2154,SC2004
# Loaded by a generated copy of upstream's entry point AFTER module registration.
# Do not enable nounset/errexit here: upstream uses explicit module error reporting.

gitPullOrClone() {
    local dir="${1:-$md_build}" repo="${2:-}" commit actual
    if [[ -z $repo ]]; then repo=$(rp_resolveRepoParam "$md_repo_url"); fi
    commit=$(python3 /opt/piforge/scripts/config.py lookup "$repo") || exit 1
    if [[ -z ${__mod_info[$md_id/repo_dir]} ]]; then __mod_info[$md_id/repo_dir]="$dir"; fi
    if [[ ! -d $dir/.git ]]; then
        mkdir -p "$dir" && git -C "$dir" init && git -C "$dir" remote add origin "$repo" || exit 1
    fi
    # Fetch the immutable object directly, then resolve submodules at that object.
    # Branch tips are never build inputs, even when upstream supplies a branch.
    git -C "$dir" -c protocol.file.allow=never fetch --depth=1 origin "$commit" || exit 1
    git -C "$dir" checkout --detach --force "$commit" || exit 1
    git -C "$dir" -c protocol.file.allow=never submodule update --init --recursive --depth=1 || exit 1
    actual=$(git -C "$dir" rev-parse HEAD) || exit 1
    [[ $actual == "$commit" ]] || exit 1
    python3 /opt/piforge/scripts/record-source.py "$repo" "$dir" "$commit" || exit 1
}

install_minimal_assets_retroarch() {
    # Replace the moving, unversioned minimal-assets archive with a pinned
    # checkout of the official UI assets repository. These are not game assets.
    local dir="$configdir/all/retroarch/assets"
    gitPullOrClone "$dir" https://github.com/libretro/retroarch-assets.git || return 1
    chown -R "$__user:$__group" "$dir"
}

rpSwap() {
    # Swap belongs to the Linux build host, never to a guest image. Creating
    # swap here would mutate the shared host kernel. Low memory fails clearly.
    if [[ $1 == on && $__memory_avail -lt $2 ]]; then
        __ERRMSGS+=("Insufficient build host memory: need $2 MiB available; configure host swap/RAM")
        return 1
    fi
    return 0
}
