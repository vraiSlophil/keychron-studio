# Keychron Studio

Configure a **Keychron K5 (QMK, Version 2)** keyboard locally on Linux — remap keys,
back up/restore your layout, and bind physical keys to shell scripts — talking to the
board directly over the open **VIA/QMK raw-HID protocol**, without any web launcher.

> **Unofficial community project.** Not affiliated with, authorized, or endorsed by
> Keychron. "Keychron" is a trademark of its respective owner. Use at your own risk.

## Why
The official web launcher requires a Chromium browser (WebHID) and, on Linux, raw-HID
permissions — and it can hang during firmware flashing. Keychron Studio speaks the same
open protocol from a small native app, with an explicit privilege-separation model.

## Supported hardware
Developed and verified against the **Keychron K5 Version 2 — ISO, White backlight**
(`vendorId 0x3434 / productId 0x0D54`). Other K5 v2 variants (ANSI/JIS, RGB) use the
same protocol; drop their VIA JSON in `defs/` and point the app at it. Other Keychron
QMK boards are likely compatible but untested.

## Requirements
- Linux with the keyboard connected **by cable** and its switch set to **Cable**
  (the VIA interface is not exposed over Bluetooth).
- Python 3, **PyGObject + GTK 4 + libadwaita** (preinstalled on GNOME).
- The **Scripts** feature uses GNOME custom shortcuts (`gsettings`) — GNOME only.
- `pkexec` (polkit) for privileged keyboard access.

## Security model — privilege separation
The keyboard's raw-HID node is kept **root-only**. The GUI runs unprivileged and performs
all device I/O through a small, auditable helper (`kc_helper.py`) elevated via **pkexec**
(one password prompt per action batch). The helper accepts only a whitelist of bounds-checked
operations, opens no path from its input, and does no shell/network work. See
[`packaging/lockdown.sh`](packaging/lockdown.sh) to enforce root-only access.

A simpler development model (direct user access via a udev `uaccess` rule) is available in
[`packaging/50-keychron-dev.rules`](packaging/50-keychron-dev.rules) — it weakens separation
and re-enables the web launcher; use only if you accept the trade-off.

## Install & run
```bash
git clone <this-repo> keychron-studio && cd keychron-studio
# GNOME already ships the GTK4/libadwaita bindings; nothing to pip-install.
python3 keychron_studio.py
```
To enforce the root-only model (recommended), run once and replug:
```bash
./packaging/lockdown.sh
```

### Desktop launcher (double-click)
To get a clickable icon in your GNOME app grid instead of running from a terminal:
```bash
./packaging/install.sh
```
Then search **Keychron Studio** in your apps and double-click it. You can pin it to the
dash or copy the generated `.desktop` file to `~/Desktop`.

## Features (v1)
- **Remap** every key across the 4 layers (Mac Base / Mac Fn / Win Base / Win Fn),
  visual ISO layout, full keycode palette (letters, F1–F24, media, system, white
  backlight, and Keychron custom keycodes: Bluetooth hosts, Mission Control, …).
- **Backup / restore** the full keymap + macros to a local file.
- **Reset** the keymap to firmware defaults.
- **National keycaps with modifier levels**: switch the on-screen legends (US, French
  OSS, …) to match your physical keycaps, and hold Shift / CapsLock / AltGr to see each
  key's other characters. French (OSS) legends are generated from the X11 xkb definition
  (`tools/gen_keycaps_from_xkb.py`); add a layout by dropping a JSON in `keycaps/`.
- **Typing test**: a field below the keyboard highlights the physical key you press
  (held while pressed), layout-independently (via evdev→HID), handy to locate keys.
- **Layer keys** (`MO`/`TO`) in the palette, and an **English/French UI** that follows
  your system locale (`locales/`).
- **Scripts**: bind F13–F24 (the K5's four top-right keys are F13–F16 by default) to a
  shell command via a GNOME shortcut; mark a command *privileged* to run it through
  `pkexec`.

## Roadmap
- Macro editor (16 slots), white-backlight brightness/effect sliders, more national
  keycap layouts and additional Keychron boards.

## Troubleshooting
- **"VIA interface not found"**: connect by cable, set the switch to Cable (not Bluetooth),
  use a data USB port.
- **Password prompt on every action**: expected under the root-only model; actions are
  batched to minimize prompts.

## Credits
- Open **VIA**/**QMK** raw-HID protocol (`the-via`, `qmk`).
- Keyboard definition & keycode values from Keychron's QMK firmware
  (`Keychron/qmk_firmware`, branch `wls_2025q1`).

## Author
Built by **Slophil / Nathan OUDER** — <https://nathan-ouder.fr/> · <https://github.com/vraiSlophil>

## License
[PolyForm Noncommercial 1.0.0](LICENSE.md) — personal and other **noncommercial** use and
modification permitted; **commercial use is prohibited**. See
[CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.
