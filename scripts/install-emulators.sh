#!/usr/bin/env bash
# shellcheck source=scripts/common.sh
source "$(dirname "$0")/common.sh"
guest_only
emulators=$(python3 "$PIFORGE_ROOT/scripts/config.py" emulators)
while IFS= read -r module; do
    bash "$PIFORGE_ROOT/scripts/retropie-module.sh" "$module"
    python3 "$PIFORGE_ROOT/scripts/smoke.py" --component "$module"
done <<< "$emulators"
