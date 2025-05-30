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

DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 64

# Font paths
FONT_DIR = os.path.expanduser("~/midihub/fonts")
FONT_DEVICE_LIST = os.path.join(FONT_DIR, "miniwi-8.bdf")
FONT_INFO = os.path.join(FONT_DIR, "RobotoMono-VariableFont_wght.ttf")

# Load fonts
def load_fonts():
    try:
        font_device = ImageFont.load(FONT_DEVICE_LIST)
    except Exception:
        font_device = None
    try:
        font_info_big = ImageFont.truetype(FONT_INFO, 22)
    except Exception:
        font_info_big = None
    try:
        font_info = ImageFont.truetype(FONT_INFO, 14)
    except Exception:
        font_info = None
    try:
        font_info_small = ImageFont.truetype(FONT_INFO, 11)
    except Exception:
        font_info_small = None
    return font_device, font_info_big, font_info, font_info_small

font_device, font_info_big, font_info, font_info_small = load_fonts()

TRIGGER_FILE = "/tmp/midihub_devices.trigger"
DEVICE_DISPLAY_TIME = 4      # seconds
NOTE_DEBOUNCE_TIME = 0.03
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
    'toprow_values_flash_until': {'ch': 0, 'cc': 0, 'val': 0},
    'toprow_last': {'ch': None, 'cc': None, 'val': None},
    'last_chord_flash_until': 0,
    'device_scroll_time': 0,
    'device_name_scroll_time': 0,
    'bubble_latched_notes': [],        # latched notes for display
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
        bbox = font.getbbox(text)
        return (bbox[2] - bbox[0], bbox[3] - bbox[1])
    else:
        return (len(text) * 6, 10)

def draw_toprow(draw, y, state):
    """Draw CH, CC, VAL on top row. Only values flash when changed."""
    ch = str(state['channel']) if state['channel'] is not None else '-'
    cc = str(state['cc']) if state['cc'] is not None else '-'
    val = str(state['cc_val']) if state['cc_val'] is not None else '-'

    font = font_info
    labels = ['CH:', 'CC:', 'VAL:']
    values = [ch, cc, val]
    flash_until = state.get('toprow_values_flash_until', {})
    last_vals = state.get('toprow_last', {})

    # Compute total width dynamically with small paddings
    padd = 2
    sep = 4
    parts = []
    for label, value in zip(labels, values):
        lw, lh = get_text_size(label, font)
        vw, vh = get_text_size(value, font)
        parts.append((label, lw, lh, value, vw, vh))
    total_w = sum(lw + padd + vw for _, lw, _, _, vw, _ in parts) + sep * (len(parts) - 1)
    x = (DISPLAY_WIDTH - total_w) // 2

    now = time.time()
    for i, (label, lw, lh, value, vw, vh) in enumerate(parts):
        # Draw label (never inverted)
        draw.text((x, y), label, font=font, fill=255)
        x += lw + padd
        # Draw value (invert only if flash is active for this field)
        invert = now < flash_until.get(['ch','cc','val'][i], 0)
        if invert:
            draw.rectangle((x, y, x + vw, y + vh), outline=255, fill=255)
            draw.text((x, y), value, font=font, fill=0)
        else:
            draw.text((x, y), value, font=font, fill=255)
        x += vw + sep

def draw_bubble_notes(draw, y, note_names, held_notes, font, held_set):
    """Draw note 'bubbles' in one line, tightly packed, with vertical centering.
       Invert bubble if note is currently held."""
    padd_x = 4  # Small horizontal padding
    padd_y = 2  # Small vertical padding
    spacing = 2  # Reduced spacing between bubbles
    bubble_h = get_text_size("A", font)[1] + padd_y * 2  # Bubble height just fits the font
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
        # Center text vertically in the bubble
        text_y = y + (bubble_h - h) // 2
        if invert:
            draw.rounded_rectangle((x, y, x + bw, y + bubble_h), radius=7, outline=255, fill=255)
            draw.text((x + (bw - w) // 2, text_y), name, font=font, fill=0)
        else:
            draw.rounded_rectangle((x, y, x + bw, y + bubble_h), radius=7, outline=255, fill=0)
            draw.text((x + (bw - w) // 2, text_y), name, font=font, fill=255)
        x += bw + spacing

def update_display():
    while True:
        with canvas(device) as draw:
            if state['show_devices']:
                # Smooth pixel-based device list scrolling
                devices = filter_device_names(state['devices'])
                font = font_device
                line_h = get_text_size("A", font)[1] + 2
                n_devices = len(devices)
                visible_lines = DISPLAY_HEIGHT // line_h
                scroll_pixels = int((time.time() - state['device_scroll_time']) * 20)  # 20 px/sec scroll speed
                total_height = n_devices * line_h
                offset = scroll_pixels % total_height
                for i in range(visible_lines + 1):  # +1 to fill screen at wrap
                    idx = (i + offset // line_h) % n_devices
                    y = i * line_h - (offset % line_h)
                    if 0 <= y < DISPLAY_HEIGHT:
                        draw.text((0, y), devices[idx], font=font, fill=255)
            else:
                # Info screen
                draw_toprow(draw, 0, state)

                # Bubbles: tighter, smaller, more per line
                # Use new bubble layout logic
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
                bubble_font = font_info_big
                bubble_h = get_text_size("A", bubble_font)[1] + 4
                bubble_y = (DISPLAY_HEIGHT - bubble_h - 2 - get_text_size("A", font_info)[1]) // 2
                if notes_to_display:
                    draw_bubble_notes(
                        draw, bubble_y, notes_to_display, note_vals,
                        font=bubble_font,
                        held_set=held_set
                    )
                else:
                    draw.text((DISPLAY_WIDTH // 2 - 10, bubble_y), "--", font=bubble_font, fill=128)

                # Chord output logic
                chord_font = font_info
                chord_to_display = ""
                if len(note_vals) >= 3 and state['chord_name']:
                    chord_to_display = state['chord_name']
                elif state['last_chord_persist']:
                    chord_to_display = state['last_chord_persist']
                chord_invert = (time.time() < state.get('last_chord_flash_until', 0))
                w, h = get_text_size(chord_to_display, chord_font)
                chord_y = DISPLAY_HEIGHT - h - 2
                if chord_to_display:
                    if chord_invert:
                        draw.rectangle(
                            (max(0, (DISPLAY_WIDTH - w) // 2), chord_y, min(DISPLAY_WIDTH, (DISPLAY_WIDTH + w) // 2), chord_y + h),
                            outline=255, fill=255
                        )
                        draw.text((max(0, (DISPLAY_WIDTH - w) // 2), chord_y), chord_to_display, font=chord_font, fill=0)
                    else:
                        draw.text((max(0, (DISPLAY_WIDTH - w) // 2), chord_y), chord_to_display, font=chord_font, fill=255)
        time.sleep(0.04)  # Faster update for smoother display and better VAL responsiveness

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
    prev_cc = None
    prev_val = None
    while True:
        # Device update
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

        # MIDI handling
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
        # Latching, chord, bubble update logic
        if note_changed or (not state['active_notes'] and state['bubble_latched_notes']):
            sorted_notes = sorted(state['active_notes'])
            names = [midi_note_to_name(n) for n in sorted_notes]
            state['all_note_names'] = names
            if sorted_notes:
                # Chord detection and persist
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
                # Latch notes for display
                state['bubble_latched_notes'] = sorted_notes.copy()
            else:
                # On all keys released: keep latched notes
                pass
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
