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

# Display constants
DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 64
LINE_HEIGHT = 10

# Font paths
FONT_DIR = os.path.expanduser("~/midihub/fonts")
FONT_DEVICE_LIST = os.path.join(FONT_DIR, "miniwi-8.bdf")
FONT_INFO = os.path.join(FONT_DIR, "RobotoMono-VariableFont_wght.ttf")

# Load fonts
try:
    font_device = ImageFont.load(FONT_DEVICE_LIST)
except Exception:
    font_device = None

try:
    font_info = ImageFont.truetype(FONT_INFO, 22)
except Exception:
    font_info = None

try:
    font_info_small = ImageFont.truetype(FONT_INFO, 14)
except Exception:
    font_info_small = None

TRIGGER_FILE = "/tmp/midihub_devices.trigger"
DEVICE_DISPLAY_TIME = 4  # seconds
NOTE_DEBOUNCE_TIME = 0.03

# Change flash time in seconds
FLASH_TIME = 0.3

# Shared state
state = {
    'channel': None,
    'cc': None,
    'cc_val': None,
    'active_notes': set(),
    'note_timestamps': {},
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
    'last_toprow': '',
    'toprow_flash_until': 0,
    'last_chord_flash_until': 0,
    'device_scroll_offset': 0,
    'device_scroll_time': 0,
    'device_name_scroll_offsets': {},
    'device_name_scroll_time': 0,
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
        is_inversion = ch.bass() and ch.root() and (ch.bass().name != ch.root().name)
        if common in allowed_types:
            quality = allowed_types[common]
            if is_inversion:
                chord_str = f"{root}{quality}/{bass}"
            else:
                chord_str = f"{root}{quality}"
            return chord_str, root, quality, bass, False
        else:
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

def filter_device_names(devices):
    filtered = []
    for name in devices:
        if "Through" in name:
            continue
        # Remove anything like [128:0] at end
        if "[" in name and "]" in name:
            name = name.rsplit("[", 1)[0].strip()
        filtered.append(name)
    return filtered

def get_text_size(text, font):
    if font:
        return font.getsize(text)
    else:
        # fallback: estimate 6px per char
        return (len(text) * 6, 10)

def draw_centered(draw, y, text, font, fill=255, invert=False, bgfill=0):
    w, h = get_text_size(text, font)
    x = max(0, (DISPLAY_WIDTH - w) // 2)
    if invert:
        draw.rectangle((x, y, x + w, y + h), outline=fill, fill=fill)
        draw.text((x, y), text, font=font, fill=bgfill)
    else:
        draw.text((x, y), text, font=font, fill=fill)

def draw_bubble_notes(draw, y, note_names, font):
    # Draw each note in a rounded rectangle "bubble", centered as a group
    padd = 4
    spacing = 4
    bubble_h = 28
    bubble_font_y = y + 4
    x = 0
    bubble_w = []
    for name in note_names:
        w, h = get_text_size(name, font)
        bubble_w.append(w + padd * 2)
    total_w = sum(bubble_w) + spacing * (len(note_names) - 1)
    x = (DISPLAY_WIDTH - total_w) // 2
    for i, name in enumerate(note_names):
        w, h = get_text_size(name, font)
        bw = bubble_w[i]
        # Draw rounded rectangle
        draw.rounded_rectangle((x, y, x + bw, y + bubble_h), radius=8, outline=255, fill=0)
        # Draw note name centered in bubble
        draw.text((x + (bw - w) // 2, bubble_font_y), name, font=font, fill=255)
        x += bw + spacing

def update_display():
    while True:
        with canvas(device) as draw:
            if state['show_devices']:
                # Device list logic (use miniwi-8.bdf)
                device_names = state['devices']
                filtered_devices = filter_device_names(device_names)
                n_devices = len(filtered_devices)
                lines_per_screen = DISPLAY_HEIGHT // LINE_HEIGHT
                lines_on_screen = min(lines_per_screen, 6)
                scroll_needed = n_devices > lines_on_screen
                now = time.time()
                elapsed = now - state['device_scroll_time']
                if scroll_needed:
                    total_scroll_steps = n_devices - lines_on_screen
                    scroll_step_time = DEVICE_DISPLAY_TIME / max(1, total_scroll_steps)
                    scroll_idx = int(min(total_scroll_steps, elapsed // scroll_step_time))
                else:
                    scroll_idx = 0
                y = 0
                for i in range(lines_on_screen):
                    dev_idx = i + scroll_idx
                    if dev_idx >= n_devices:
                        break
                    name = filtered_devices[dev_idx]
                    draw.text((0, y), name, font=font_device, fill=255)
                    y += LINE_HEIGHT
            else:
                # Info screen (RobotoMono font)
                # Top row: CH, CC, VAL centered, invert if any value changed
                ch = str(state['channel']) if state['channel'] is not None else '-'
                cc = str(state['cc']) if state['cc'] is not None else '-'
                val = str(state['cc_val']) if state['cc_val'] is not None else '-'
                toprow = f"CH:{ch}  CC:{cc}  VAL:{val}"
                invert_toprow = (time.time() < state.get('toprow_flash_until', 0))
                draw_centered(draw, 0, toprow, font_info_small, fill=255, invert=invert_toprow, bgfill=0)

                # Middle: Bubble notes, large
                notes_to_display = state['all_note_names'] if state['all_note_names'] else state.get('last_notes_display', [])
                if notes_to_display:
                    draw_bubble_notes(draw, 16, notes_to_display, font_info)
                else:
                    # Draw a dashed empty row for "no notes"
                    draw_centered(draw, 24, "--", font_info, fill=128)

                # Bottom: Chord name, centered, inverts when changed
                chord_to_display = ""
                if len(notes_to_display) >= 3:
                    if not state['unknown_chord'] and state['chord_name']:
                        chord_to_display = state['chord_name']
                    elif state.get('last_chord_persist'):
                        chord_to_display = state['last_chord_persist']
                    else:
                        chord_to_display = "Unknown"
                elif state.get('last_chord_persist'):
                    chord_to_display = state['last_chord_persist']
                chord_invert = (time.time() < state.get('last_chord_flash_until', 0))
                draw_centered(draw, 48, chord_to_display, font_info, fill=255, invert=chord_invert, bgfill=0)
        time.sleep(0.1)

def debounce_note_event(note, now):
    last = state['note_timestamps'].get(note, 0)
    if now - last > NOTE_DEBOUNCE_TIME:
        state['note_timestamps'][note] = now
        return True
    return False

def monitor_midi():
    inputs = []
    last_device_list = []
    shown_at = None
    prev_toprow = ''
    prev_chord = ''
    while True:
        # Device change detection
        if check_for_device_update() or not inputs:
            current_devices = get_input_names()
            filtered_devices = filter_device_names(current_devices)
            if filtered_devices != last_device_list:
                last_device_list = list(filtered_devices)
                state['devices'] = current_devices
                state['show_devices'] = True
                for inp in inputs:
                    inp.close()
                inputs = [open_input(name) for name in current_devices if "Through" not in name]
                shown_at = time.time()
                state['device_scroll_time'] = shown_at
                state['device_name_scroll_time'] = shown_at
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
            state['last_notes_display'] = state['all_note_names']
            if 3 <= len(sorted_notes) <= 6:
                chord_str, root, quality, bass, unknown = detect_chord(sorted_notes)
                state['chord_name'] = chord_str
                state['chord_root'] = root
                state['chord_quality'] = quality
                state['chord_bass'] = bass
                state['unknown_chord'] = unknown
                if not unknown:
                    state['last_chord_persist'] = chord_str
                    state['last_chord_time'] = time.time()
            else:
                state['chord_name'] = ""
                state['unknown_chord'] = False
        else:
            state['all_note_names'] = []
            state['chord_name'] = ""
            state['unknown_chord'] = False

        # Flash top row if changed
        ch = str(state['channel']) if state['channel'] is not None else '-'
        cc = str(state['cc']) if state['cc'] is not None else '-'
        val = str(state['cc_val']) if state['cc_val'] is not None else '-'
        toprow = f"CH:{ch}  CC:{cc}  VAL:{val}"
        if toprow != state.get('last_toprow', ''):
            state['toprow_flash_until'] = time.time() + FLASH_TIME
            state['last_toprow'] = toprow

        # Flash chord if changed
        chord_to_display = state['chord_name'] if state['chord_name'] else state.get('last_chord_persist', '')
        if chord_to_display != prev_chord:
            state['last_chord_flash_until'] = time.time() + FLASH_TIME
            prev_chord = chord_to_display

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
