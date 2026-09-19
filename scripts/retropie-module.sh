#!/usr/bin/env bash
# shellcheck source=scripts/common.sh
source "$(dirname "$0")/common.sh"
guest_only
module=${1:?Usage: retropie-module.sh MODULE [ACTION]}
action=${2:-_source_}
[[ $module =~ ^[a-z0-9-]+$ && $action =~ ^[a-z_]+$ ]] || die "Invalid module/action"
log "RetroPie module $module: $action"
export __platform=rpi5 __has_kms=1 __has_binaries=0 __user=pi __nodialog=1
export __makeflags="-j$BUILD_JOBS"
cd /opt/RetroPie-Setup || exit
# Upstream has its own error accounting and is intentionally a child shell.
bash ./piforge_packages.sh "$module" "$action" 2>&1 | tee "/var/log/piforge/$module-$action.log"
