#!/bin/bash

echo "🔧 Starting Midihub setup..."

# Ensure script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "❌ Please run as root: sudo ./setup.sh"
  exit 1
fi

# Variables
USER_NAME="oermens"
MIDIHUB_DIR="/home/$USER_NAME/midihub"
VENV_DIR="$MIDIHUB_DIR/venv"

# 1. Enable I2C interface
echo "🔌 Enabling I²C interface..."
raspi-config nonint do_i2c 0

# 2. Update and install system dependencies
echo "📦 Installing system dependencies..."
apt update
apt install -y python3 python3-pip python3-venv libcairo2-dev pkg-config python3-dev git i2c-tools libffi-dev libjpeg-dev zlib1g-dev libfreetype6-dev python3-gi gir1.2-gtk-3.0 libgirepository1.0-dev

# 3. Clone repo (if not already cloned)
if [ ! -d "$MIDIHUB_DIR" ]; then
  echo "📂 Cloning midihub repository..."
  sudo -u $USER_NAME git clone https://github.com/oermenz/midihub.git "$MIDIHUB_DIR"
else
  echo "📂 Midihub directory exists, skipping clone."
fi

# 4. Create Python virtual environment
echo "🐍 Creating Python virtual environment..."
sudo python3 -m venv --system-site-packages "$VENV_DIR"

# 5. Upgrade pip and install python packages inside venv
echo "📦 Installing Python packages inside virtual environment..."
sudo -u $USER_NAME "$VENV_DIR/bin/pip" install --upgrade pip
sudo -u $USER_NAME "$VENV_DIR/bin/pip" install mido python-rtmidi adafruit-circuitpython-ssd1306 Pillow pydbus

# 6. Copy systemd service file and enable it
echo "📂 Setting up systemd service..."
cp "$MIDIHUB_DIR/midihub.service" /etc/systemd/system/midihub.service
chmod 644 /etc/systemd/system/midihub.service

# Reload systemd, enable and start service
systemctl daemon-reload
systemctl enable midihub.service
systemctl restart midihub.service

# 7. Reboot prompt
echo "✅ Setup complete. Reboot recommended."
read -p "Would you like to reboot now? (y/n): " confirm
if [[ "$confirm" =~ ^[Yy]$ ]]; then
  reboot
fi
