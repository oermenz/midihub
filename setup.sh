#!/bin/bash

set -e

# Variables
USER_NAME="oermens"
USER_HOME="/home/$USER_NAME"
REPO_DIR="$USER_HOME/midihub"
VENV_DIR="$REPO_DIR/venv"

echo "==> Creating Python virtual environment..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# SYSTEM DEPENDENCIES
if [ -f "$REPO_DIR/dependencies.txt" ]; then
    echo "==> Installing system dependencies..."
    sudo apt update
    xargs -a "$REPO_DIR/dependencies.txt" sudo apt install -y
fi

# PYTHON DEPENDENCIES
if [ -f "$REPO_DIR/requirements.txt" ]; then
    echo "==> Installing Python requirements..."
    pip install -r "$REPO_DIR/requirements.txt"
fi

echo "==> Copying service and target files..."
for SERVICE in midihub.service midioled.service midihub.target; do
    sudo cp "$REPO_DIR/services/$SERVICE" /etc/systemd/system/
done

echo "==> Copying udev rules for MIDI devices..."
for RULES in 11-midihub.rules; do
    sudo cp "$REPO_DIR/$RULES" /etc/udev/rules.d/
done

echo "==> Reloading udev rules..."
sudo udevadm control --reload-rules
sudo udevadm trigger

echo "==> Reloading systemd..."
sudo systemctl daemon-reload

echo "==> Enabling services and target for user: $USER_NAME"
sudo systemctl enable midihub.service midioled.service midihub.target

echo "==> Setup complete."
echo "You can now start the full stack with:"
echo "sudo systemctl start midihub.target"
