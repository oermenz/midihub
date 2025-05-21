# 🎛️ Midihub — Headless MIDI Router with OLED Display

Midihub is a lightweight, headless Raspberry Pi project that:
- Connects all available MIDI input/output devices
- Displays device names on a 128x64 OLED screen with paging and scrolling
- Shows live MIDI activity: Control Change (CC), Note, and Velocity values

No desktop needed — runs automatically on boot using a systemd service.

---

## 📷 Features

- ✅ Auto-connects all MIDI devices (USB, Bluetooth, etc.)
- ✅ OLED display of connected device names (with scrolling for long names)
- ✅ Displays last received CC + note + velocity
- ✅ Designed for 128x64 SSD1306 I²C OLED
- ✅ Auto-starts on boot via systemd

---

## 📦 Requirements

- Raspberry Pi (tested on Bookworm)
- I²C-enabled 128x64 SSD1306 OLED
- Python 3
- Internet access (for initial setup)

---

## 🚀 Setup Instructions

1. **Clone the repository**

```bash
git clone https://github.com/oermenz/midihub.git
cd midihub
chmod +x setup.sh
sudo ./setup.sh
