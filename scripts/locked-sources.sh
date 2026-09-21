#!/usr/bin/env bash
# Upstream supplies these variables and declares __mod_info as associative.
# shellcheck disable=SC2154,SC2004
# Loaded by a generated copy of upstream's entry point AFTER module registration.
# Do not enable nounset/errexit here: upstream uses explicit module error reporting.

gitPullOrClone() {
    local dir="${1:-$md_build}" repo="${2:-}" commit actual
    # Upstream deliberately owns configuration directories as pi. Trust only
    # this exact reviewed destination, never a global safe.directory wildcard.
    local git_command=(git -c "safe.directory=$dir" -C "$dir")
    if [[ -z $repo ]]; then repo=$(rp_resolveRepoParam "$md_repo_url"); fi
    commit=$(python3 "${PIFORGE_ROOT:-/opt/piforge}/scripts/config.py" lookup "$repo") || exit 1
    if [[ -z ${__mod_info[$md_id/repo_dir]} ]]; then __mod_info[$md_id/repo_dir]="$dir"; fi
    if [[ ! -d $dir/.git ]]; then
        mkdir -p "$dir" && "${git_command[@]}" init && "${git_command[@]}" remote add origin "$repo" || exit 1
    fi
    # Fetch the immutable object directly, then resolve submodules at that object.
    # Branch tips are never build inputs, even when upstream supplies a branch.
    local cache="${PIFORGE_GIT_CACHE:-/var/cache/piforge-git}/$commit.git"
    [[ -d $cache ]] || { printf 'Missing pinned source cache: %s\n' "$commit" >&2; exit 1; }
    # Local upload-pack does not inherit command-line trust configuration.
    # This exact immutable cache is mounted read-only by the orchestrator.
    git config --global --add safe.directory "$cache" || exit 1
    "${git_command[@]}" -c protocol.file.allow=always fetch --depth=1 --update-shallow "$cache" "$commit" || exit 1
    "${git_command[@]}" checkout --detach --force "$commit" || exit 1
    if [[ -f $dir/.gitmodules ]]; then
        "${git_command[@]}" -c protocol.file.allow=never submodule update --init --recursive --depth=1 || exit 1
    fi
    actual=$("${git_command[@]}" rev-parse HEAD) || exit 1
    [[ $actual == "$commit" ]] || exit 1
    python3 "${PIFORGE_ROOT:-/opt/piforge}/scripts/record-source.py" "$repo" "$dir" "$commit" || exit 1
}

install_minimal_assets_retroarch() {
    # Replace the moving, unversioned minimal-assets archive with a pinned
    # checkout of the official UI assets repository. These are not game assets.
    local dir="$configdir/all/retroarch/assets"
    gitPullOrClone "$dir" https://github.com/libretro/retroarch-assets.git || return 1
    # Match the three directories in upstream's minimal-assets packaging.
    git -c "safe.directory=$dir" -C "$dir" sparse-checkout set --cone \
        ozone menu_widgets xmb/monochrome || return 1
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
