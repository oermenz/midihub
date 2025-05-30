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

FONT_DIR = os.path.expanduser("~/midihub/fonts")
FONT_INFO = os.path.join(FONT_DIR, "RobotoMono-VariableFont_wght.ttf")

def load_fonts():
    try:
        font_info = ImageFont.truetype(FONT_INFO, 14)
    except Exception:
        font_info = ImageFont.load_default()
    try:
        font_info_small = ImageFont.truetype(FONT_INFO, 11)
    except Exception:
        font_info_small = font_info
    font_device = ImageFont.load_default()
    return font_device, font_info, font_info_small

font_device, font_info, font_info_small = load_fonts()

TRIGGER_FILE = "/tmp/midihub_devices.trigger"
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
        base = name.split(":")[0].strip()
        base = base.split("[")[0].strip()
        filtered.append(base)
    return filtered

def get_text_size(text, font):
    if font:
        bbox = font.getbbox(text)
        return (bbox[2] - bbox[0], bbox[3] - bbox[1])
    else:
        return (len(text) * 6, 10)

def draw_centered_text(draw, x, y, w, h, text, font, fill):
    text_w, text_h = get_text_size(text, font)
    text_y = y + (h - text_h) // 2
    draw.text((x + (w - text_w) // 2, text_y), text, font=font, fill=fill)

def draw_toprow(draw, y, state):
    ch = str(state['channel']) if state['channel'] is not None else '-'
    cc = str(state['cc']) if state['cc'] is not None else '-'
    val = str(state['cc_val']) if state['cc_val'] is not None else '-'
    font = font_info
    labels = ['CH', 'CC', 'VAL']
    values = [ch, cc, val]
    flash_until = state.get('toprow_values_flash_until', {})
    padd = 2
    sep = 2
    ascent, descent = font.getmetrics()
    maxh = ascent + descent
    parts = []
    for label, value in zip(labels, values):
        lw, lh = get_text_size(label, font)
        vw, vh = get_text_size(value, font)
        parts.append((label, lw, lh, value, vw, vh))
    total_w = sum(lw + padd + vw for _, lw, _, _, vw, _ in parts) + sep * (len(parts) - 1)
    x = (DISPLAY_WIDTH - total_w) // 2
    now = time.time()
    for i, (label, lw, lh, value, vw, vh) in enumerate(parts):
        label_y = y + (maxh - lh) // 2
        draw.text((x, label_y), label, font=font, fill=255)
        x += lw + padd
        invert = now < flash_until.get(['ch','cc','val'][i], 0)
        if invert:
            draw.rectangle((x, y, x + vw, y + maxh), outline=255, fill=255)
            draw_centered_text(draw, x, y, vw, maxh, value, font, fill=0)
        else:
            draw_centered_text(draw, x, y, vw, maxh, value, font, fill=255)
        x += vw + sep

def draw_bubble_notes(draw, region_y, bubbles, font, region_height):
    padd_x = 3
    padd_y = 4
    spacing = 3
    if not bubbles:
        return
    ascent, descent = font.getmetrics()
    text_height = ascent + descent
    bubble_h = text_height + padd_y * 2
    bubble_w = []
    note_names = [b['name'] for b in bubbles]
    for name in note_names:
        w, h = get_text_size(name, font)
        bubble_w.append(w + 2 * padd_x)
    total_w = sum(bubble_w) + spacing * (len(note_names) - 1)
    x = max(0, (DISPLAY_WIDTH - total_w) // 2)
    y_centered = region_y + (region_height - bubble_h) // 2
    for i, b in enumerate(bubbles):
        name = b['name']
        bw = bubble_w[i]
        invert = b['invert']
        if invert:
            draw.rounded_rectangle((x, y_centered, x + bw, y_centered + bubble_h), radius=5, outline=255, fill=255)
            draw_centered_text(draw, x, y_centered, bw, bubble_h, name, font, fill=0)
        else:
            draw.rounded_rectangle((x, y_centered, x + bw, y_centered + bubble_h), radius=5, outline=255, fill=0)
            draw_centered_text(draw, x, y_centered, bw, bubble_h, name, font, fill=255)
        x += bw + spacing

def update_display():
    chord_font = font_info
    chord_text_h = get_text_size("A", chord_font)[1]
    chord_fixed_y = DISPLAY_HEIGHT - chord_text_h
    topline_h = get_text_size("A", font_info)[1]
    topline_y = 0

    def get_bubbles_region():
        top = topline_y + topline_h + 2
        bottom = chord_fixed_y - 2
        region_y = top
        region_h = max(0, bottom - top)
        return region_y, region_h

    while True:
        now = time.time()
        # Gather bubbles to display: held notes (invert), plus latched notes (not invert)
        held_notes = state['held_notes']
        # Remove released notes older than NOTE_LATCH_SHOW
        to_remove = [n for n, t in state['released_notes'].items() if now - t > NOTE_LATCH_SHOW]
        for n in to_remove:
            del state['released_notes'][n]
        # Latched notes: currently released (not held) and still in release window
        latched_notes = set(state['released_notes'].keys()) - held_notes
        # Display: held (inverted, sorted), then latched (not inverted, sorted)
        display_notes = list(sorted(held_notes)) + list(sorted(latched_notes - held_notes))
        display_bubbles = []
        for n in display_notes:
            display_bubbles.append({
                'note': n,
                'name': midi_note_to_name(n),
                'invert': n in held_notes
            })
        with canvas(device) as draw:
            if state['show_devices']:
                devices = filter_device_names(state['devices'])
                font = font_device
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
                draw_toprow(draw, topline_y, state)
                bubble_font = font_info
                region_y, region_h = get_bubbles_region()
                if display_bubbles:
                    draw_bubble_notes(draw, region_y, display_bubbles, font=bubble_font, region_height=region_h)
                else:
                    dash_w, dash_h = get_text_size("--", bubble_font)
                    dash_x = (DISPLAY_WIDTH - dash_w) // 2
                    dash_y = region_y + (region_h - dash_h) // 2
                    draw.text((dash_x, dash_y), "--", font=bubble_font, fill=128)
                # Chord name
                chord_to_display = ""
                # Show chord for held notes (if any), else for most recent latched chord
                chord_notes = set(display_notes)
                if len(chord_notes) >= 3:
                    chord_str, root, quality, bass, unknown = detect_chord(chord_notes)
                    state['chord_name'] = chord_str
                    state['chord_root'] = root
                    state['chord_quality'] = quality
                    state['chord_bass'] = bass
                    state['unknown_chord'] = unknown
                    if not unknown:
                        state['last_chord_persist'] = chord_str
                        state['last_chord_time'] = now
                    chord_to_display = chord_str
                elif state['last_chord_persist']:
                    chord_to_display = state['last_chord_persist']
                chord_invert = (now < state.get('last_chord_flash_until', 0))
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

def debounce_note_event(note, now, note_timestamps, debounce_time=NOTE_DEBOUNCE_TIME):
    last = note_timestamps.get(note, 0)
    if now - last > debounce_time:
        note_timestamps[note] = now
        return True
    return False

def monitor_midi():
    inputs = []
    last_device_list = []
    shown_at = None
    prev_ch = None
    note_timestamps = {}
    prev_held_notes = set()
    # For chord latching window
    last_release_times = {}
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
        if state['show_devices']:
            if shown_at and (time.time() - shown_at > DEVICE_DISPLAY_TIME):
                state['show_devices'] = False

        now = time.time()
        note_changed = False
        for port in inputs:
            for msg in port.iter_pending():
                if msg.type == 'note_on' and msg.velocity > 0:
                    if debounce_note_event(msg.note, now, note_timestamps):
                        state['channel'] = msg.channel + 1
                        state['held_notes'].add(msg.note)
                        # Remove from released notes, if present
                        state['released_notes'].pop(msg.note, None)
                        note_changed = True
                elif (msg.type == 'note_off') or (msg.type == 'note_on' and msg.velocity == 0):
                    if debounce_note_event(msg.note, now, note_timestamps):
                        state['channel'] = msg.channel + 1
                        if msg.note in state['held_notes']:
                            state['held_notes'].remove(msg.note)
                        state['released_notes'][msg.note] = now
                        note_changed = True
                elif msg.type == 'control_change':
                    state['channel'] = msg.channel + 1
                    if state['cc'] != msg.control:
                        state['toprow_values_flash_until']['cc'] = now + FLASH_TIME
                    if state['cc_val'] != msg.value:
                        state['toprow_values_flash_until']['val'] = now + FLASH_TIME
                    state['cc'] = msg.control
                    state['cc_val'] = msg.value
        if prev_ch != state['channel']:
            state['toprow_values_flash_until']['ch'] = now + FLASH_TIME
        prev_ch = state['channel']

        # Chord latching for short chords: if all notes released within 0.1s, latch all for 2s
        if note_changed:
            if len(state['held_notes']) == 0 and len(prev_held_notes) > 0:
                # All notes released, see if last releases happened together
                now = time.time()
                release_times = [state['released_notes'].get(n, now) for n in prev_held_notes]
                if release_times and (max(release_times) - min(release_times) < 0.1):
                    for n in prev_held_notes:
                        state['released_notes'][n] = now
        prev_held_notes = set(state['held_notes'])
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
