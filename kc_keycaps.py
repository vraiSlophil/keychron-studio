"""National keycap legends for the on-screen keyboard, with modifier levels.

Loads keycaps/<layout>.json. A HID-usage entry is either:
  - a string  -> single legend (letters get generic Shift/CapsLock casing), or
  - an object  {"base","shift","altgr","shift_altgr"} -> per-level legends.
Cosmetic only; the real keycode is unchanged. Add a layout by dropping a JSON
file in keycaps/."""
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

def _cased(s, shift, caps_lock):
    if len(s) == 1 and s.isalpha():
        return s.upper() if (shift ^ caps_lock) else s.lower()
    return s

def legend(code, caps, shift=False, altgr=False, caps_lock=False):
    """Return the character to show for `code` under the given modifiers."""
    entry = caps.get(code)
    if isinstance(entry, dict):
        if altgr and shift and entry.get("shift_altgr"):
            return entry["shift_altgr"]
        if altgr and entry.get("altgr"):
            return entry["altgr"]
        if shift and entry.get("shift"):
            return entry["shift"]
        return _cased(entry.get("base", ""), shift, caps_lock)
    base = entry if isinstance(entry, str) else kc_keycodes.label(code)
    return _cased(base, shift, caps_lock)
