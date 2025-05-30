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
BUBBLE_FLASH_TIME = 0.08     # length of flash for note bubbles

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
    'bubble_invert_notes': set(),      # notes currently being held for bubble inversion
    'bubble_latched_notes': [],        # latched notes for display
    'bubble_last_changed': 0,
    'bubble_invert_until': {},         # note: time to keep inverting bubble after release
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

def draw_bubble_notes(draw, y, note_names, held_notes, font, invert_bubbles, invert_until):
    """Draw each note in a rounded rectangle 'bubble', vertically centered text.
    If invert_bubbles is True for a note, invert that bubble (held down), else normal.
    """
    padd_x = 8
    padd_y = 4
    spacing = 6
    bubble_h = max(get_text_size("A", font)[1] + 2 * padd_y, 24)
    bubble_w = []
    for name in note_names:
        w, h = get_text_size(name, font)
        bubble_w.append(w + 2 * padd_x)
    total_w = sum(bubble_w) + spacing * (len(note_names) - 1)
    x = (DISPLAY_WIDTH - total_w) // 2
    now = time.time()
    for i, name in enumerate(note_names):
        w, h = get_text_size(name, font)
        bw = bubble_w[i]
        # Which note does this bubble represent?
        try:
            note_val = held_notes[i]
        except IndexError:
            note_val = None
        # Decide invert
        invert = False
        if note_val is not None:
            invert = note_val in invert_bubbles or (now < invert_until.get(note_val, 0))
        # Rectangle (invert bubble fill)
        if invert:
            draw.rounded_rectangle((x, y, x + bw, y + bubble_h), radius=8, outline=255, fill=255)
            draw.text((x + (bw - w) // 2, y + (bubble_h - h) // 2), name, font=font, fill=0)
        else:
            draw.rounded_rectangle((x, y, x + bw, y + bubble_h), radius=8, outline=255, fill=0)
            draw.text((x + (bw - w) // 2, y + (bubble_h - h) // 2), name, font=font, fill=255)
        x += bw + spacing

def update_display():
    while True:
        with canvas(device) as draw:
            if state['show_devices']:
                # Device list display
                devices = filter_device_names(state['devices'])
                font = font_device
                line_h = get_text_size("A", font)[1] + 2
                # lines per screen
                lines_per_screen = DISPLAY_HEIGHT // line_h
                n_devices = len(devices)
                scroll_needed = n_devices > lines_per_screen
                now = time.time()
                # Scroll logic: every DEVICE_DISPLAY_TIME, scroll to next page
                if scroll_needed:
                    total_pages = n_devices - lines_per_screen + 1
                    page_time = DEVICE_DISPLAY_TIME / max(1, total_pages)
                    page = int((now - state['device_scroll_time']) // page_time) % total_pages
                else:
                    page = 0
                y = 0
                for idx in range(page, min(page + lines_per_screen, n_devices)):
                    draw.text((0, y), devices[idx], font=font, fill=255)
                    y += line_h
            else:
                # Info screen
                # 1. Top row: CH, CC, VAL
                draw_toprow(draw, 0, state)

                # 2. Notes - bubble notes, big
                # Show active notes if any, else latched notes
                if state['active_notes']:
                    notes_to_display = [midi_note_to_name(n) for n in sorted(state['active_notes'])]
                    note_vals = sorted(state['active_notes'])
                elif state['bubble_latched_notes']:
                    notes_to_display = [midi_note_to_name(n) for n in state['bubble_latched_notes']]
                    note_vals = state['bubble_latched_notes']
                else:
                    notes_to_display = []
                    note_vals = []
                # Bubble y center
                bubble_font = font_info_big
                bubble_h = max(get_text_size("A", bubble_font)[1] + 8, 28)
                bubble_y = (DISPLAY_HEIGHT - bubble_h - 2 - get_text_size("A", font_info)[1]) // 2
                if notes_to_display:
                    draw_bubble_notes(
                        draw, bubble_y, notes_to_display, note_vals,
                        font=bubble_font,
                        invert_bubbles=state['bubble_invert_notes'],
                        invert_until=state['bubble_invert_until']
                    )
                else:
                    draw.text((DISPLAY_WIDTH // 2 - 10, bubble_y), "--", font=bubble_font, fill=128)

                # 3. Chord name, centered, small font, at bottom
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
        time.sleep(0.08)

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
    prev_chord = ''
    while True:
        # Device hotplug
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
                        # Invert bubble for this note
                        state['bubble_invert_notes'].add(msg.note)
                        state['bubble_invert_until'][msg.note] = now + BUBBLE_FLASH_TIME
                        state['bubble_last_changed'] = now
                elif (msg.type == 'note_off') or (msg.type == 'note_on' and msg.velocity == 0):
                    if debounce_note_event(msg.note, now):
                        state['channel'] = msg.channel + 1
                        if msg.note in state['active_notes']:
                            state['active_notes'].remove(msg.note)
                        note_changed = True
                        # Remove inversion for this note after short flash
                        state['bubble_invert_notes'].discard(msg.note)
                        state['bubble_invert_until'][msg.note] = now + BUBBLE_FLASH_TIME
                        state['bubble_last_changed'] = now
                elif msg.type == 'control_change':
                    state['channel'] = msg.channel + 1
                    # Only flash CC/VAL if value changed
                    if state['cc'] != msg.control:
                        state['toprow_values_flash_until']['cc'] = now + FLASH_TIME
                    if state['cc_val'] != msg.value:
                        state['toprow_values_flash_until']['val'] = now + FLASH_TIME
                    state['cc'] = msg.control
                    state['cc_val'] = msg.value
        # Update top row flash for channel change
        if state['active_notes']:
            ch = min([msg.channel + 1 for port in inputs for msg in port.iter_pending() if hasattr(msg, 'channel')], default=state['channel'])
            if state['toprow_last'].get('ch') != ch:
                state['toprow_values_flash_until']['ch'] = now + FLASH_TIME
            state['toprow_last']['ch'] = ch
        # Update note and chord state, latching logic
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
        # Remove bubbles from invert after their flash time
        expired = [n for n, t in state['bubble_invert_until'].items() if now > t]
        for n in expired:
            state['bubble_invert_notes'].discard(n)
            del state['bubble_invert_until'][n]
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
