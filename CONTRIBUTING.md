# Contributing to Keychron Studio

Thanks for your interest! This project is community-run and **noncommercial**.
Contributions are welcome under the rules below.

## Licensing of contributions
By submitting a contribution (code, docs, definitions), you agree that it is licensed
under the project's [PolyForm Noncommercial 1.0.0](LICENSE.md) license. In short:
- Personal and other **noncommercial** use and modification are allowed.
- **Any commercial use, sale, or paid redistribution is prohibited** — for the project
  as a whole and for your contribution.
- You confirm you have the right to contribute the material.

## Project layout
- `keychron_studio.py` — the GTK4/libadwaita app (window, pages, event handling).
- `kc_helper.py` — the **privileged** raw-HID helper (runs as root via pkexec).
- `kc_client.py` — GUI-side bridge that invokes the helper.
- `kc_layout.py` — decodes the VIA/KLE layout in `defs/`.
- `kc_keycodes.py` — keycode catalogue and groups (values from the board's firmware).
- `kc_keycaps.py` — national keycap legends (`keycaps/`), with modifier levels.
- `kc_case.py` — the single utility deciding letter case (Shift/CapsLock).
- `kc_evdev.py` — evdev→HID table for layout-independent key detection.
- `kc_i18n.py` — UI localization (`locales/`).
- `kc_scripts.py` — bind keys to shell commands via GNOME shortcuts.
- `defs/` VIA definitions · `keycaps/` legends · `locales/` translations ·
  `tools/` generators · `packaging/` installer, launcher, lockdown.

## Ground rules
1. **Conventional Commits, in English.** Examples:
   - `feat(remap): add tap-hold keycodes`
   - `fix(helper): bounds-check macro buffer length`
   - `docs(readme): clarify wired-mode requirement`
   Allowed types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `build`, `perf`.
2. **No new runtime dependencies** without discussion. The app deliberately relies only
   on the Python standard library and the system GTK4/libadwaita (PyGObject) bindings.
3. **Keep the privileged helper minimal and auditable.** `kc_helper.py` runs as root:
   - only add ops to the whitelist with explicit bounds checks;
   - never take a filesystem path, shell string, or network target from its input;
   - no `eval`, no `subprocess`, no sockets.
4. **Do not guess keycode or legend values.** Take keycodes from the board's QMK firmware
   source, and keycap legends from the relevant xkb definition; note where they come from.
5. **No user-visible string is hardcoded.** UI text goes through `kc_i18n.t("code")` with
   an entry in every `locales/<lang>.json`; keep code/comments in English.
6. Match the existing style (PEP 8, small focused modules).

## Adding a keyboard / variant
Place its VIA definition JSON in `defs/` (matrix + `layouts.keymap` + `customKeycodes`)
and point the app at it. Verify the `productId` matches the device.

## Adding a UI language
Copy `locales/en.json` to `locales/<lang>.json` and translate the values (keep every
key). It appears automatically in the language selector; English is the fallback.

## Adding a keycap layout
Prefer generating it from the system's xkb definition:
`python3 tools/gen_keycaps_from_xkb.py <layout> <variant> "<Display Name>" > keycaps/<name>.json`.
Entries are `"0xHID": "char"` for single-legend keys, or
`{"base","shift","altgr","shift_altgr"}` for multi-level keys. Letters store only their
base lowercase char — case is applied at runtime by `kc_case`, never encoded in data.

## Pull requests
1. Fork, branch from `main` (`feat/…`, `fix/…`).
2. Keep PRs focused; describe what you changed and how you tested it on real hardware.
3. Ensure the sources still parse and the app still launches:
   `python3 -c "import ast,pathlib; [ast.parse(p.read_text()) for p in pathlib.Path('.').rglob('*.py')]"`.

## Reporting issues
Include: keyboard model + `productId`, distro, desktop/session (X11/Wayland), keyboard
layout (e.g. `fr+oss`), and the exact error text. For the "VIA interface not found" case,
confirm the keyboard is wired and set to Cable mode.
