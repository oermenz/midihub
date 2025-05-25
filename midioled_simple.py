#!/usr/bin/env python3

import time
import sys
import subprocess
from PIL import Image, ImageDraw, ImageFont

# Import Adafruit SSD1306 library
import Adafruit_SSD1306

# Raspberry Pi pin configuration:
RST = None  # on the PiOLED this pin isn't used

# Initialize the display
disp = Adafruit_SSD1306.SSD1306_128_64(rst=RST)

# Begin display
disp.begin()
disp.clear()
disp.display()

# Create image buffer with mode '1' for 1-bit color
width = disp.width
height = disp.height
image = Image.new('1', (width, height))

# Get drawing object to draw on image
draw = ImageDraw.Draw(image)

# Load default font
font = ImageFont.load_default()

# Define padding and initial top position
padding = 2
top = padding
bottom = height - padding
x = 0
line_height = 10  # Allow room for 6 lines in 64px height

def get_midi_devices():
    try:
        output = subprocess.check_output(['aconnect', '-i'], text=True)
        devices = []
        lines = output.strip().split('\n')
        for line in lines:
            if 'client' in line and 'Through' not in line:
                parts = line.split("'")
                if len(parts) > 1:
                    devices.append(parts[1])
        return devices
    except subprocess.CalledProcessError:
        return []

def display_devices(devices):
    draw.rectangle((0, 0, width, height), outline=0, fill=0)
    if devices:
        for i, device in enumerate(devices[:6]):  # Display up to 6 devices
            draw.text((x, top + i * line_height), device, font=font, fill=255)
    else:
        draw.text((x, top), "No MIDI devices", font=font, fill=255)
    disp.image(image)
    disp.display()

if __name__ == "__main__":
    devices = get_midi_devices()
    display_devices(devices)
