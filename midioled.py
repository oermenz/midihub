#!/usr/bin/env python3

import os
import time
import threading
from mido import get_input_names, open_input
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas
from PIL import ImageFont
from music21 import note as m21note, chord as m21chord

DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 64

# Font paths (adjust as needed)
FONT_DIR = os.path.expanduser("~/midihub/fonts")
FONT_DEVICE_LIST = os.path.join(FONT_DIR, "miniwi-8.bdf")
FONT_MONO = FONT_DEVICE_LIST  # Use miniwi-8.bdf for all monospace
FONT_INFO = os.path.join(FONT_DIR, "RobotoMono-VariableFont_wght.ttf")

def load_fonts():
    try:
        font_device = ImageFont.load(FONT_DEVICE_LIST)
    except Exception:
        font_device = None
    try:
        font_mono = ImageFont.load(FONT_MONO)
    except Exception:
        font_mono = None
    try:
        font_info = ImageFont.truetype(FONT_INFO, 14)
    except Exception:
        font_info = None
    return font_device, font_mono, font_info

font_device, font_mono, font_info = load_fonts()

TRIGGER_FILE = "/tmp/midihub_devices.trigger"
DEVICE_DISPLAY_TIME = 5      # seconds
NOTE_DEBOUNCE_TIME = 0.03
FLASH_TIME = 0.3
MAX_DEVICE_LINES = 5  # max device lines to show at once

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
    'toprow_values_flash_until': {'ch': 0, 'cc': 0, 'val': 0},
    'toprow_last': {'ch': None, 'cc': None, 'val': None},
    'last_chord_flash_until': 0,
    'device_scroll_time': 0,
    'bubble_latched_notes': [],
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
        if "[" in name and "]" in name:
            name = name.rsplit("[", 1)[0].strip()
        filtered.append(name)
    return filtered

def get_text_size(text, font):
    if font:
        bbox = font.getbbox(text)
        return (bbox[2] - bbox[0], bbox[3] - bbox[1])
    else:
        return (len(text) * 6, 10)

def draw_centered_text(draw, x, y, w, h, text, font, fill):
    ascent, descent = font.getmetrics()
    text_w, text_h = get_text_size(text, font)
    # Adjust for bitmap font vertical alignment
    offset = (h - (ascent + descent)) // 2
    draw.text((x + (w - text_w) // 2, y + offset), text, font=font, fill=fill)

def draw_toprow(draw, y, state):
    # Use miniwi-8.bdf for top row for best fit and vertical alignment
    font = font_mono
    ch = str(state['channel']) if state['channel'] is not None else '-'
    cc = str(state['cc']) if state['cc'] is not None else '-'
    val = str(state['cc_val']) if state['cc_val'] is not None else '-'
    labels = ['CH', 'CC', 'VAL']
    values = [ch, cc, val]
    flash_until = state.get('toprow_values_flash_until', {})
    padd = 1  # between label and value
    sep = 1   # between blocks
    parts = []
    for label, value in zip(labels, values):
        lw, lh = get_text_size(label, font)
        vw, vh = get_text_size(value, font)
        boxw = lw + padd + vw
        boxh = max(lh, vh)
        parts.append((label, lw, lh, value, vw, vh, boxw, boxh))
    total_w = sum(boxw for *_, boxw, _ in parts) + sep * (len(parts) - 1)
    x = (DISPLAY_WIDTH - total_w) // 2
    now = time.time()
    for i, (label, lw, lh, value, vw, vh, boxw, boxh) in enumerate(parts):
        # Draw label
        draw_centered_text(draw, x, y, lw, boxh, label, font, fill=255)
        x += lw + padd
        invert = now < flash_until.get(['ch','cc','val'][i], 0)
        if invert:
            draw.rectangle((x, y, x + vw, y + boxh), outline=255, fill=255)
            draw_centered_text(draw, x, y, vw, boxh, value, font, fill=0)
        else:
            draw_centered_text(draw, x, y, vw, boxh, value, font, fill=255)
        x += vw + sep

def draw_bubble_notes(draw, y, note_names, held_notes, font, held_set):
    padd_x = 1
    padd_y = 0
    spacing = 1
    bubble_h = get_text_size("A", font)[1] + padd_y * 2
    bubble_w = []
    for name in note_names:
        w, h = get_text_size(name, font)
        bubble_w.append(w + 2 * padd_x)
    total_w = sum(bubble_w) + spacing * (len(note_names) - 1)
    x = max(0, (DISPLAY_WIDTH - total_w) // 2)
    for i, name in enumerate(note_names):
        w, h = get_text_size(name, font)
        bw = bubble_w[i]
        try:
            note_val = held_notes[i]
        except IndexError:
            note_val = None
        invert = note_val in held_set
        if invert:
            draw.rounded_rectangle((x, y, x + bw, y + bubble_h), radius=3, outline=255, fill=255)
            draw_centered_text(draw, x, y, bw, bubble_h, name, font, fill=0)
        else:
            draw.rounded_rectangle((x, y, x + bw, y + bubble_h), radius=3, outline=255, fill=0)
            draw_centered_text(draw, x, y, bw, bubble_h, name, font, fill=255)
        x += bw + spacing

def update_display():
    chord_font = font_info or font_mono
    chord_fixed_y = DISPLAY_HEIGHT - get_text_size("A", chord_font)[1] - 2 - 8  # Raise chord by 8px
    while True:
        with canvas(device) as draw:
            if state['show_devices']:
                devices = filter_device_names(state['devices'])
                font = font_device or font_mono
                line_h = get_text_size("A", font)[1] + 2
                n_devices = len(devices)
                if n_devices <= MAX_DEVICE_LINES:
                    for i, name in enumerate(devices):
                        y = i * line_h
                        if y < DISPLAY_HEIGHT:
                            draw.text((0, y), name, font=font, fill=255)
                else:
                    total_scroll = n_devices - MAX_DEVICE_LINES
                    scroll_period = DEVICE_DISPLAY_TIME
                    elapsed = (time.time() - state['device_scroll_time']) % scroll_period
                    scroll_lines = (elapsed / scroll_period) * total_scroll
                    first_line = int(scroll_lines)
                    pixel_offset = int((scroll_lines - first_line) * line_h)
                    for i in range(MAX_DEVICE_LINES + 1):
                        idx = first_line + i
                        if idx < n_devices:
                            y = i * line_h - pixel_offset
                            if 0 <= y < DISPLAY_HEIGHT:
                                draw.text((0, y), devices[idx], font=font, fill=255)
            else:
                draw_toprow(draw, 0, state)
                # Notes
                bubble_font = font_mono
                if state['active_notes']:
                    notes_to_display = [midi_note_to_name(n) for n in sorted(state['active_notes'])]
                    note_vals = sorted(state['active_notes'])
                    held_set = set(note_vals)
                elif state['bubble_latched_notes']:
                    notes_to_display = [midi_note_to_name(n) for n in state['bubble_latched_notes']]
                    note_vals = state['bubble_latched_notes']
                    held_set = set()
                else:
                    notes_to_display = []
                    note_vals = []
                    held_set = set()
                bubble_h = get_text_size("A", bubble_font)[1] + 2
                toprow_height = get_text_size("A", font_mono)[1]
                # Center between toprow and chord
                bubbles_y = (chord_fixed_y - bubble_h - toprow_height) // 2 + toprow_height
                if notes_to_display:
                    draw_bubble_notes(
                        draw, bubbles_y, notes_to_display, note_vals,
                        font=bubble_font,
                        held_set=held_set
                    )
                else:
                    w, h = get_text_size("--", bubble_font)
                    draw.text((DISPLAY_WIDTH // 2 - w // 2, bubbles_y), "--", font=bubble_font, fill=128)
                # Chord name, static position
                chord_to_display = ""
                if len(note_vals) >= 3 and state['chord_name']:
                    chord_to_display = state['chord_name']
                elif state['last_chord_persist']:
                    chord_to_display = state['last_chord_persist']
                chord_invert = (time.time() < state.get('last_chord_flash_until', 0))
                w, h = get_text_size(chord_to_display, chord_font)
                chord_x = max(0, (DISPLAY_WIDTH - w) // 2)
                if chord_to_display:
                    if chord_invert:
                        draw.rectangle(
                            (chord_x, chord_fixed_y, chord_x + w, chord_fixed_y + h),
                            outline=255, fill=255
                        )
                        draw_centered_text(draw, chord_x, chord_fixed_y, w, h, chord_to_display, chord_font, fill=0)
                    else:
                        draw_centered_text(draw, chord_x, chord_fixed_y, w, h, chord_to_display, chord_font, fill=255)
        time.sleep(0.04)

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
    prev_ch = None
    prev_active_notes = set()
    while True:
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
        if state['show_devices']:
            if shown_at and (time.time() - shown_at > DEVICE_DISPLAY_TIME):
                state['show_devices'] = False

        now = time.time()
        note_changed = False
        for port in inputs:
            for msg in port.iter_pending():
                if msg.type == 'note_on' and msg.velocity > 0:
                    if debounce_note_event(msg.note, now):
                        state['channel'] = msg.channel + 1
                        state['active_notes'].add(msg.note)
                        note_changed = True
                elif (msg.type == 'note_off') or (msg.type == 'note_on' and msg.velocity == 0):
                    if debounce_note_event(msg.note, now):
                        state['channel'] = msg.channel + 1
                        if msg.note in state['active_notes']:
                            state['active_notes'].remove(msg.note)
                        note_changed = True
                elif msg.type == 'control_change':
                    state['channel'] = msg.channel + 1
                    if state['cc'] != msg.control:
                        state['toprow_values_flash_until']['cc'] = now + FLASH_TIME
                    if state['cc_val'] != msg.value:
                        state['toprow_values_flash_until']['val'] = now + FLASH_TIME
                    state['cc'] = msg.control
                    state['cc_val'] = msg.value
        # Flash logic for CH value
        if prev_ch != state['channel']:
            state['toprow_values_flash_until']['ch'] = now + FLASH_TIME
        prev_ch = state['channel']

        # Latching logic: If we just released the last note, latch the previous active_notes set
        if note_changed:
            if not state['active_notes'] and prev_active_notes:
                # All notes released, latch previous set
                state['bubble_latched_notes'] = sorted(prev_active_notes)
                if 3 <= len(prev_active_notes) <= 6:
                    chord_str, root, quality, bass, unknown = detect_chord(prev_active_notes)
                    state['chord_name'] = chord_str
                    state['chord_root'] = root
                    state['chord_quality'] = quality
                    state['chord_bass'] = bass
                    state['unknown_chord'] = unknown
                    if not unknown:
                        state['last_chord_persist'] = chord_str
                        state['last_chord_time'] = now
                else:
                    state['chord_name'] = ""
                    state['unknown_chord'] = False
            elif state['active_notes']:
                sorted_notes = sorted(state['active_notes'])
                state['bubble_latched_notes'] = []
                if 3 <= len(sorted_notes) <= 6:
                    chord_str, root, quality, bass, unknown = detect_chord(sorted_notes)
                    state['chord_name'] = chord_str
                    state['chord_root'] = root
                    state['chord_quality'] = quality
                    state['chord_bass'] = bass
                    state['unknown_chord'] = unknown
                    if not unknown:
                        state['last_chord_persist'] = chord_str
                        state['last_chord_time'] = now
                else:
                    state['chord_name'] = ""
                    state['unknown_chord'] = False
            prev_active_notes = set(state['active_notes'])
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
