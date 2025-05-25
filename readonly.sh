# readonly-setup.sh - toggle Raspberry Pi filesystem between read-only and read-write
#!/bin/bash

set -e

if [[ "$1" == "RO" ]]; then
  echo "🔒 Switching to READ-ONLY mode..."

  # Back up fstab and cmdline.txt if not already backed up
  [[ -f /etc/fstab.bak ]] || sudo cp /etc/fstab /etc/fstab.bak
  [[ -f /boot/cmdline.txt.bak ]] || sudo cp /boot/cmdline.txt /boot/cmdline.txt.bak

  # Modify fstab: mount / and /boot as read-only
  sudo sed -i 's|defaults|defaults,ro|' /etc/fstab
  sudo sed -i 's|/boot.*defaults|/boot  defaults,ro|' /etc/fstab

  # Modify cmdline.txt to include fastboot and ro
  sudo sed -i 's| rootwait| fastboot noswap ro rootwait|' /boot/cmdline.txt

  # Add tmpfs for /var/log and /tmp if not already present
  grep -q "/var/log" /etc/fstab || sudo tee -a /etc/fstab > /dev/null <<EOL
tmpfs /tmp tmpfs defaults,noatime,nosuid,size=50m 0 0
tmpfs /var/log tmpfs defaults,noatime,nosuid,mode=0755,size=20m 0 0
tmpfs /var/tmp tmpfs defaults,noatime,nosuid,size=20m 0 0
EOL

  # Create required mount points
  sudo mkdir -p /var/log /var/tmp /tmp

  echo "✅ System is now in READ-ONLY mode. Reboot required."

elif [[ "$1" == "RW" ]]; then
  echo "🔓 Switching to READ-WRITE mode..."

  # Restore from backup
  [[ -f /etc/fstab.bak ]] && sudo cp /etc/fstab.bak /etc/fstab
  [[ -f /boot/cmdline.txt.bak ]] && sudo cp /boot/cmdline.txt.bak /boot/cmdline.txt

  echo "✅ System is now in READ-WRITE mode. Reboot required."

else
  echo "Usage: $0 RO|RW"
  echo "  RO - Set filesystem to read-only mode"
  echo "  RW - Revert to read-write mode"
  exit 1
fi

read -p "Would you like to reboot now? (y/n): " confirm
if [[ "$confirm" =~ ^[Yy]$ ]]; then
  sudo reboot
fi
