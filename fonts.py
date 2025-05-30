import os
from PIL import ImageFont

FONT_DIR = os.path.expanduser("~/midihub/fonts")

# Mapping of logical font roles to font files and sizes
FONT_FILES = {
    # Topline
    "top_label": ("ter-u14n.pil", 14),
    "top_value": ("ter-u14b.pil", 14),
    # Chord name
    "chord_normal": ("ter-u14n.pil", 14),
    "chord_bold": ("ter-u14b.pil", 14),
    # Notes
    "note": ("ter-u18b.pil", 18),
    # Device list
    "device": ("ter-u14n.pil", 14),
}

def load_font(fontfile, size):
    path = os.path.join(FONT_DIR, fontfile)
    # The .pil fonts need the .pbm next to them, PIL will find the .pbm automatically
    return ImageFont.load(path)

def load_fonts():
    fonts = {}
    for key, (fname, size) in FONT_FILES.items():
        try:
            fonts[key] = load_font(fname, size)
        except Exception as e:
            raise RuntimeError(f"Could not load font {fname}: {e}")
    return fonts

# Usage: from fonts import load_fonts; fonts = load_fonts(); fonts["top_label"]
