#!/usr/bin/env python3
"""
Keychron Studio — configure a Keychron K5 v2 (VIA protocol) locally on Linux.
Unofficial community project. Not affiliated with or endorsed by Keychron.
"""
import os, sys, json, time, gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib, Pango

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kc_client, kc_layout, kc_keycodes, kc_scripts, kc_i18n, kc_keycaps, kc_evdev
from kc_i18n import t

APP_ID   = "com.github.vraislophil.keychron_studio"
DEF_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "defs", "k5_iso_white.json")
BACKUP_DIR = os.path.join(GLib.get_user_data_dir(), "keychron-studio", "backups")
SCALE = 46
LAYER_CODES = ["layer.mac_base", "layer.mac_fn", "layer.win_base", "layer.win_fn"]
SCRIPT_KEYS = [f"F{n}" for n in range(13, 25)]
LANG_NAMES = {"en": "English", "fr": "Français"}
AUTHOR_SITE = "https://nathan-ouder.fr/"
AUTHOR_SITE_LINK = "https://nathan-ouder.fr/?utm_source=keychron_studio_about"
AUTHOR_GH = "https://github.com/vraiSlophil"


class KeycodePicker(Gtk.Popover):
    def __init__(self, on_pick):
        super().__init__()
        self.on_pick = on_pick
        sc = Gtk.ScrolledWindow(min_content_height=380, min_content_width=460,
                                propagate_natural_width=True)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=8,
                      margin_bottom=8, margin_start=8, margin_end=8)
        for gid, codes in kc_keycodes.GROUPS:
            box.append(Gtk.Label(label=t("group." + gid), xalign=0, css_classes=["heading"]))
            flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=8,
                               column_spacing=4, row_spacing=4)
            for code in codes:
                b = Gtk.Button(label=kc_keycodes.label(code), tooltip_text=f"0x{code:04X}")
                b.connect("clicked", self._picked, code)
                flow.append(b)
            box.append(flow)
        sc.set_child(box)
        self.set_child(sc)

    def _picked(self, _btn, code):
        self.popdown()
        self.on_pick(code)


class KeyboardView(Gtk.Fixed):
    def __init__(self, layout, on_key):
        super().__init__()
        self.on_key = on_key
        self.buttons = {}
        self.labels = {}
        for k in layout["keys"]:
            lbl = Gtk.Label(single_line_mode=True, ellipsize=Pango.EllipsizeMode.END,
                            max_width_chars=max(2, int(round(k["w"] * 3))), wrap=False)
            b = Gtk.Button(css_classes=["kc-key"])
            b.set_child(lbl)
            b.set_size_request(int(k["w"] * SCALE) - 4, int(k["h"] * SCALE) - 4)
            b.connect("clicked", self._clicked, (k["row"], k["col"]))
            self.put(b, k["x"] * SCALE, k["y"] * SCALE)
            self.buttons[(k["row"], k["col"])] = b
            self.labels[(k["row"], k["col"])] = lbl

    def _clicked(self, btn, rc):
        self.on_key(rc, btn)

    def show_layer(self, keymap, layer, caps):
        for rc, lbl in self.labels.items():
            code = keymap[layer][rc[0]][rc[1]]
            lbl.set_text(kc_keycaps.legend(code, caps))
            self.buttons[rc].set_tooltip_text(f"{kc_keycodes.label(code)}  (0x{code:04X})")


class KeychronWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Keychron Studio",
                         default_width=1120, default_height=640)
        self.layout = kc_layout.decode(DEF_PATH)
        self.keymap = None
        self.pending = {}
        self.hid2rc = {}
        self.caps_codes = kc_keycaps.available()
        self.caps_layout = kc_i18n.current() if kc_i18n.current() in self.caps_codes else kc_keycaps.DEFAULT
        self.caps = kc_keycaps.load(self.caps_layout)

        self._install_css()
        self.toasts = Adw.ToastOverlay()
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        header = Adw.HeaderBar()
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.switcher = Gtk.StackSwitcher(stack=self.stack)
        header.set_title_widget(self.switcher)

        self.lang_codes = kc_i18n.available()
        self.lang_dd = Gtk.DropDown.new_from_strings(
            [LANG_NAMES.get(c, c.upper()) for c in self.lang_codes])
        if kc_i18n.current() in self.lang_codes:
            self.lang_dd.set_selected(self.lang_codes.index(kc_i18n.current()))
        self.lang_dd.set_tooltip_text(t("about.language"))
        self.lang_dd.connect("notify::selected", self._on_lang)
        header.pack_end(self.lang_dd)

        root.append(header)
        root.append(self.stack)
        self.toasts.set_child(root)
        self.set_content(self.toasts)

        keyctrl = Gtk.EventControllerKey()
        keyctrl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keyctrl.connect("key-pressed", self._on_test_key)
        self.add_controller(keyctrl)

        self.build_stack()
        GLib.idle_add(self.reload_keymap)

    def build_stack(self):
        child = self.stack.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self.stack.remove(child)
            child = nxt
        self.stack.add_titled(self._remap_page(), "remap", t("tab.remap"))
        self.stack.add_titled(self._backup_page(), "backup", t("tab.backup"))
        self.stack.add_titled(self._scripts_page(), "scripts", t("tab.scripts"))
        self.stack.add_titled(self._about_page(), "about", t("tab.about"))

    def _on_lang(self, dd, _p):
        code = self.lang_codes[dd.get_selected()]
        if code != kc_i18n.current():
            kc_i18n.set_language(code)
            self.build_stack()
            if self.keymap:
                self._refresh_keys()

    # ---------- pages ----------
    def _remap_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                       margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)
        bar = Gtk.Box(spacing=10)
        bar.append(Gtk.Label(label=t("remap.layer")))
        self.layer_dd = Gtk.DropDown.new_from_strings([t(c) for c in LAYER_CODES])
        self.layer_dd.connect("notify::selected", lambda *_: self._refresh_keys())
        bar.append(self.layer_dd)
        bar.append(Gtk.Label(label=t("remap.caps")))
        self.caps_dd = Gtk.DropDown.new_from_strings(
            [kc_keycaps.display_name(c) for c in self.caps_codes])
        if self.caps_layout in self.caps_codes:
            self.caps_dd.set_selected(self.caps_codes.index(self.caps_layout))
        self.caps_dd.connect("notify::selected", self._on_caps)
        bar.append(self.caps_dd)
        self.apply_btn = Gtk.Button(label=t("remap.apply"), css_classes=["suggested-action"],
                                    sensitive=bool(self.pending))
        self.apply_btn.connect("clicked", self._apply_pending)
        reload_btn = Gtk.Button(label=t("remap.reload"), tooltip_text=t("remap.reload_tip"))
        reload_btn.connect("clicked", lambda *_: self.reload_keymap())
        end = Gtk.Box(spacing=8, hexpand=True, halign=Gtk.Align.END)
        end.append(reload_btn)
        end.append(self.apply_btn)
        bar.append(end)
        page.append(bar)

        self.kbview = KeyboardView(self.layout, self._on_key)
        frame = Gtk.Frame()
        frame.set_child(self.kbview)
        frame.set_size_request(int(22.4 * SCALE), int(6.3 * SCALE))
        page.append(frame)
        page.append(Gtk.Label(label=t("remap.hint"), css_classes=["dim-label"], xalign=0))

        # typing test + live key highlight
        test = Gtk.Box(spacing=10)
        test.append(Gtk.Label(label=t("test.label")))
        entry = Gtk.Entry(hexpand=True, placeholder_text=t("test.placeholder"))
        test.append(entry)
        page.append(test)
        return page

    def _backup_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                       margin_top=16, margin_bottom=16, margin_start=16, margin_end=16)
        g = Adw.PreferencesGroup(title=t("backup.group"))
        r1 = Adw.ActionRow(title=t("backup.save_title"), subtitle=t("backup.save_sub"))
        b1 = Gtk.Button(label=t("backup.save"), valign=Gtk.Align.CENTER)
        b1.connect("clicked", self._do_backup)
        r1.add_suffix(b1)
        g.add(r1)
        r2 = Adw.ActionRow(title=t("backup.restore_title"), subtitle=t("backup.restore_sub"))
        self.backup_dd = Gtk.DropDown.new_from_strings(self._list_backups() or [t("backup.none")])
        r2.add_suffix(self.backup_dd)
        b2 = Gtk.Button(label=t("backup.restore"), valign=Gtk.Align.CENTER)
        b2.connect("clicked", self._do_restore)
        r2.add_suffix(b2)
        g.add(r2)
        page.append(g)

        g2 = Adw.PreferencesGroup(title=t("reset.group"))
        r3 = Adw.ActionRow(title=t("reset.km_title"), subtitle=t("reset.km_sub"))
        b3 = Gtk.Button(label=t("reset.km_btn"), css_classes=["destructive-action"],
                        valign=Gtk.Align.CENTER)
        b3.connect("clicked", lambda *_: self._confirm(
            t("confirm.reset_km_h"), t("confirm.reset_km_b"),
            lambda: self._helper([{"op": "keymap_reset"}], t("toast.keymap_reset"), reload=True)))
        r3.add_suffix(b3)
        g2.add(r3)
        page.append(g2)
        return page

    def _scripts_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                       margin_top=16, margin_bottom=16, margin_start=16, margin_end=16)
        page.append(Gtk.Label(xalign=0, css_classes=["dim-label"], wrap=True, label=t("scripts.intro")))
        existing = {}
        try:
            existing = kc_scripts.list_triggers()
        except Exception:
            pass
        self.script_rows = {}
        g = Adw.PreferencesGroup(title=t("scripts.group"))
        for key in SCRIPT_KEYS:
            row = Adw.ActionRow(title=key)
            entry = Gtk.Entry(hexpand=True, valign=Gtk.Align.CENTER,
                              placeholder_text=t("scripts.cmd_ph"))
            cmd = existing.get(key, "")
            priv = cmd.startswith("pkexec ")
            entry.set_text(cmd[len("pkexec "):] if priv else cmd)
            sw = Gtk.Switch(active=priv, valign=Gtk.Align.CENTER, tooltip_text=t("scripts.priv_tip"))
            row.add_suffix(entry)
            row.add_suffix(sw)
            g.add(row)
            self.script_rows[key] = (entry, sw)
        page.append(g)
        save = Gtk.Button(label=t("scripts.save"), css_classes=["suggested-action"],
                          halign=Gtk.Align.END)
        save.connect("clicked", self._save_scripts)
        page.append(save)
        return page

    def _about_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                       margin_top=24, margin_bottom=24, margin_start=24, margin_end=24)
        page.append(Gtk.Label(css_classes=["title-1"], label="Keychron Studio"))
        page.append(Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER, label=t("about.subtitle")))
        page.append(Gtk.Label(css_classes=["heading"], label=t("about.author")))
        links = Gtk.Box(spacing=18, halign=Gtk.Align.CENTER)
        links.append(Gtk.Label(use_markup=True,
                     label=f'{t("about.website")} : <a href="{AUTHOR_SITE_LINK}">{AUTHOR_SITE}</a>'))
        links.append(Gtk.Label(use_markup=True,
                     label=f'{t("about.github")} : <a href="{AUTHOR_GH}">github.com/vraiSlophil</a>'))
        page.append(links)
        page.append(Gtk.Label(css_classes=["dim-label"], label=t("about.license")))
        return page

    # ---------- keymap logic ----------
    def _cur_layer(self):
        return self.layer_dd.get_selected()

    def reload_keymap(self):
        try:
            res = kc_client.call([{"op": "get_keymap",
                                   "rows": self.layout["rows"], "cols": self.layout["cols"]}])
            self.keymap = res[0]["keymap"]
            self.pending.clear()
            self.apply_btn.set_sensitive(False)
            self._rebuild_hid_index()
            self._refresh_keys()
            self._toast(t("toast.kb_read"))
        except kc_client.HelperError as e:
            self._toast(t("toast.error", e=e))
        return False

    def _rebuild_hid_index(self):
        self.hid2rc = {}
        order = [i for i in (0, 2, 1, 3) if i < len(self.keymap)]
        for L in order:
            for r, row in enumerate(self.keymap[L]):
                for c, code in enumerate(row):
                    self.hid2rc.setdefault(code, (r, c))

    def _refresh_keys(self):
        if self.keymap:
            self.kbview.show_layer(self.keymap, self._cur_layer(), self.caps)

    def _on_caps(self, dd, _p):
        self.caps_layout = self.caps_codes[dd.get_selected()]
        self.caps = kc_keycaps.load(self.caps_layout)
        self._refresh_keys()

    def _on_key(self, rc, btn):
        if self.keymap is None:
            self._toast(t("toast.kb_not_read"))
            return
        picker = KeycodePicker(lambda code: self._set_key(rc, code))
        picker.set_parent(btn)
        picker.popup()

    def _set_key(self, rc, code):
        layer = self._cur_layer()
        self.keymap[layer][rc[0]][rc[1]] = code
        self.pending[(layer, rc[0], rc[1])] = code
        self.kbview.labels[rc].set_text(kc_keycaps.legend(code, self.caps))
        self.kbview.buttons[rc].set_tooltip_text(f"{kc_keycodes.label(code)}  (0x{code:04X})")
        self.apply_btn.set_sensitive(True)

    def _on_test_key(self, _ctrl, _keyval, keycode, _state):
        rc = None
        for hid in kc_evdev.hids_from_hwkeycode(keycode):
            if hid in self.hid2rc:
                rc = self.hid2rc[hid]
                break
        if rc:
            self._flash(rc)
        return False  # let the entry still receive the keystroke

    def _flash(self, rc):
        btn = self.kbview.buttons.get(rc)
        if not btn:
            return
        btn.add_css_class("pressed")
        GLib.timeout_add(220, self._unflash, btn)

    def _unflash(self, btn):
        btn.remove_css_class("pressed")
        return False

    def _apply_pending(self, _btn):
        if not self.pending:
            return
        ops = [{"op": "set_keycode", "layer": l, "row": r, "col": c, "keycode": k}
               for (l, r, c), k in self.pending.items()]
        try:
            kc_client.call(ops)
            self._toast(t("toast.keys_written", n=len(ops)))
            self.pending.clear()
            self.apply_btn.set_sensitive(False)
        except kc_client.HelperError as e:
            self._toast(t("toast.error", e=e))

    # ---------- backup / restore ----------
    def _list_backups(self):
        try:
            return sorted((f for f in os.listdir(BACKUP_DIR) if f.endswith(".json")), reverse=True)
        except OSError:
            return []

    def _do_backup(self, _btn):
        try:
            res = kc_client.call([{"op": "backup",
                                   "rows": self.layout["rows"], "cols": self.layout["cols"]}])[0]
            os.makedirs(BACKUP_DIR, exist_ok=True)
            fname = time.strftime("k5-%Y%m%d-%H%M%S.json")
            with open(os.path.join(BACKUP_DIR, fname), "w") as f:
                json.dump(res, f)
            self.backup_dd.set_model(Gtk.StringList.new(self._list_backups()))
            self._toast(t("backup.saved", f=fname))
        except (kc_client.HelperError, OSError) as e:
            self._toast(t("toast.error", e=e))

    def _do_restore(self, _btn):
        model = self.backup_dd.get_model()
        if model is None or self.backup_dd.get_selected() == Gtk.INVALID_LIST_POSITION:
            return
        fname = model.get_string(self.backup_dd.get_selected())
        if not fname.endswith(".json"):
            return

        def go():
            try:
                with open(os.path.join(BACKUP_DIR, fname)) as f:
                    data = json.load(f)
                kc_client.call([{"op": "restore", "rows": self.layout["rows"],
                                 "cols": self.layout["cols"],
                                 "keymap_hex": data["keymap_hex"],
                                 "macros_hex": data["macros_hex"]}])
                self._toast(t("toast.restored"))
                self.reload_keymap()
            except (kc_client.HelperError, OSError, KeyError) as e:
                self._toast(t("toast.error", e=e))
        self._confirm(t("confirm.restore_h"), t("confirm.restore_b", f=fname), go)

    # ---------- scripts ----------
    def _save_scripts(self, _btn):
        n = 0
        try:
            for key, (entry, sw) in self.script_rows.items():
                cmd = entry.get_text().strip()
                if cmd:
                    kc_scripts.set_trigger(key, cmd, sw.get_active())
                    n += 1
                else:
                    kc_scripts.clear_trigger(key)
            self._toast(t("scripts.saved", n=n))
        except Exception as e:
            self._toast(t("toast.error", e=e))

    # ---------- helpers ----------
    def _helper(self, ops, ok_msg, reload=False):
        try:
            kc_client.call(ops)
            self._toast(ok_msg)
            if reload:
                self.reload_keymap()
        except kc_client.HelperError as e:
            self._toast(t("toast.error", e=e))

    def _confirm(self, heading, body, on_yes):
        dlg = Adw.MessageDialog(transient_for=self, heading=heading, body=body)
        dlg.add_response("cancel", t("common.cancel"))
        dlg.add_response("ok", t("common.confirm"))
        dlg.set_response_appearance("ok", Adw.ResponseAppearance.DESTRUCTIVE)
        dlg.connect("response", lambda d, r: on_yes() if r == "ok" else None)
        dlg.present()

    def _toast(self, text):
        self.toasts.add_toast(Adw.Toast.new(text))

    def _install_css(self):
        css = Gtk.CssProvider()
        css.load_from_data(
            b".kc-key{font-size:10px;padding:1px 2px;min-height:0;min-width:0;}"
            b".kc-key.pressed{background-color:#3584e4;background-image:none;color:#ffffff;}")
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


class KeychronStudio(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_activate(self):
        win = self.props.active_window or KeychronWindow(self)
        win.present()


def main():
    Adw.init()
    kc_i18n.init()
    return KeychronStudio().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
