"""
Keycode catalogue for the Keychron K5 v2 (VIA protocol v12).

All 16-bit values are taken verbatim from the keyboard's own QMK firmware
(Keychron/qmk_firmware @ wls_2025q1, quantum/keycodes.h) plus the Keychron
customKeycodes from the VIA definition (QK_KB_0 + index). Group ids are stable
keys resolved to display names through kc_i18n (group.<id>).
"""
import json, os

CODE2LABEL = {0x0000: "▽", 0x0001: "▁"}          # KC_NO, KC_TRANSPARENT
for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
    CODE2LABEL[0x0004 + i] = c
for i, c in enumerate("1234567890"):
    CODE2LABEL[0x001E + i] = c
CODE2LABEL.update({
    0x0028: "Enter", 0x0029: "Esc", 0x002A: "Bspc", 0x002B: "Tab", 0x002C: "Space",
    0x002D: "-", 0x002E: "=", 0x002F: "[", 0x0030: "]", 0x0031: "\\", 0x0032: "#~",
    0x0033: ";", 0x0034: "'", 0x0035: "`", 0x0036: ",", 0x0037: ".", 0x0038: "/",
    0x0039: "Caps",
    0x0046: "PrtSc", 0x0047: "ScrLk", 0x0048: "Pause",
    0x0049: "Ins", 0x004A: "Home", 0x004B: "PgUp", 0x004C: "Del", 0x004D: "End", 0x004E: "PgDn",
    0x004F: "→", 0x0050: "←", 0x0051: "↓", 0x0052: "↑",
    0x0053: "NumLk", 0x0054: "KP/", 0x0055: "KP*", 0x0056: "KP-", 0x0057: "KP+",
    0x0058: "KPEnt", 0x0059: "KP1", 0x005A: "KP2", 0x005B: "KP3", 0x005C: "KP4",
    0x005D: "KP5", 0x005E: "KP6", 0x005F: "KP7", 0x0060: "KP8", 0x0061: "KP9",
    0x0062: "KP0", 0x0063: "KP.", 0x0064: "ISO\\", 0x0065: "App",
    0x00E0: "LCtrl", 0x00E1: "LShift", 0x00E2: "LAlt", 0x00E3: "LGui",
    0x00E4: "RCtrl", 0x00E5: "RShift", 0x00E6: "RAlt", 0x00E7: "RGui",
})
for i in range(12):
    CODE2LABEL[0x003A + i] = f"F{i+1}"
    CODE2LABEL[0x0068 + i] = f"F{i+13}"
CODE2LABEL.update({
    0x00A5: "Power", 0x00A6: "Sleep", 0x00A7: "Wake",
    0x00A8: "Mute", 0x00A9: "Vol+", 0x00AA: "Vol-",
    0x00AB: "Next", 0x00AC: "Prev", 0x00AD: "Stop", 0x00AE: "Play",
    0x00AF: "Media", 0x00B0: "Eject", 0x00B1: "Mail", 0x00B2: "Calc",
    0x00B3: "MyPC", 0x00B4: "Search", 0x00B5: "Home(web)",
    0x00BD: "Bright+", 0x00BE: "Bright-",
    0x7800: "BL On", 0x7801: "BL Off", 0x7802: "BL Tgl", 0x7803: "BL-",
    0x7804: "BL+", 0x7805: "BL Step", 0x7806: "BL Breath",
})

QK_KB_0 = 0x7E00
# layer-switch families (verified: quantum/keycodes.h)
_LAYER_RANGES = [(0x5200, "TO"), (0x5220, "MO"), (0x5240, "DF"),
                 (0x5260, "TG"), (0x5280, "OSL")]

GROUPS = [
    ("letters",     [0x0004 + i for i in range(26)]),
    ("digits",      [0x001E + i for i in range(10)]),
    ("functions",   [0x003A + i for i in range(12)]),
    ("f13_24",      [0x0068 + i for i in range(12)]),
    ("navigation",  [0x0049,0x004A,0x004B,0x004C,0x004D,0x004E,0x004F,0x0050,0x0051,0x0052]),
    ("modifiers",   [0x00E0,0x00E1,0x00E2,0x00E3,0x00E4,0x00E5,0x00E6,0x00E7]),
    ("punctuation", [0x002D,0x002E,0x002F,0x0030,0x0031,0x0032,0x0033,0x0034,0x0035,0x0036,0x0037,0x0038,0x0064]),
    ("editing",     [0x0028,0x0029,0x002A,0x002B,0x002C,0x0039,0x0046,0x0065]),
    ("media",       [0x00A8,0x00A9,0x00AA,0x00AB,0x00AC,0x00AD,0x00AE,0x00AF,0x00B0]),
    ("system",      [0x00A5,0x00A6,0x00A7,0x00BD,0x00BE,0x00B1,0x00B2,0x00B3,0x00B4,0x00B5]),
    ("backlight",   [0x7800,0x7801,0x7802,0x7803,0x7804,0x7805,0x7806]),
    ("layers",      [0x5220+i for i in range(4)] + [0x5200+i for i in range(4)]),
    ("special",     [0x0000,0x0001]),
]

def load_custom_keycodes(def_path):
    try:
        with open(def_path) as f:
            d = json.load(f)
    except OSError:
        return
    codes = []
    for i, ck in enumerate(d.get("customKeycodes", [])):
        code = QK_KB_0 + i
        CODE2LABEL[code] = ck.get("name", f"KB{i}")
        codes.append(code)
    if codes:
        GROUPS.append(("keychron", codes))

def label(code: int) -> str:
    if code in CODE2LABEL:
        return CODE2LABEL[code]
    for base, name in _LAYER_RANGES:
        if base <= code <= base + 0x1F:
            return f"{name}({code - base})"
    return f"0x{code:04X}"

_DEF = os.path.join(os.path.dirname(__file__), "defs", "k5_iso_white.json")
load_custom_keycodes(_DEF)
