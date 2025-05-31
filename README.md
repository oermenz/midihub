# 🎛️ Midihub — MIDI/AUDIO Router with OLED Display 

Midihub is a lightweight, headless Raspberry Pi project perfect for Dawless setups.

## 📷 Features

- ✅ Auto-connects all MIDI devices (USB, Bluetooth, DIN)
- ✅ Displays connected device names when connected on screen
- ✅ Displays last received Notes, Chords, Channel, CC, Value
- ✅ Designed for monochrone 128x64 SSD1306 I²C OLED display
- ✅ Auto-starts on boot via systemd and udev triggers

---

## 📦 Requirements

- Raspberry Pi (tested on Bookworm, x64 lite)
- I²C-enabled 128x64 SSD1306 OLED (DIYUSER 0.96 Inch)
- USB midi controllers (no fun without them)
- Internet access (for initial setup)

---

## 🚀 Setup Instructions

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
