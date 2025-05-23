#!/bin/bash

echo "🔧 Starting Midihub clean setup..."

# Ensure script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "❌ Please run as root: sudo ./setup.sh"
  exit 1
fi

# Enable I2C
echo "🔌 Enabling I²C interface..."
raspi-config nonint do_i2c 0

# Update and install system packages
echo "📦 Installing system dependencies..."
apt update
apt install -y python3 python3-pip python3-venv git i2c-tools libffi-dev libjpeg-dev zlib1g-dev libfreetype6-dev

# Clone or update midihub repo
MIDIHUB_DIR="/home/oermens/midihub"
if [ ! -d "$MIDIHUB_DIR" ]; then
  echo "📥 Cloning Midihub repository..."
  sudo -u oermens git clone https://github.com/oermenz/midihub.git "$MIDIHUB_DIR"
else
  echo "🔄 Updating Midihub repository..."
  cd "$MIDIHUB_DIR"
  sudo -u oermens git pull
fi

# Create and setup Python virtual environment
echo "🐍 Creating Python virtual environment..."
sudo -u pi python3 -m venv "$MIDIHUB_DIR/venv"

echo "📦 Installing Python packages in venv..."
sudo -u pi bash -c "source $MIDIHUB_DIR/venv/bin/activate && pip install --upgrade pip && pip install mido python-rtmidi adafruit-circuitpython-ssd1306 Pillow pydbus"

# Setup systemd service
echo "📂 Setting up systemd service..."

SERVICE_FILE="/etc/systemd/system/midihub.service"

cat > "$SERVICE_FILE" <<EOL
[Unit]
Description=Headless MIDI Hub
After=network.target sound.target bluetooth.target dbus.service
Requires=bluetooth.target

[Service]
ExecStart=$MIDIHUB_DIR/venv/bin/python $MIDIHUB_DIR/midihub.py
WorkingDirectory=$MIDIHUB_DIR
StandardOutput=journal
StandardError=journal
Restart=on-failure
RestartSec=5
User=oermens
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOL

chmod 644 "$SERVICE_FILE"

systemctl daemon-reload
systemctl enable midihub.service
systemctl restart midihub.service

echo "✅ Setup complete. A reboot is recommended."

read -p "Would you like to reboot now? (y/n): " confirm
if [[ "$confirm" =~ ^[Yy]$ ]]; then
  reboot
fi
