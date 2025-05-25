# setup.sh - installation script for Midihub
#!/bin/bash

set -e

REPO_DIR=$(dirname "$(realpath "$0")")

# Add aliases to .bashrc (RO to set readonly, RW to set readwrite)
if ! grep -q "alias RO=" ~/.bashrc; then
  echo "🛠️  Adding RO and RW aliases to ~/.bashrc..."
  echo "alias RO='sudo /usr/local/bin/readonly.sh RO'" >> ~/.bashrc
  echo "alias RW='sudo /usr/local/bin/readonly.sh RW'" >> ~/.bashrc
fi

echo "🔌 Enabling I²C and UART interface..."
raspi-config nonint do_i2c 0
raspi-config nonint do_serial 0
sed -i 's/$/ logo.nologo vt.global_cursor_default=0 quiet splash plymouth.ignore-serial-consoles/' /boot/cmdline.txt

echo "📦 Installing system dependencies..."
apt-get update
xargs -a "$REPO_DIR/dependencies.txt" sudo apt-get install -y

echo "🐍 Installing Python packages globally..."
pip3 install -r "$REPO_DIR/requirements.txt"

echo "📦 Copying udev rules & systemd service..."
cp "$REPO_DIR"/33-midiusb.rules /etc/udev/rules.d/
cp "$REPO_DIR"/44-midibt.rules /etc/udev/rules.d/
cp "$REPO_DIR"/midihub.service /etc/systemd/system/midihub.service
chmod 644 /etc/systemd/system/midihub.service
udevadm control --reload-rules
udevadm trigger

echo "📂 Installing scripts..."
cp "$REPO_DIR"/midioled.py /usr/local/bin/
cp "$REPO_DIR"/midihub.py /usr/local/bin/
chmod +x /usr/local/bin/midioled.py
chmod +x /usr/local/bin/midihub.py

echo "✅ Setup complete. Reboot recommended."
read -p "Would you like to reboot now? (y/n): " confirm
if [[ "$confirm" =~ ^[Yy]$ ]]; then
  reboot
fi
