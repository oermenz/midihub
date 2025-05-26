# 🎛️ Midihub — MIDI Router with OLED Display

Midihub is a lightweight, headless Raspberry Pi project perfect for Dawless setups.

## 📷 Features

- ✅ Auto-connects all MIDI devices (USB, Bluetooth, DIN)
- ✅ OLED display of connected device names when connected
- ✅ Displays last received CH + CC + Value + Note + BPM
- ✅ Designed for 128x64 SSD1306 I²C OLED
- ✅ Auto-starts on boot via systemd

---

## 📦 Requirements

- Raspberry Pi (tested on Bookworm, x64 lite)
- I²C-enabled 128x64 SSD1306 OLED (DIYUSER 0.96 Inch)
- USB midi controllers (no fun without them)
- Internet access (for initial setup)

---

## 🚀 Setup Instructions

***IMPORTANT: Use "oermens" as username or replace in the services files and setup script***

1. **Update and install**

```bash
sudo apt update -y && sudo apt upgrade -y
sudo apt install git -y
```

2. **Download and run setup**

```bash
git clone https://github.com/oermenz/midihub.git ~/midihub && cd ~/midihub
sudo chmod +x setup.sh && sudo ./setup.sh
```
