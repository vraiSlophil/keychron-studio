#!/usr/bin/env python3
"""
Privileged HID helper for the Keychron VIA interface — single source of truth for
all raw-HID I/O. Runs as ROOT (invoked via pkexec by the GUI).

Reads one JSON request on stdin, writes one JSON response on stdout:
    request  = {"ops": [ {"op": "...", ...}, ... ]}
    response = {"ok": true, "results": [...]} | {"ok": false, "error": "..."}

Security posture:
 - Whitelisted ops only; unknown ops rejected.
 - Every index/length is bounds-checked before any device write.
 - No shell, no eval, no network. The hidraw node is auto-detected (never taken
   from the request): the wired interface exposing VIA usage page 0xFF60.

VIA command IDs verified against qmk_firmware/quantum/via.h (protocol v0x0D).
"""
import os, sys, json, glob, select

REPORT_LEN = 32
CHUNK = 28  # max payload for dynamic_keymap get/set buffer

# VIA command ids (via.h)
C_GET_PROTOCOL_VERSION     = 0x01
C_GET_KEYBOARD_VALUE       = 0x02
C_DK_SET_KEYCODE           = 0x05
C_DK_RESET                 = 0x06
C_EEPROM_RESET             = 0x0A
C_DK_MACRO_GET_COUNT       = 0x0C
C_DK_MACRO_GET_BUFFER_SIZE = 0x0D
C_DK_MACRO_GET_BUFFER      = 0x0E
C_DK_MACRO_SET_BUFFER      = 0x0F
C_DK_GET_LAYER_COUNT       = 0x11
C_DK_GET_BUFFER            = 0x12
C_DK_SET_BUFFER            = 0x13
KV_LAYOUT_OPTIONS = 0x02

class HidError(Exception): pass

def find_via_node():
    for h in glob.glob('/sys/class/hidraw/hidraw*'):
        try:
            with open(os.path.join(h, 'device', 'report_descriptor'), 'rb') as f:
                desc = f.read()
        except OSError:
            continue
        parent = os.path.realpath(os.path.join(h, 'device'))
        if b'\x06\x60\xff' in desc and 'uhid' not in parent:  # 0xFF60, wired
            return '/dev/' + os.path.basename(h)
    return None

class Kbd:
    def __init__(self):
        node = find_via_node()
        if not node:
            raise HidError("interface VIA (0xFF60) filaire introuvable — clavier en mode Cable ?")
        self.node = node
        self.fd = os.open(node, os.O_RDWR)
    def close(self):
        try: os.close(self.fd)
        except OSError: pass
    def xfer(self, cmd, args=b'', timeout=1.5):
        payload = (bytes([cmd]) + args)[:REPORT_LEN]
        payload += b'\x00' * (REPORT_LEN - len(payload))
        os.write(self.fd, b'\x00' + payload)
        r, _, _ = select.select([self.fd], [], [], timeout)
        if not r:
            raise HidError(f"pas de reponse (cmd 0x{cmd:02x})")
        return os.read(self.fd, REPORT_LEN)
    # -- chunked buffer helpers --
    def read_buffer(self, cmd, total):
        out = bytearray(); off = 0
        while off < total:
            sz = min(CHUNK, total - off)
            d = self.xfer(cmd, bytes([(off >> 8) & 0xFF, off & 0xFF, sz]))
            out += d[4:4 + sz]; off += sz
        return bytes(out)
    def write_buffer(self, cmd, data):
        off = 0; total = len(data)
        while off < total:
            sz = min(CHUNK, total - off)
            self.xfer(cmd, bytes([(off >> 8) & 0xFF, off & 0xFF, sz]) + data[off:off + sz])
            off += sz

def _layers(kb):        return kb.xfer(C_DK_GET_LAYER_COUNT)[1]
def _macro_bufsize(kb):
    d = kb.xfer(C_DK_MACRO_GET_BUFFER_SIZE); return (d[1] << 8) | d[2]

# ---------------- op handlers ----------------
def op_read_info(kb, _):
    d = kb.xfer(C_GET_PROTOCOL_VERSION); proto = (d[1] << 8) | d[2]
    d = kb.xfer(C_GET_KEYBOARD_VALUE, bytes([KV_LAYOUT_OPTIONS]))
    lo = (d[2] << 24) | (d[3] << 16) | (d[4] << 8) | d[5]
    return {"node": kb.node, "protocol": proto, "layers": _layers(kb),
            "macro_count": kb.xfer(C_DK_MACRO_GET_COUNT)[1],
            "macro_buffer_size": _macro_bufsize(kb), "layout_options": lo}

def op_get_keymap(kb, o):
    rows = int(o["rows"]); cols = int(o["cols"])
    if not (1 <= rows <= 16 and 1 <= cols <= 32):
        raise HidError("dimensions matrice hors bornes")
    layers = _layers(kb)
    total = layers * rows * cols * 2
    raw = kb.read_buffer(C_DK_GET_BUFFER, total)
    km = []
    for l in range(layers):
        grid = []
        for r in range(rows):
            row = []
            for c in range(cols):
                i = (l * rows * cols + r * cols + c) * 2
                row.append((raw[i] << 8) | raw[i + 1])
            grid.append(row)
        km.append(grid)
    return {"layers": layers, "rows": rows, "cols": cols, "keymap": km}

def op_set_keycode(kb, o):
    layer = int(o["layer"]); row = int(o["row"]); col = int(o["col"]); kc = int(o["keycode"])
    if not (0 <= layer <= 15 and 0 <= row <= 15 and 0 <= col <= 31 and 0 <= kc <= 0xFFFF):
        raise HidError("parametres set_keycode hors bornes")
    kb.xfer(C_DK_SET_KEYCODE, bytes([layer, row, col, (kc >> 8) & 0xFF, kc & 0xFF]))
    return {"set": [layer, row, col, kc]}

def op_backup(kb, o):
    rows = int(o["rows"]); cols = int(o["cols"]); layers = _layers(kb)
    km = kb.read_buffer(C_DK_GET_BUFFER, layers * rows * cols * 2)
    mac = kb.read_buffer(C_DK_MACRO_GET_BUFFER, _macro_bufsize(kb))
    return {"layers": layers, "rows": rows, "cols": cols,
            "keymap_hex": km.hex(), "macros_hex": mac.hex()}

def op_restore(kb, o):
    km = bytes.fromhex(o["keymap_hex"]); mac = bytes.fromhex(o["macros_hex"])
    rows = int(o["rows"]); cols = int(o["cols"]); layers = _layers(kb)
    if len(km) != layers * rows * cols * 2:
        raise HidError("taille keymap incompatible avec le clavier")
    if len(mac) != _macro_bufsize(kb):
        raise HidError("taille macros incompatible avec le clavier")
    kb.write_buffer(C_DK_SET_BUFFER, km)
    kb.write_buffer(C_DK_MACRO_SET_BUFFER, mac)
    return {"restored": True}

def op_keymap_reset(kb, _):
    kb.xfer(C_DK_RESET); return {"keymap_reset": True}

def op_eeprom_reset(kb, _):
    kb.xfer(C_EEPROM_RESET); return {"eeprom_reset": True}

OPS = {
    "read_info": op_read_info, "get_keymap": op_get_keymap, "set_keycode": op_set_keycode,
    "backup": op_backup, "restore": op_restore,
    "keymap_reset": op_keymap_reset, "eeprom_reset": op_eeprom_reset,
}

def main():
    try:
        req = json.load(sys.stdin); ops = req["ops"]
        if not isinstance(ops, list): raise ValueError("'ops' doit etre une liste")
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"requete invalide: {e}"})); return 2
    kb = None
    try:
        kb = Kbd()
        results = []
        for o in ops:
            name = o.get("op")
            if name not in OPS: raise HidError(f"op inconnue: {name!r}")
            results.append(OPS[name](kb, o))
        print(json.dumps({"ok": True, "results": results})); return 0
    except (HidError, PermissionError, OSError, KeyError, ValueError) as e:
        print(json.dumps({"ok": False, "error": str(e)})); return 1
    finally:
        if kb: kb.close()

if __name__ == "__main__":
    sys.exit(main())
