#!/usr/bin/env bash
set -Eeuo pipefail
[[ $EUID -eq 0 ]] || exit 1
[[ -e /var/lib/piforge/firstboot-complete ]] && exit 0
# Deliberately local-console-only. Do not store a password in an image or log.
printf '\nPiForge first boot: set a password for the local pi account.\n'
passwd pi
mkdir -p /var/lib/piforge
touch /var/lib/piforge/firstboot-complete
