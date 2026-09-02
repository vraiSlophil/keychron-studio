"""Decode a VIA/KLE 'layouts.keymap' into placed keys with their matrix (row,col).

Implements the subset of the KLE format used by VIA definitions: per-key property
dicts carry x/y offsets (relative) and w/h sizes that apply to the next key only.
Each string item is a key whose label is 'row,col'."""
import json

def decode(def_path):
    with open(def_path) as f:
        d = json.load(f)
    rows = d["matrix"]["rows"]; cols = d["matrix"]["cols"]
    kle = d["layouts"]["keymap"]
    keys = []; y = 0.0
    for line in kle:
        x = 0.0; w = h = 1.0
        for item in line:
            if isinstance(item, dict):
                x += item.get("x", 0.0)
                y += item.get("y", 0.0)
                w = item.get("w", 1.0)
                h = item.get("h", 1.0)
            else:  # "r,c"
                r, c = (int(v) for v in item.split(","))
                keys.append({"x": x, "y": y, "w": w, "h": h, "row": r, "col": c})
                x += w; w = h = 1.0
        y += 1.0
    return {"name": d.get("name"), "rows": rows, "cols": cols, "keys": keys}
