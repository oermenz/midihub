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

echo "==> Installing Python requirements..."
pip install --upgrade pip
if [ -f "$REPO_DIR/dependencies.txt" ]; then
    pip install -r "$REPO_DIR/dependencies.txt"
fi
if [ -f "$REPO_DIR/requirements.txt" ]; then
    pip install -r "$REPO_DIR/requirements.txt"
fi

echo "==> Copying service and target files..."
for SERVICE in midihub.service midioled.service midihub.target; do
    sudo cp "$REPO_DIR/services/$SERVICE" /etc/systemd/system/
done

echo "==> Copying udev rules for MIDI devices..."
UDEV_RULES_SRC="$REPO_DIR/services"
UDEV_RULES_DST="/etc/udev/rules.d"

for RULE in 33-midiusb.rules 33-midibt.rules; do
    if [ -f "$UDEV_RULES_SRC/$RULE" ]; then
        sudo cp "$UDEV_RULES_SRC/$RULE" "$UDEV_RULES_DST/"
        echo "  - Copied $RULE"
    else
        echo "  - Warning: $RULE not found in $UDEV_RULES_SRC"
    fi
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
