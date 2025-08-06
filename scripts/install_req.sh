#!/usr/bin/env bash

set -e
set -x

function apt_install() {
    if ! dpkg -s "$@" >/dev/null 2>&1; then
        if [ "$(find /var/lib/apt/lists/* | wc -l)" = "0" ]; then
            apt-get update || { echo "apt-get update failed"; exit 1; }
        fi
        apt-get install -y --no-install-recommends "$@" || { echo "apt-get install failed"; exit 1; }
    fi
}

echo "Installing packages..."
apt_install \
    build-essential \
    curl

echo "Upgrading pip..."
python3 -m pip --no-cache-dir install --upgrade pip || { echo "Failed to upgrade pip"; exit 1; }

echo "Installing requirements..."
python3 -m pip --no-cache-dir install --upgrade -r requirements.txt || { echo "Failed to install requirements"; exit 1; }

echo "Script completed successfully"
