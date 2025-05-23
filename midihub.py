import threading
import queue
import time
import mido
from mido import get_input_names, get_output_names, open_input, open_output, Message
from pydbus import SystemBus
from gi.repository import GLib
import board
import busio
import adafruit_ssd1306
from PIL import Image, ImageDraw, ImageFont

# === Initialize OLED Display ===
i2c = busio.I2C(board.SCL, board.SDA)
oled = adafruit_ssd1306.SSD1306_I2C(128, 32, i2c)
font = ImageFont.load_default()

# === MIDI variables and state ===
midi_queue = queue.Queue()
last_midi_msg = None
last_cc = None
last_val = None
last_note_name = "---"
last_bpm = 0

# === MIDI clock timing ===
clock_count = 0
clock_start_time = None

# === Helper function: MIDI note to name with octave ===
def note_name(note):
    names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    octave = (note // 12) - 1
    return f"{names[note % 12]}{octave}"

# === MIDI input reader thread ===
def midi_input_reader(port_name):
    global clock_count, clock_start_time, last_bpm
    with mido.open_input(port_name) as inport:
        while True:
            for msg in inport.iter_pending():
                midi_queue.put(msg)
                # Calculate BPM from clock messages
                if msg.type == 'clock':
                    if clock_start_time is None:
                        clock_start_time = time.time()
                        clock_count = 1
                    else:
                        clock_count += 1
                        if clock_count >= 24 * 4:  # one measure (24 clocks per quarter * 4 quarters)
                            elapsed = time.time() - clock_start_time
                            if elapsed > 0:
                                bpm = 60 / (elapsed / 4)
                                last_bpm = int(bpm)
                            clock_start_time = time.time()
                            clock_count = 0
            time.sleep(0.002)  # small sleep to reduce CPU usage

# === Initialize MIDI input port ===
def get_midi_input_name():
    names = mido.get_input_names()
    # Pick first port containing 'Midi Fighter Twister' or fallback to first port
    for name in names:
        if 'Midi Fighter Twister' in name:
            return name
    return names[0] if names else None

# === OLED display update function ===
def update_oled(ch=None, cc=None, val=None, note=None, bpm=None):
    oled.fill(0)
    image = Image.new("1", (oled.width, oled.height))
    draw = ImageDraw.Draw(image)

    # Compose top line: CH, CC, VAL
    top_line = f"CH:{ch if ch is not None else '--'} CC:{cc if cc is not None else '--'} VAL:{val if val is not None else '--'}"
    # Compose bottom line: NOTE, BPM
    bottom_line = f"NOTE:{note if note else '---'} BPM:{bpm if bpm else '--'}"

    draw.text((0, 0), top_line, font=font, fill=255)
    draw.text((0, 16), bottom_line, font=font, fill=255)

    oled.image(image)
    oled.show()

def main():
    global last_midi_msg, last_cc, last_val, last_note_name, last_bpm, last_update_time

    # Initialize last_update_time here before loop
    last_update_time = 0
    
    midi_port_name = get_midi_input_name()
    if not midi_port_name:
        print("No MIDI input ports found!")
        return

    print(f"Using MIDI input: {midi_port_name}")

    # Start MIDI input thread
    threading.Thread(target=midi_input_reader, args=(midi_port_name,), daemon=True).start()

    # Main loop
    while True:
        updated = False
        # Process all MIDI messages in the queue immediately
        while not midi_queue.empty():
            msg = midi_queue.get()
            last_midi_msg = msg

            if msg.type == 'control_change':
                last_cc = msg.control
                last_val = msg.value
            elif msg.type == 'note_on' or msg.type == 'note_off':
                last_note_name = note_name(msg.note)
            # Add more MIDI message handling if needed
            updated = True

        # Update OLED display at ~10 Hz
        if updated or (time.time() - last_update_time) > 0.1:
            ch = last_midi_msg.channel + 1 if last_midi_msg and hasattr(last_midi_msg, 'channel') else None
            update_oled(ch=ch, cc=last_cc, val=last_val, note=last_note_name, bpm=last_bpm)
            last_update_time = time.time()

        time.sleep(0.01)  # small delay to reduce CPU usage

if __name__ == "__main__":
    main()
