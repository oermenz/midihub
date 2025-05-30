#!/usr/bin/env python3

import os
import time
import threading
from collections import deque
from mido import get_input_names, open_input
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas
from PIL import ImageFont
from music21 import note as m21note, chord as m21chord

# Initialize OLED display
serial = i2c(port=1, address=0x3C)
device = ssd1306(serial)

# Load default font
font_path = os.path.expanduser("~/midihub/fonts/miniwi-8.bdf")
try:
    font = ImageFont.load(font_path)
except Exception:
    font = None

TRIGGER_FILE = "/tmp/midihub_devices.trigger"
DEVICE_DISPLAY_TIME = 2  # seconds

# Debounce time for note events in seconds
NOTE_DEBOUNCE_TIME = 0.03

# Shared state
state = {
    'channel': None,
    'cc': None,
    'cc_val': None,
    'active_notes': set(),  # Track currently held MIDI note numbers
    'note_timestamps': {},  # For debouncing: note -> last event time
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
}

def midi_note_to_name(midi_note):
    """Use music21 to get note name with octave."""
    try:
        n = m21note.Note(midi_note)
        return n.nameWithOctave
    except Exception:
        return str(midi_note)

def detect_chord(notes):
    """Return formatted chord name from a list of MIDI note numbers, or joined note names if not recognizable."""
    try:
        ch = m21chord.Chord(notes)
        # Extended set of chord types
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
            'suspended fourth chord': 'sus4',
            'suspended second chord': 'sus2',
            'ninth chord': '9th',
            'major ninth chord': 'Maj9',
            'minor ninth chord': 'Min9',
            'sixth chord': '6th',
            'minor sixth chord': 'Min6',
            'eleventh chord': '11th',
            'thirteenth chord': '13th',
        }
        common = ch.commonName
        root = ch.root().name if ch.root() else ""
        bass = ch.bass().nameWithOctave if ch.bass() else ""
        # Detect inversions
        is_inversion = ch.bass() and ch.root() and (ch.bass().name != ch.root().name)
        if common in allowed_types:
            quality = allowed_types[common]
            if is_inversion:
                chord_str = f"{root}{quality}/{bass}"
            else:
                chord_str = f"{root}{quality}"
            return chord_str, root, quality, bass, False
        else:
            # Show note names if not in allowed types
            note_names = [midi_note_to_name(n) for n in sorted(notes)]
            return " ".join(note_names), "", "", "", True
    except Exception:
        note_names = [midi_note_to_name(n) for n in sorted(notes)]
        return " ".join(note_names), "", "", "", True

def check_for_device_update():
    try:
        mtime = os.path.getmtime(TRIGGER_FILE)
        if mtime != state.get('last_device_update', 0):
            state['last_device_update'] = mtime
            return True
    except FileNotFoundError:
        pass
    return False

def update_display():
    while True:
        with canvas(device) as draw:
            if state['show_devices']:
                draw.text((0, 0), "MIDI Devices:", font=font, fill=255)
                for idx, name in enumerate(state['devices']):
                    draw.text((0, 10 + idx * 10), f"{idx+1}: {name}", font=font, fill=255)
            else:
                draw.text((0, 0), f"CH: {state['channel']}", font=font, fill=255)
                draw.text((0, 10), f"CC: {state['cc']} VAL: {state['cc_val']}", font=font, fill=255)

                # Show all held notes
                notes_str = " ".join(state['all_note_names'])
                draw.text((0, 20), f"NOTES: {notes_str}", font=font, fill=255)

                # Show chord (root, type, inversion)
                if len(state['all_note_names']) >= 3:
                    if not state['unknown_chord']:
                        draw.text((0, 30), f"CHORD: {state['chord_name']}", font=font, fill=255)
                    else:
                        # Show last recognized chord for 1.5s, then indicate unknown
                        if state['last_chord_display'] and (time.time() - state['last_chord_time'] < 1.5):
                            draw.text((0, 30), f"CHORD: {state['last_chord_display']}", font=font, fill=255)
                        else:
                            draw.text((0, 30), "CHORD: Unknown", font=font, fill=255)
                else:
                    # If less than 3 notes, show last chord for 1.5s
                    if state['last_chord_display'] and (time.time() - state['last_chord_time'] < 1.5):
                        draw.text((0, 30), f"CHORD: {state['last_chord_display']}", font=font, fill=255)
                    else:
                        draw.text((0, 30), "CHORD: ", font=font, fill=255)
        time.sleep(0.1)

def debounce_note_event(note, now):
    """Return True if event should be processed (not debounced)."""
    last = state['note_timestamps'].get(note, 0)
    if now - last > NOTE_DEBOUNCE_TIME:
        state['note_timestamps'][note] = now
        return True
    return False

def monitor_midi():
    inputs = []
    last_device_list = []
    shown_at = None

    while True:
        # Device change detection
        if check_for_device_update() or not inputs:
            # Refresh list of devices and input ports
            current_devices = get_input_names()
            if current_devices != last_device_list:
                last_device_list = list(current_devices)
                state['devices'] = current_devices
                state['show_devices'] = True
                # Close old ports and open new
                for inp in inputs:
                    inp.close()
                inputs = [open_input(name) for name in current_devices]
                # Show device list for specified time
                shown_at = time.time()
            else:
                shown_at = None

        # Handle display timeout for devices
        if state['show_devices']:
            if shown_at and (time.time() - shown_at > DEVICE_DISPLAY_TIME):
                state['show_devices'] = False

        # Read MIDI input
        now = time.time()
        for port in inputs:
            for msg in port.iter_pending():
                if msg.type == 'note_on' and msg.velocity > 0:
                    if debounce_note_event(msg.note, now):
                        state['channel'] = msg.channel + 1
                        state['active_notes'].add(msg.note)
                elif (msg.type == 'note_off') or (msg.type == 'note_on' and msg.velocity == 0):
                    if debounce_note_event(msg.note, now):
                        state['channel'] = msg.channel + 1
                        state['active_notes'].discard(msg.note)
                elif msg.type == 'control_change':
                    state['channel'] = msg.channel + 1
                    state['cc'] = msg.control
                    state['cc_val'] = msg.value

        # Update note and chord state
        if state['active_notes']:
            sorted_notes = sorted(state['active_notes'])
            state['all_note_names'] = [midi_note_to_name(n) for n in sorted_notes]
            if 3 <= len(sorted_notes) <= 6:
                chord_str, root, quality, bass, unknown = detect_chord(sorted_notes)
                state['chord_name'] = chord_str
                state['chord_root'] = root
                state['chord_quality'] = quality
                state['chord_bass'] = bass
                state['unknown_chord'] = unknown
                if not unknown:
                    state['last_chord_display'] = chord_str
                    state['last_chord_time'] = time.time()
            else:
                state['chord_name'] = ""
                state['unknown_chord'] = False
        else:
            state['all_note_names'] = []
            state['chord_name'] = ""
            state['unknown_chord'] = False

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
