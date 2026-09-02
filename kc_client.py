"""GUI-side bridge to the privileged HID helper (kc_helper.py).

All keyboard I/O goes through here. If the VIA node is directly accessible (dev
setup with a udev uaccess rule) the helper runs in-process-user for speed; in the
locked-down deployment the node is root-only, so it is invoked via `pkexec`
(one password prompt per call/batch). This keeps privilege handling in one place.
"""
import os, sys, json, glob, subprocess

HELPER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kc_helper.py")

class HelperError(Exception):
    pass

def _node_user_accessible():
    for h in glob.glob('/sys/class/hidraw/hidraw*'):
        try:
            with open(os.path.join(h, 'device', 'report_descriptor'), 'rb') as f:
                desc = f.read()
        except OSError:
            continue
        parent = os.path.realpath(os.path.join(h, 'device'))
        if b'\x06\x60\xff' in desc and 'uhid' not in parent:
            node = '/dev/' + os.path.basename(h)
            return os.access(node, os.R_OK | os.W_OK)
    return False

def call(ops, force_pkexec=False):
    """Run a batch of ops; returns the list of results or raises HelperError."""
    req = json.dumps({"ops": ops}).encode()
    if not force_pkexec and _node_user_accessible():
        cmd = [sys.executable, HELPER]
    else:
        cmd = ["pkexec", sys.executable, HELPER]
    try:
        p = subprocess.run(cmd, input=req, capture_output=True, timeout=60)
    except FileNotFoundError as e:
        raise HelperError(f"commande introuvable: {e}")
    if p.returncode == 126 or p.returncode == 127:
        raise HelperError("autorisation refusée (pkexec).")
    try:
        resp = json.loads(p.stdout.decode() or "{}")
    except json.JSONDecodeError:
        raise HelperError(f"réponse helper invalide: {p.stderr.decode()[:200]}")
    if not resp.get("ok"):
        raise HelperError(resp.get("error", "erreur inconnue"))
    return resp["results"]
