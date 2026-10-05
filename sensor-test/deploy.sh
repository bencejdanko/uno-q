#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
APP=$(basename "$PWD")
DEST=/home/arduino/ArduinoApps/$APP
PASS=/home/bence/uno-q/.ssh_pass
IP=192.168.1.69

remote() {
    sshpass -f "$PASS" ssh -o StrictHostKeyChecking=no arduino@$IP "$1"
}
remote_in() {
    sshpass -f "$PASS" ssh -o StrictHostKeyChecking=no arduino@$IP "$1"
}

if [[ "${1:-}" == "logs" ]]; then
    remote "arduino-app-cli app logs $DEST"
    exit
fi

echo "Syncing $APP to $IP..."
remote "mkdir -p $DEST && rm -rf $DEST/python $DEST/sketch"
tar -c --exclude=deploy.sh --exclude='.cache' --exclude='__pycache__' . | remote_in "tar -x -C $DEST"

echo "Stopping other running apps..."
remote "for id in \$(arduino-app-cli app list | awk '/ running /{print \$1}'); do
    [ \"\$id\" = user:$APP ] || arduino-app-cli app stop \"\$id\"; done"

echo "Deploying and restarting $APP..."
remote "arduino-app-cli app restart $DEST"
