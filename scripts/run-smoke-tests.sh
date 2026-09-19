#!/usr/bin/env bash
# shellcheck source=scripts/common.sh
source "$(dirname "$0")/common.sh"
guest_only
log "Build-time image content and linkage checks"
python3 "$PIFORGE_ROOT/scripts/smoke.py" 2>&1 | tee /var/log/piforge/smoke.log
