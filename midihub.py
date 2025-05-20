import time
import subprocess
import threading
import mido
from mido import get_input_names
from PIL import Image, ImageDraw, ImageFont
import board
import busio
import adafruit_ssd1306

# === OLED SETUP ===
WIDTH = 128
HEIGHT = 64
LINE_HEIGHT = 10  # with spacing
SPACING = 2
SCROLL_SPEED = 0.2

i2c = busio.I2C(board.SCL, board.SDA)
oled = adafruit_ssd1306.SSD1306_I2C(WIDTH, HEIGHT, i2c)
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)

# === DATA TRACKING ===
latest_cc = "CC: --"
latest_note = "Note: -- --"

scroll_offsets = {}
scroll_directions = {}

def get_displayable_devices():
    devices = get_input_names()
    cleaned = []
    for name in devices:
        if "kernel" not in name.lower():
            cleaned.append(name.strip())
    return cleaned[:5]

def scroll_text(text, line_index):
    text_width = font.getlength(text)
    if text_width <= WIDTH:
        return text

    offset = scroll_offsets.get(line_index, 0)
    direction = scroll_directions.get(line_index, 1)

    max_offset = int(text_width - WIDTH)

    if direction == 1:
        offset += 2
        if offset >= max_offset:
            direction = -1
    else:
        offset -= 2
        if offset <= 0:
            direction = 1

    scroll_offsets[line_index] = offset
    scroll_directions[line_index] = direction

    return text[int(offset/2):]

def midi_listener():
    global latest_cc, latest_note
    inputs = mido.get_input_names()
    ports = [mido.open_input(name, callback=handle_midi) for name in inputs]

def handle_midi(msg):
    global latest_cc, latest_note
    if msg.type == 'control_change':
        latest_cc = f"CC: {msg.control}"
    elif msg.type == 'note_on':
        note_name = note_number_to_name(msg.note)
        latest_note = f"Note: {note_name} {msg.velocity}"

def note_number_to_name(note):
    notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    return notes[note % 12] + str(note // 12)

def connect_all_midi_ports():
    inputs = get_alsa_ports('-i')
    outputs = get_alsa_ports('-o')
    for inp in inputs:
        for out in outputs:
            subprocess.run(['aconnect', inp, out], stderr=subprocess.DEVNULL)

def get_alsa_ports(flag):
    result = subprocess.run(['aconnect', flag], capture_output=True, text=True)
    ports = []
    for line in result.stdout.splitlines():
        if ':' in line:
            ports.append(line.split()[0])
    return ports

def draw_loop():
    device_page = 0
    while True:
        devices = get_displayable_devices()
        image = Image.new("1", (WIDTH, HEIGHT))
        draw = ImageDraw.Draw(image)

        # Draw header (top line)
        header = f"{latest_cc} | {latest_note}"
        draw.text((0, 0), header, font=font, fill=255)

        # Draw MIDI device names below
        lines_available = (HEIGHT - LINE_HEIGHT) // LINE_HEIGHT
        start = device_page * lines_available
        end = start + lines_available
        visible_devices = devices[start:end]

        for i, dev in enumerate(visible_devices):
            y = LINE_HEIGHT + i * LINE_HEIGHT
            line_index = start + i
            scrolled = scroll_text(dev, line_index)
            draw.text((0, y), scrolled, font=font, fill=255)

        oled.image(image)
        oled.show()

        if len(devices) > lines_available:
            device_page = (device_page + 1) % ((len(devices) + lines_available - 1) // lines_available)

        time.sleep(SCROLL_SPEED)

# === MAIN ===
if __name__ == "__main__":
    time.sleep(2)  # Wait for MIDI devices
    connect_all_midi_ports()
    threading.Thread(target=midi_listener, daemon=True).start()
    draw_loop()
