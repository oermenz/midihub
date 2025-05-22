#!/bin/bash

echo "🔧 Starting Midihub setup..."

# Ensure script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "❌ Please run as root: sudo ./setup.sh"
  exit
fi

# 1. Enable I2C
echo "🔌 Enabling I²C interface..."
raspi-config nonint do_i2c 0

# 2. Update and install system packages
echo "📦 Installing system dependencies..."
apt update
apt install -y python3 python3-pip python3-venv git i2c-tools libffi-dev libjpeg-dev zlib1g-dev libfreetype6-dev

# 3. Optional: Set up a Python virtual environment (can skip if using system Python)
# echo "🐍 Setting up virtual environment..."
# python3 -m venv /home/pi/midihub/venv
# source /home/pi/midihub/venv/bin/activate

# 4. Install Python packages
echo "📦 Installing Python packages..."
pip3 install mido python-rtmidi adafruit-circuitpython-ssd1306 Pillow --break-system-packages

# 5. Copy and enable systemd service
echo "📂 Setting up systemd service..."
cp midihub.service /etc/systemd/system/midihub.service
chmod 644 /etc/systemd/system/midihub.service

systemctl daemon-reload
systemctl enable midihub.service
systemctl start midihub.service

# 6. Reboot prompt
echo "✅ Setup complete. Reboot recommended."
read -p "Would you like to reboot now? (y/n): " confirm
if [[ $confirm == "y" ]]; then
  reboot
fi
