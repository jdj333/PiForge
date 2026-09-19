#!/usr/bin/env bash
# shellcheck source=scripts/common.sh
source "$(dirname "$0")/common.sh"
guest_only
log "Record build provenance and clean temporary files"
python3 "$PIFORGE_ROOT/scripts/build-metadata.py"
# Upstream starts a key agent even for source installs. Stop only agents in
# this guest before removing their sockets, so they cannot keep root mounted.
gpgconf --kill all
apt-get clean
rm -f /etc/apt/preferences.d/piforge
rm -f /root/.gitconfig
rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* /root/.cache /root/.gnupg
rm -rf /opt/RetroPie-Setup/tmp
rm -f /opt/RetroPie-Setup/piforge_packages.sh
# Preserve installed UI resources and license files, remove only Git history.
find /opt/retropie /etc/emulationstation -type d -name .git -prune -exec rm -rf '{}' +
rm -f /root/.bash_history /home/pi/.bash_history /etc/ssh/ssh_host_*
truncate -s 0 /etc/machine-id
if [[ -f /var/lib/dbus/machine-id && ! -L /var/lib/dbus/machine-id ]]; then truncate -s 0 /var/lib/dbus/machine-id; fi
rm -f /var/lib/systemd/random-seed
find /var/log -type f ! -path '/var/log/piforge/*' -exec truncate -s 0 '{}' +
sync
