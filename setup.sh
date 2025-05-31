#!/bin/bash

set -e

# ==== VARIABLES ====
USER_NAME="$(whoami)"
USER_HOME="$HOME"
REPO_DIR="$USER_HOME/hookup"
VENV_DIR="$REPO_DIR/venv"
YELLOW='\033[0;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

# ==== ENABLE i2C + UART ====
echo "==> Enabling i2c and UART pins..."
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

# ==== INSTALL SYSTEMD SERVICES (with prompts) ====
REQUIRED_SERVICE="midiup.service"
OPTIONAL_SERVICES=("audioup.service" "oledup.service")
TARGET_SERVICE="hookup.target"

# Required service check and install
if [ ! -f "$REPO_DIR/services/$REQUIRED_SERVICE" ]; then
    echo -e "${RED}Error:${RESET} $REQUIRED_SERVICE is required but not found in $REPO_DIR/services."
    exit 1
fi
sed "s|__USERNAME__|$USER_NAME|g" "$REPO_DIR/services/$REQUIRED_SERVICE" | sudo tee "/etc/systemd/system/$REQUIRED_SERVICE" > /dev/null
ENABLED_SERVICES=("$REQUIRED_SERVICE")

# Optional services
for SERVICE in "${OPTIONAL_SERVICES[@]}"; do
    if [ -f "$REPO_DIR/services/$SERVICE" ]; then
        read -p "==> Do you want to install and enable $SERVICE? [y/N] " response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            sed "s|__USERNAME__|$USER_NAME|g" "$REPO_DIR/services/$SERVICE" | sudo tee "/etc/systemd/system/$SERVICE" > /dev/null
            ENABLED_SERVICES+=("$SERVICE")
        else
            echo "Skipping $SERVICE."
        fi
    else
        echo "Optional $SERVICE not found, skipping."
    fi
done

# Always install the target unit if present
if [ -f "$REPO_DIR/services/$TARGET_SERVICE" ]; then
    sed "s|__USERNAME__|$USER_NAME|g" "$REPO_DIR/services/$TARGET_SERVICE" | sudo tee "/etc/systemd/system/$TARGET_SERVICE" > /dev/null
    ENABLED_SERVICES+=("$TARGET_SERVICE")
fi

echo "==> Enabling present services and targets: ${ENABLED_SERVICES[*]}"
sudo systemctl enable "${ENABLED_SERVICES[@]}"

# ==== ALIASES ====
echo "==> Creating aliases for readonly.sh toggle..."
BASHRC="$HOME/.bashrc"
if ! grep -q 'alias SETRO=' "$BASHRC"; then
    echo "alias SETRO='sudo ~/hookup/readonly.sh RO'" >> "$BASHRC"
    echo "Added alias: SETRO (set system to read-only mode)"
fi
if ! grep -q 'alias SETRW=' "$BASHRC"; then
    echo "alias SETRW='sudo ~/hookup/readonly.sh RW'" >> "$BASHRC"
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
