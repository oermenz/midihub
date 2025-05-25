# setup.sh - Script to install and configure Midihub
#!/bin/bash

set -e

REPO_DIR=$(dirname "$(realpath "$0")")

echo "Installing system dependencies..."
sudo apt-get update
xargs -a "$REPO_DIR/dependencies.txt" sudo apt-get install -y

echo "Installing Python packages..."
pip3 install -r "$REPO_DIR/requirements.txt"

echo "Copying udev rules..."
sudo cp "$REPO_DIR"/33-midiusb.rules /etc/udev/rules.d/
sudo cp "$REPO_DIR"/44-midibt.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger

echo "Copying Python scripts..."
sudo cp "$REPO_DIR"/midioled.py /usr/local/bin/
sudo cp "$REPO_DIR"/midihub.py /usr/local/bin/

sudo chmod +x /usr/local/bin/midioled.py
sudo chmod +x /usr/local/bin/midihub.py

echo "Setup complete. Reboot recommended."
