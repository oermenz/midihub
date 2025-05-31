#!/bin/bash

set -e

# VARIABLES
USER_NAME="oermens"
USER_HOME="/home/$USER_NAME"
REPO_DIR="$USER_HOME/midihub"
VENV_DIR="$REPO_DIR/venv"

# ENABLE i2C + UART
sudo raspi-config nonint do_i2c 0
sudo raspi-config nonint do_serial 1

# VENV
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

# COPY FILES
echo "==> Copying service and target files..."
for SERVICE in midihub.service midioled.service midihub.target; do
    sudo cp "$REPO_DIR/services/$SERVICE" /etc/systemd/system/
done

echo "==> Copying udev rules for MIDI devices..."
for RULES in 11-midihub.rules; do
    sudo cp "$REPO_DIR/$RULES" /etc/udev/rules.d/
done

# /TMP TO RAM)
if ! mount | grep -qE '^tmpfs on /tmp '; then
    echo "Mounting /tmp as tmpfs (RAM disk)..."
    # Add to /etc/fstab if not already present
    if ! grep -qE '^tmpfs\s+/tmp\s+tmpfs' /etc/fstab; then
        echo 'tmpfs   /tmp    tmpfs   defaults,noatime,nosuid,nodev,mode=1777,size=100M  0  0' | sudo tee -a /etc/fstab
    fi
    sudo mount -o remount /tmp
    echo "/tmp is now using RAM (tmpfs)."
else
    echo "/tmp is already mounted as tmpfs."
fi

# RELOAD/ENABLE
echo "==> Reloading udev rules..."
sudo udevadm control --reload-rules
sudo udevadm trigger

echo "==> Reloading systemd..."
sudo systemctl daemon-reload

echo "==> Enabling services and target for user: $USER_NAME"
sudo systemctl enable midihub.service midioled.service midihub.target

# FINISH
echo
read -p "==> Setup complete. Reboot now? [y/N] " response
if [[ "$response" =~ ^[Yy]$ ]]; then
    echo "Rebooting..."
    sudo reboot now
else
    echo "==> Reboot skipped."
fi
