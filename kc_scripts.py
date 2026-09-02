"""Bind a keyboard key (mapped to F13–F24) to a shell command via GNOME's custom
keyboard shortcuts (gsettings). No custom daemon: we reuse GNOME, which is
maintained and works on Wayland. Privileged commands are wrapped with `pkexec`.

Abstracted behind set_trigger()/list_triggers() so an evdev/keyd backend can be
added later without touching the GUI."""
from gi.repository import Gio

_BASE   = "org.gnome.settings-daemon.plugins.media-keys"
_CUSTOM = "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"
_PREFIX = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"

def _slot_path(accel):
    return f"{_PREFIX}keychron-studio-{accel.lower()}/"

def set_trigger(accel, command, privileged=False):
    """accel e.g. 'F13'. command is a shell command run on that key press."""
    if privileged:
        command = "pkexec " + command
    media = Gio.Settings.new(_BASE)
    paths = list(media.get_strv("custom-keybindings"))
    p = _slot_path(accel)
    if p not in paths:
        paths.append(p); media.set_strv("custom-keybindings", paths)
    cb = Gio.Settings.new_with_path(_CUSTOM, p)
    cb.set_string("name", f"Keychron Studio · {accel}")
    cb.set_string("command", command)
    cb.set_string("binding", accel)

def clear_trigger(accel):
    media = Gio.Settings.new(_BASE)
    p = _slot_path(accel)
    paths = [x for x in media.get_strv("custom-keybindings") if x != p]
    media.set_strv("custom-keybindings", paths)

def list_triggers():
    media = Gio.Settings.new(_BASE)
    out = {}
    for p in media.get_strv("custom-keybindings"):
        if p.startswith(_PREFIX + "keychron-studio-"):
            cb = Gio.Settings.new_with_path(_CUSTOM, p)
            out[cb.get_string("binding")] = cb.get_string("command")
    return out
