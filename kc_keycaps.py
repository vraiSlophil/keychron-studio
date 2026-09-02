"""National keycap legends for the on-screen keyboard.

Loads keycaps/<layout>.json (HID-usage hex -> printed character). This is a
cosmetic overlay so the rendered board matches the user's physical keycaps
(e.g. French AZERTY); the real keycode is unchanged and shown in the tooltip.
Add a layout by dropping a new JSON file in keycaps/."""
import json, os
import kc_keycodes

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keycaps")
DEFAULT = "us"

def available():
    try:
        return sorted(f[:-5] for f in os.listdir(_DIR) if f.endswith(".json"))
    except OSError:
        return [DEFAULT]

def load(layout):
    try:
        with open(os.path.join(_DIR, f"{layout}.json"), encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        raw = {}
    return {int(k, 16): v for k, v in raw.items() if k.startswith("0x")}

def display_name(layout):
    try:
        with open(os.path.join(_DIR, f"{layout}.json"), encoding="utf-8") as f:
            return json.load(f).get("_name", layout.upper())
    except (OSError, ValueError):
        return layout.upper()

def legend(code, caps):
    """caps = dict from load(); returns the physical-cap character or the keycode label."""
    if code in caps:
        return caps[code]
    return kc_keycodes.label(code)
