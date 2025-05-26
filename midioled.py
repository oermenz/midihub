import os
import time
import threading
from collections import deque
from mido import get_input_names, open_input
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas
from PIL import ImageFont

# Initialize OLED display
serial = i2c(port=1, address=0x3C)
device = ssd1306(serial)

# Load default font
font_path = os.path.expanduser("~/midihub/font/miniwi-8.bdf")
font = ImageFont.load(font_path)

# Shared state
state = {
    'channel': None,
    'cc': None,
    'cc_val': None,
    'note': None,
    'bpm': None,
    'show_devices': False,
    'devices': [],
    'last_clock_times': deque(maxlen=24)
}

def note_number_to_pitch(note_number):
    """Convert MIDI note number to pitch notation."""
    notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    octave = (note_number // 12) - 1
    note = notes[note_number % 12]
    return f"{note}{octave}"

def update_display():
    """Update the OLED display based on the current state."""
    while True:
        with canvas(device) as draw:
            if state['show_devices']:
                draw.text((0, 0), "MIDI Devices:", font=font, fill=255)
                for idx, name in enumerate(state['devices']):
                    draw.text((0, 10 + idx * 10), f"{idx+1}: {name}", font=font, fill=255)
            else:
                draw.text((0, 0), f"CH: {state['channel']}", font=font, fill=255)
                draw.text((0, 10), f"CC: {state['cc']} VAL: {state['cc_val']}", font=font, fill=255)
                draw.text((0, 20), f"NOTE: {state['note']}", font=font, fill=255)
                draw.text((0, 30), f"BPM: {state['bpm']}", font=font, fill=255)
        time.sleep(0.1)

def monitor_midi():
    """Monitor MIDI messages and update the state accordingly."""
    input_names = get_input_names()
    state['devices'] = input_names
    state['show_devices'] = True
    time.sleep(2)
    state['show_devices'] = False

    inputs = [open_input(name) for name in input_names]

    while True:
        for port in inputs:
            for msg in port.iter_pending():
                if msg.type == 'note_on':
                    state['channel'] = msg.channel + 1  # MIDI channels are 1-based
                    state['note'] = note_number_to_pitch(msg.note)
                elif msg.type == 'control_change':
                    state['channel'] = msg.channel + 1
                    state['cc'] = msg.control
                    state['cc_val'] = msg.value
                elif msg.type == 'clock':
                    now = time.time()
                    state['last_clock_times'].append(now)
                    if len(state['last_clock_times']) >= 2:
                        intervals = [t2 - t1 for t1, t2 in zip(state['last_clock_times'], list(state['last_clock_times'])[1:])]
                        avg_interval = sum(intervals) / len(intervals)
                        # MIDI clock sends 24 messages per quarter note
                        bpm = 60 / (avg_interval * 24)
                        state['bpm'] = round(bpm, 1)
        time.sleep(0.01)

if __name__ == "__main__":
    display_thread = threading.Thread(target=update_display, daemon=True)
    midi_thread = threading.Thread(target=monitor_midi, daemon=True)

    display_thread.start()
    midi_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
