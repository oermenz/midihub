#!/bin/bash

set -e

# ==== VARIABLES ====
USER_NAME="$(whoami)"
USER_HOME="$HOME"
REPO_DIR="$USER_HOME/midihub"
VENV_DIR="$REPO_DIR/venv"
GREEN='\033[0;32m'
RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

# ==== ENABLE i2C + UART ====
echo "==> Enabeling i2c and UART pins..."
sudo raspi-config nonint do_i2c 0
sudo raspi-config nonint do_serial 1

# ==== CREATE VENV ====
echo "==> Creating Python virtual environment..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# ==== SYSTEM DEPENDENCIES ====
if [ -f "$REPO_DIR/dependencies.txt" ]; then
    echo "==> Installing system dependencies..."
    sudo apt update
    xargs -a "$REPO_DIR/dependencies.txt" sudo apt install -y
fi

# ==== PYTHON REQUIREMENTS ====
if [ -f "$REPO_DIR/requirements.txt" ]; then
    echo "==> Installing Python requirements..."
    pip install -r "$REPO_DIR/requirements.txt"
fi

# ==== COPY FILES ====
echo "==> Copying service and target files..."
for SERVICE in midihub.service midioled.service midihub.target; do
    sed "s|__USERNAME__|$USER_NAME|g" "$REPO_DIR/services/$SERVICE" | sudo tee "/etc/systemd/system/$SERVICE" > /dev/null
done

echo "==> Copying udev rules for MIDI devices..."
for RULES in 11-midihub.rules; do
    sudo cp "$REPO_DIR/$RULES" /etc/udev/rules.d/
done

# ==== RELOAD/ENABLE ====
echo "==> Reloading udev rules..."
sudo udevadm control --reload-rules
sudo udevadm trigger

echo "==> Reloading systemd..."
sudo systemctl daemon-reload

echo "==> Enabling services and target for user: $USER_NAME"
sudo systemctl enable midihub.service midioled.service midihub.target

# ==== ALIASES ====
echo "==> Creating aliases for readonly.sh toggle..."
BASHRC="$HOME/.bashrc"
if ! grep -q 'alias SETRO=' "$BASHRC"; then
    echo "alias SETRO='sudo ~/midihub/readonly.sh RO'" >> "$BASHRC"
    echo "Added alias: SETRO (set system to read-only mode)"
fi
if ! grep -q 'alias SETRW=' "$BASHRC"; then
    echo "alias SETRW='sudo ~/midihub/readonly.sh RW'" >> "$BASHRC"
    echo "Added alias: SETRW (set system to read-write mode)"
fi

source "$BASHRC"

echo
echo -e "==> You can now use '${BOLD}${GREEN}SETRO${RESET}' to set the system to read-only mode and '${BOLD}${RED}SETRW${RESET}' to revert to read-write mode."
echo

# ==== FINISH ====
echo
read -p "==> Setup complete. Reboot required. Reboot now? [y/N] " response
if [[ "$response" =~ ^[Yy]$ ]]; then
    echo "Rebooting..."
    sudo reboot now
else
    echo "==> Reboot skipped."
fi
