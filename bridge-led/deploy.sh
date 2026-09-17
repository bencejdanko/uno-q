#!/usr/bin/env bash
# Sync this app to the UNO Q and (re)start it.
#   ./deploy.sh            # over USB (adb)
#   UNOQ_SSH=arduino@172.20.10.3 ./deploy.sh   # over Wi-Fi (ssh)
#   ./deploy.sh logs       # follow Python logs
set -euo pipefail
cd "$(dirname "$0")"
APP=$(basename "$PWD")
DEST=/home/arduino/ArduinoApps/$APP
ADB=${ADB:-$HOME/.arduino15/packages/arduino/tools/adb/32.0.0/adb}

remote() {
    if [[ -n "${UNOQ_SSH:-}" ]]; then ssh "$UNOQ_SSH" "$1"; else "$ADB" shell "export TMPDIR=/tmp; $1"; fi
}
remote_in() {  # like remote, but forwards stdin
    if [[ -n "${UNOQ_SSH:-}" ]]; then ssh "$UNOQ_SSH" "$1"; else "$ADB" shell -T "$1"; fi
}

if [[ "${1:-}" == "logs" ]]; then
    remote "arduino-app-cli app logs $DEST"
    exit
fi

remote "mkdir -p $DEST && rm -rf $DEST/python $DEST/sketch"
tar -c --exclude=deploy.sh --exclude='.cache' --exclude='__pycache__' . | remote_in "tar -x -C $DEST"
# Only one app can run at a time: stop any other running app first.
remote "for id in \$(arduino-app-cli app list | awk '/ running /{print \$1}'); do
    [ \"\$id\" = user:$APP ] || arduino-app-cli app stop \"\$id\"; done"
remote "arduino-app-cli app restart $DEST"
