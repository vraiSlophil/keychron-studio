#!/usr/bin/env python3
"""
Keychron Studio — configure a Keychron K5 v2 (VIA protocol) locally on Linux.
Unofficial community project. Not affiliated with or endorsed by Keychron.

GUI (GTK4 / libadwaita). All keyboard I/O is delegated to the privileged helper
via kc_client (pkexec), keeping this process unprivileged.
"""
import os, sys, json, time, gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kc_client, kc_layout, kc_keycodes, kc_scripts

APP_ID   = "com.github.vraislophil.keychron_studio"
DEF_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "defs", "k5_iso_white.json")
BACKUP_DIR = os.path.join(GLib.get_user_data_dir(), "keychron-studio", "backups")
SCALE = 46  # px per keyboard unit
LAYER_NAMES = ["0 · Mac Base", "1 · Mac Fn", "2 · Win Base", "3 · Win Fn"]
SCRIPT_KEYS = [f"F{n}" for n in range(13, 25)]  # F13..F24


class KeycodePicker(Gtk.Popover):
    """Grouped keycode chooser; calls on_pick(code) on selection."""
    def __init__(self, on_pick):
        super().__init__()
        self.on_pick = on_pick
        sc = Gtk.ScrolledWindow(min_content_height=380, min_content_width=440,
                                propagate_natural_width=True)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=8,
                      margin_bottom=8, margin_start=8, margin_end=8)
        for name, codes in kc_keycodes.GROUPS:
            box.append(Gtk.Label(label=name, xalign=0, css_classes=["heading"]))
            flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=8,
                               column_spacing=4, row_spacing=4)
            for code in codes:
                b = Gtk.Button(label=kc_keycodes.label(code), tooltip_text=f"0x{code:04X}")
                b.connect("clicked", self._picked, code)
                flow.append(b)
            box.append(flow)
        sc.set_child(box); self.set_child(sc)

    def _picked(self, _btn, code):
        self.popdown()
        self.on_pick(code)


class KeyboardView(Gtk.Fixed):
    """Renders the physical keyboard; each key is a button carrying (row,col)."""
    def __init__(self, layout, on_key):
        super().__init__()
        self.on_key = on_key
        self.buttons = {}   # (row,col) -> button
        for k in layout["keys"]:
            b = Gtk.Button()
            b.set_size_request(int(k["w"] * SCALE) - 4, int(k["h"] * SCALE) - 4)
            b.add_css_class("kc-key")
            b.connect("clicked", self._clicked, (k["row"], k["col"]))
            self.put(b, k["x"] * SCALE, k["y"] * SCALE)
            self.buttons[(k["row"], k["col"])] = b

    def _clicked(self, btn, rc):
        self.on_key(rc, btn)

    def show_layer(self, keymap, layer):
        for (r, c), b in self.buttons.items():
            code = keymap[layer][r][c]
            b.set_label(kc_keycodes.label(code))


class KeychronWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Keychron Studio",
                         default_width=1080, default_height=560)
        self.layout = kc_layout.decode(DEF_PATH)
        self.keymap = None
        self.pending = {}   # (layer,row,col) -> code

        self.toasts = Adw.ToastOverlay()
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        header = Adw.HeaderBar()
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        switcher = Gtk.StackSwitcher(stack=self.stack)
        header.set_title_widget(switcher)
        root.append(header); root.append(self.stack)
        self.toasts.set_child(root)
        self.set_content(self.toasts)

        self.stack.add_titled(self._remap_page(), "remap", "Remap")
        self.stack.add_titled(self._backup_page(), "backup", "Sauvegarde")
        self.stack.add_titled(self._scripts_page(), "scripts", "Scripts")
        self.stack.add_titled(self._about_page(), "about", "À propos")

        self._install_css()
        GLib.idle_add(self.reload_keymap)

    # ---------- pages ----------
    def _remap_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                       margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)
        bar = Gtk.Box(spacing=10)
        bar.append(Gtk.Label(label="Couche :"))
        self.layer_dd = Gtk.DropDown.new_from_strings(LAYER_NAMES)
        self.layer_dd.connect("notify::selected", lambda *_: self._refresh_keys())
        bar.append(self.layer_dd)
        self.apply_btn = Gtk.Button(label="Appliquer", css_classes=["suggested-action"],
                                    sensitive=False)
        self.apply_btn.connect("clicked", self._apply_pending)
        reload_btn = Gtk.Button(label="Recharger", tooltip_text="Relire le clavier")
        reload_btn.connect("clicked", lambda *_: self.reload_keymap())
        end = Gtk.Box(spacing=8, hexpand=True, halign=Gtk.Align.END)
        end.append(reload_btn); end.append(self.apply_btn)
        bar.append(end)
        page.append(bar)

        self.kbview = KeyboardView(self.layout, self._on_key)
        frame = Gtk.Frame()
        frame.set_child(self.kbview)
        frame.set_size_request(int(22.4 * SCALE), int(6.3 * SCALE))
        page.append(frame)
        page.append(Gtk.Label(
            label="Clique une touche pour la réassigner. « Appliquer » écrit dans le clavier.",
            css_classes=["dim-label"], xalign=0))
        return page

    def _backup_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                       margin_top=16, margin_bottom=16, margin_start=16, margin_end=16)
        g = Adw.PreferencesGroup(title="Sauvegarde & restauration")
        r1 = Adw.ActionRow(title="Sauvegarder la configuration",
                           subtitle="Keymap + macros vers un fichier local")
        b1 = Gtk.Button(label="Sauvegarder", valign=Gtk.Align.CENTER)
        b1.connect("clicked", self._do_backup); r1.add_suffix(b1); g.add(r1)
        r2 = Adw.ActionRow(title="Restaurer", subtitle="Recharger une sauvegarde")
        self.backup_dd = Gtk.DropDown.new_from_strings(self._list_backups() or ["(aucune)"])
        r2.add_suffix(self.backup_dd)
        b2 = Gtk.Button(label="Restaurer", valign=Gtk.Align.CENTER)
        b2.connect("clicked", self._do_restore); r2.add_suffix(b2); g.add(r2)
        page.append(g)

        g2 = Adw.PreferencesGroup(title="Réinitialisation")
        r3 = Adw.ActionRow(title="Réinitialiser la keymap",
                           subtitle="Restaure la disposition d'usine (touches)")
        b3 = Gtk.Button(label="Reset keymap", css_classes=["destructive-action"],
                        valign=Gtk.Align.CENTER)
        b3.connect("clicked", lambda *_: self._confirm(
            "Réinitialiser la keymap ?", "Toutes tes réassignations seront perdues.",
            lambda: self._helper([{"op": "keymap_reset"}], "Keymap réinitialisée", reload=True)))
        r3.add_suffix(b3); g2.add(r3)
        page.append(g2)
        return page

    def _scripts_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                       margin_top=16, margin_bottom=16, margin_start=16, margin_end=16)
        page.append(Gtk.Label(xalign=0, css_classes=["dim-label"], wrap=True, label=(
            "Assigne d'abord une touche physique à F13–F24 dans l'onglet Remap, "
            "puis associe ici une commande. « Privilégié » l'exécute via pkexec (mot de passe).")))
        existing = {}
        try:
            existing = kc_scripts.list_triggers()
        except Exception:
            pass
        self.script_rows = {}
        g = Adw.PreferencesGroup(title="Touches-scripts (via raccourcis GNOME)")
        for key in SCRIPT_KEYS:
            row = Adw.ActionRow(title=key)
            entry = Gtk.Entry(hexpand=True, valign=Gtk.Align.CENTER,
                              placeholder_text="commande shell…")
            cmd = existing.get(key, "")
            priv = cmd.startswith("pkexec ")
            entry.set_text(cmd[len("pkexec "):] if priv else cmd)
            sw = Gtk.Switch(active=priv, valign=Gtk.Align.CENTER, tooltip_text="Privilégié (pkexec)")
            row.add_suffix(entry); row.add_suffix(sw)
            g.add(row)
            self.script_rows[key] = (entry, sw)
        page.append(g)
        save = Gtk.Button(label="Enregistrer les scripts", css_classes=["suggested-action"],
                          halign=Gtk.Align.END)
        save.connect("clicked", self._save_scripts)
        page.append(save)
        return page

    def _about_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                       margin_top=24, margin_bottom=24, margin_start=24, margin_end=24)
        page.append(Gtk.Label(css_classes=["title-1"], label="Keychron Studio"))
        page.append(Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER, label=(
            "Configuration locale du Keychron K5 v2 via le protocole VIA/QMK.\n"
            "Projet communautaire non-officiel — non affilié à Keychron, ni approuvé par eux.\n"
            "« Keychron » est une marque de son propriétaire respectif.")))
        page.append(Gtk.Label(css_classes=["dim-label"], label=(
            "Licence PolyForm Noncommercial 1.0.0 — usage et modification non commerciaux.")))
        return page

    # ---------- keymap logic ----------
    def _cur_layer(self):
        return self.layer_dd.get_selected()

    def reload_keymap(self):
        try:
            res = kc_client.call([{"op": "get_keymap",
                                   "rows": self.layout["rows"], "cols": self.layout["cols"]}])
            self.keymap = res[0]["keymap"]
            self.pending.clear(); self.apply_btn.set_sensitive(False)
            self._refresh_keys()
            self._toast("Clavier lu.")
        except kc_client.HelperError as e:
            self._toast(f"Erreur : {e}")
        return False

    def _refresh_keys(self):
        if self.keymap:
            self.kbview.show_layer(self.keymap, self._cur_layer())

    def _on_key(self, rc, btn):
        if self.keymap is None:
            self._toast("Clavier non lu."); return
        picker = KeycodePicker(lambda code: self._set_key(rc, code))
        picker.set_parent(btn); picker.popup()

    def _set_key(self, rc, code):
        layer = self._cur_layer(); r, c = rc
        self.keymap[layer][r][c] = code
        self.pending[(layer, r, c)] = code
        self.kbview.buttons[rc].set_label(kc_keycodes.label(code))
        self.apply_btn.set_sensitive(True)

    def _apply_pending(self, _btn):
        if not self.pending:
            return
        ops = [{"op": "set_keycode", "layer": l, "row": r, "col": c, "keycode": k}
               for (l, r, c), k in self.pending.items()]
        try:
            kc_client.call(ops)
            self._toast(f"{len(ops)} touche(s) écrite(s).")
            self.pending.clear(); self.apply_btn.set_sensitive(False)
        except kc_client.HelperError as e:
            self._toast(f"Erreur : {e}")

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
            self._toast(f"Sauvegardé : {fname}")
        except (kc_client.HelperError, OSError) as e:
            self._toast(f"Erreur : {e}")

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
                self._toast("Restauré."); self.reload_keymap()
            except (kc_client.HelperError, OSError, KeyError) as e:
                self._toast(f"Erreur : {e}")
        self._confirm("Restaurer cette sauvegarde ?", f"Écrase la config actuelle par {fname}.", go)

    # ---------- scripts ----------
    def _save_scripts(self, _btn):
        n = 0
        try:
            for key, (entry, sw) in self.script_rows.items():
                cmd = entry.get_text().strip()
                if cmd:
                    kc_scripts.set_trigger(key, cmd, sw.get_active()); n += 1
                else:
                    kc_scripts.clear_trigger(key)
            self._toast(f"{n} script(s) enregistré(s) dans GNOME.")
        except Exception as e:
            self._toast(f"Erreur scripts : {e}")

    # ---------- helpers ----------
    def _helper(self, ops, ok_msg, reload=False):
        try:
            kc_client.call(ops); self._toast(ok_msg)
            if reload:
                self.reload_keymap()
        except kc_client.HelperError as e:
            self._toast(f"Erreur : {e}")

    def _confirm(self, heading, body, on_yes):
        dlg = Adw.MessageDialog(transient_for=self, heading=heading, body=body)
        dlg.add_response("cancel", "Annuler")
        dlg.add_response("ok", "Confirmer")
        dlg.set_response_appearance("ok", Adw.ResponseAppearance.DESTRUCTIVE)
        dlg.connect("response", lambda d, r: on_yes() if r == "ok" else None)
        dlg.present()

    def _toast(self, text):
        self.toasts.add_toast(Adw.Toast.new(text))

    def _install_css(self):
        css = Gtk.CssProvider()
        css.load_from_data(b".kc-key{font-size:11px;padding:2px;min-height:0;}")
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
    return KeychronStudio().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
