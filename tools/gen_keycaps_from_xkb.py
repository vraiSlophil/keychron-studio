#!/usr/bin/env python3
"""Generate a keycaps/<layout>.json from an X11 xkb symbols definition.

Reads /usr/share/X11/xkb/symbols/<file>, extracts the requested variant section,
and resolves each key's four levels (base / shift / AltGr / Shift+AltGr) to the
characters printed on a physical keycap. Keysym names are resolved via GDK, dead
keys via a small spacing-glyph table. Letters are stored as a base lowercase char
(case is applied at runtime by kc_case), other keys as explicit level objects.

Usage:  python3 tools/gen_keycaps_from_xkb.py fr oss > keycaps/fr.json
"""
import re, json, sys, os, gi
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import kc_evdev

DEAD = {"dead_circumflex": "^", "dead_diaeresis": "¨", "dead_tilde": "˜", "dead_grave": "`",
        "dead_acute": "´", "dead_cedilla": "¸", "dead_caron": "ˇ", "dead_ogonek": "˛",
        "dead_breve": "˘", "dead_abovering": "˚", "dead_doubleacute": "˝", "dead_macron": "¯",
        "dead_belowdot": "·", "dead_hook": "ˀ", "dead_horn": "ʼ", "dead_stroke": "/"}

def sym_to_char(name):
    name = name.strip()
    if not name or name in ("NoSymbol", "VoidSymbol"):
        return ""
    if name.startswith("dead_"):
        return DEAD.get(name, "")
    if name.startswith("0x"):
        v = int(name, 16)
        return chr(v & 0xffffff) if (v & 0xff000000) == 0x01000000 else (chr(v) if v < 0x110000 else "")
    kv = Gdk.keyval_from_name(name)
    if not kv:
        return ""
    u = Gdk.keyval_to_unicode(kv)
    return chr(u) if u else ""

def name_to_evdev(n):
    sp = {"TLDE": 41, "BKSL": 43, "LSGT": 86, "SPCE": 57}
    if n in sp:
        return sp[n]
    m = re.match(r'A([EDCB])(\d\d)$', n)
    return {"E": 1, "D": 15, "C": 29, "B": 43}[m.group(1)] + int(m.group(2)) if m else None

def evdev_to_hid(ev):
    h = kc_evdev.EVDEV_TO_HID.get(ev)
    return h[-1] if isinstance(h, tuple) else h

def generate(layout, variant, name):
    txt = open(f"/usr/share/X11/xkb/symbols/{layout}", encoding="utf-8").read()
    sec = re.search(rf'xkb_symbols "{variant}"\s*\{{(.*?)\n\}};', txt, re.S).group(1)
    out = {"_name": name}
    for km in re.finditer(r'key\s+<(\w+)>\s*\{\s*\[([^\]]+)\]', sec):
        ev = name_to_evdev(km.group(1))
        hid = evdev_to_hid(ev) if ev is not None else None
        if hid is None:
            continue
        lv = [sym_to_char(s) for s in ([x.strip() for x in km.group(2).split(",")] + [""] * 4)[:4]]
        l0, l1, l2, l3 = lv
        if not l0:
            continue
        key = f"0x{hid:02X}"
        if len(l0) == 1 and l0.isalpha() and l1 == l0.upper():   # letter: case applied at runtime
            e = {"base": l0}
            if l2 and l2 not in (l0, l0.upper()): e["altgr"] = l2
            if l3 and l3 not in (l0, l0.upper()): e["shift_altgr"] = l3
            out[key] = l0 if len(e) == 1 else e
        else:
            e = {"base": l0}
            if l1 and l1 != l0: e["shift"] = l1
            if l2 and l2 != l0: e["altgr"] = l2
            if l3 and l3 != l0: e["shift_altgr"] = l3
            out[key] = l0 if len(e) == 1 else e
    return out

if __name__ == "__main__":
    layout = sys.argv[1] if len(sys.argv) > 1 else "fr"
    variant = sys.argv[2] if len(sys.argv) > 2 else "oss"
    name = sys.argv[3] if len(sys.argv) > 3 else f"{layout} ({variant})"
    json.dump(generate(layout, variant, name), sys.stdout, ensure_ascii=False, indent=2)
    print()
