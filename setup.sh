#!/bin/bash

echo "🔧 Starting Midihub setup..."

# Ensure the script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "❌ Please run as root: sudo ./setup.sh"
  exit 1
fi

# Variables
USER_NAME="oermens"
USER_HOME="/home/$USER_NAME"
MIDIHUB_DIR="$USER_HOME/midihub"
VENV_DIR="$MIDIHUB_DIR/venv"
SERVICE_DIR="/etc/systemd/system"

# 1. Enable I²C and UART interfaces
echo "🔌 Enabling I²C and UART interfaces..."
raspi-config nonint do_i2c 0
raspi-config nonint do_serial_hw 0
raspi-config nonint do_serial_cons 1

# 2. Update and install system dependencies
echo "📦 Installing system dependencies..."
apt update

DEPENDENCIES_FILE="$MIDIHUB_DIR/dependencies.txt"
if [ -f "$DEPENDENCIES_FILE" ]; then
  xargs -a "$DEPENDENCIES_FILE" apt install -y
else
  echo "⚠️ Warning: $DEPENDENCIES_FILE not found. Skipping system dependencies installation."
fi

# 3. Clone the repository if it doesn't exist
if [ ! -d "$MIDIHUB_DIR" ]; then
  echo "📂 Cloning midihub repository..."
  su - "$USER_NAME" -c "git clone https://github.com/oermenz/midihub.git '$MIDIHUB_DIR'"
else
  echo "📂 Midihub directory exists, skipping clone."
fi

# 4. Create Python virtual environment
echo "🐍 Creating Python virtual environment..."
su - "$USER_NAME" -c "python3 -m venv --system-site-packages '$VENV_DIR'"

# 5. Upgrade pip and install Python packages inside venv
echo "📦 Installing Python packages inside virtual environment..."
REQUIREMENTS_FILE="$MIDIHUB_DIR/requirements.txt"
if [ -f "$REQUIREMENTS_FILE" ]; then
  su - "$USER_NAME" -c "'$VENV_DIR/bin/pip' install --upgrade pip"
  su - "$USER_NAME" -c "'$VENV_DIR/bin/pip' install -r '$REQUIREMENTS_FILE'"
else
  echo "⚠️ Warning: $REQUIREMENTS_FILE not found. Skipping Python package installation."
fi

# 6. Copy systemd service and target files
echo "📂 Setting up systemd services and target..."
cp "$MIDIHUB_DIR/services/midihub.service" "$SERVICE_DIR/"
cp "$MIDIHUB_DIR/services/midioled.service" "$SERVICE_DIR/"
cp "$MIDIHUB_DIR/services/midihub.target" "$SERVICE_DIR/"
chmod 644 "$SERVICE_DIR/midihub.service" "$SERVICE_DIR/midioled.service" "$SERVICE_DIR/midihub.target"

# 7. Reload systemd, enable and start services
echo "🔄 Reloading systemd daemon and enabling services..."
systemctl daemon-reload
systemctl enable midihub.service
systemctl enable midioled.service
systemctl enable midihub.target
systemctl restart midihub.target

# 8. Reboot prompt
echo "✅ Setup complete. A reboot is recommended."
read -p "Would you like to reboot now? (y/n): " confirm
if [[ "$confirm" =~ ^[Yy]$ ]]; then
  reboot now
fi
