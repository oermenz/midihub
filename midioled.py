#!/usr/bin/env python3

import os
import time
import threading
from mido import get_input_names, open_input
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas
from PIL import ImageDraw
from music21 import note as m21note, chord as m21chord
from fonts import load_fonts

DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 64

# Load all fonts once, raise error if missing
fonts = load_fonts()

TRIGGER_FILE = "/tmp/midihub_devices.trigger"
FONT_DIR = os.path.expanduser("~/midihub/fonts")
DEVICE_DISPLAY_TIME = 5
NOTE_DEBOUNCE_TIME = 0.03
NOTE_LATCH_WINDOW = 0.2
NOTE_LATCH_SHOW = 2.0
FLASH_TIME = 0.3
MAX_DEVICE_LINES = 5

state = {
    'channel': None,
    'cc': None,
    'cc_val': None,
    'show_devices': False,
    'devices': [],
    'last_device_update': 0,
    'chord_name': '',
    'chord_root': '',
    'chord_quality': '',
    'chord_bass': '',
    'lowest_note_name': '',
    'all_note_names': [],
    'unknown_chord': False,
    'last_chord_display': '',
    'last_chord_time': 0,
    'last_notes_display': [],
    'last_chord_persist': '',
    'toprow_values_flash_until': {'ch': 0, 'cc': 0, 'val': 0},
    'toprow_last': {'ch': None, 'cc': None, 'val': None},
    'last_chord_flash_until': 0,
    'device_scroll_time': 0,
    # New note state tracking
    'held_notes': set(),
    'released_notes': {},  # note -> release_time
    'last_released_chord': set(),
    'last_release_time': 0,
    'last_latch_time': 0,
}

serial = i2c(port=1, address=0x3C)
device = ssd1306(serial)

def midi_note_to_name(midi_note):
    try:
        n = m21note.Note(midi_note)
        return n.nameWithOctave
    except Exception:
        return str(midi_note)

def detect_chord(notes):
    try:
        ch = m21chord.Chord(notes)
        allowed_types = {
            'major triad': 'Major',
            'minor triad': 'Minor',
            'diminished triad': 'Dim',
            'augmented triad': 'Aug',
            'dominant seventh chord': '7th',
            'major seventh chord': 'Maj7',
            'minor seventh chord': 'Min7',
            'minor-major seventh chord': 'MinMaj7',
            'diminished seventh chord': 'Dim7',
            'half-diminished seventh chord': 'm7b5',
            'augmented seventh chord': 'Aug7',
        }
        quality = allowed_types.get(ch.commonName, None)
        if quality:
            root = midi_note_to_name(ch.root().midi)
            bass = midi_note_to_name(ch.bass().midi)
            return (root, quality, bass)
        else:
            return (None, None, None)
    except Exception:
        return (None, None, None)

def flash_expired(until_time):
    return time.time() > until_time

def draw_topline(draw, state, fonts):
    # Top line labels/values
    y = 0
    label_font = fonts['top_label']
    value_font = fonts['top_value']
    labels = ['CH', 'CC', 'VAL']
    value_keys = ['channel', 'cc', 'cc_val']
    x = 0
    spacing = 42
    for idx, label in enumerate(labels):
        # Draw label
        draw.text((x, y), label, font=label_font, fill=255)
        # Draw value, flash bold if needed
        val = state[value_keys[idx]]
        if val is None:
            val_str = "--"
        else:
            val_str = str(val)
        flash = not flash_expired(state['toprow_values_flash_until'][label.lower()])
        font = value_font if flash else label_font
        draw.text((x, y+14), val_str, font=font, fill=255)
        x += spacing

def draw_chord(draw, state, fonts):
    # Chord name, bold flash on change
    y = 28
    x = 0
    chord_text = state['chord_name'] if state['chord_name'] else "---"
    flash = not flash_expired(state['last_chord_flash_until'])
    font = fonts['chord_bold'] if flash else fonts['chord_normal']
    draw.text((x, y), chord_text, font=font, fill=255)

def draw_notes(draw, state, fonts):
    # Notes, invert bubble for active notes
    y = 48
    notes = state['all_note_names'] if state['all_note_names'] else []
    for idx, note in enumerate(notes):
        x = 4 + idx * 22
        # Draw bubble (filled rectangle) behind note
        active = note in state['held_notes']
        # Invert: active = white bubble, black text; else: black bubble, white text
        if active:
            draw.rectangle((x-2, y-2, x+18, y+18), fill=255)
            draw.text((x, y), note, font=fonts['note'], fill=0)
        else:
            draw.rectangle((x-2, y-2, x+18, y+18), fill=0)
            draw.text((x, y), note, font=fonts['note'], fill=255)

def draw_devices(draw, state, fonts):
    # Device list, normal font
    if not state['show_devices']:
        return
    devices = state['devices'][:MAX_DEVICE_LINES]
    y = 0
    for idx, dev in enumerate(devices):
        draw.text((0, y + idx * 12), dev, font=fonts['device'], fill=255)

def update_state_for_flashing(state, event_type, key):
    now = time.time()
    if event_type == 'toprow':
        state['toprow_values_flash_until'][key] = now + FLASH_TIME
    elif event_type == 'chord':
        state['last_chord_flash_until'] = now + FLASH_TIME

def main_loop():
    while True:
        with canvas(device) as draw:
            if state['show_devices']:
                draw_devices(draw, state, fonts)
            else:
                draw_topline(draw, state, fonts)
                draw_chord(draw, state, fonts)
                draw_notes(draw, state, fonts)
        time.sleep(0.03)

# Example usage: update_state_for_flashing(state, 'toprow', 'ch')
# or update_state_for_flashing(state, 'chord', None) when chord changes

if __name__ == "__main__":
    # Launch main loop in a thread or as needed
    main_loop()
