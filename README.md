# 🎛️ HookUp — MIDI/AUDIO Router with OLED Display 

HookUp is a lightweight, headless Raspberry Pi project perfect for Dawless setups.

## 📷 Features

- ✅ Hooks up all MIDI devices (USB, Bluetooth, DIN)
- ✅ Hooks up all AUDIO devices (AUDIO over USB)
- ✅ Displays hooked up device names if OLED screen is present
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
git clone https://github.com/hookup/midihub.git ~/hookup && cd ~/hookup
sudo chmod +x setup.sh && sudo ./setup.sh
```
