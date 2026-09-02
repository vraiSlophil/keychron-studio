"""
Minimal i18n helper. Each UI string has a unique code; translations live in
locales/<lang>.json. The active language is chosen from (in order): an explicit
override saved in the config file, then the user's system locale (LANG/LC_*),
then the English fallback. Missing codes fall back to English, then to the code
itself, so the app never crashes on a missing string.
"""
import json, os, locale as _locale

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")
_CONFDIR = os.path.join(os.environ.get("XDG_CONFIG_HOME") or
                        os.path.expanduser("~/.config"), "keychron-studio")
_CONF = os.path.join(_CONFDIR, "config.json")
FALLBACK = "en"

_strings, _fallback, _lang = {}, {}, None

def available():
    try:
        return sorted(f[:-5] for f in os.listdir(_DIR) if f.endswith(".json"))
    except OSError:
        return [FALLBACK]

def _system_lang():
    for env in ("LC_ALL", "LC_MESSAGES", "LANG"):
        v = os.environ.get(env)
        if v and v not in ("C", "POSIX"):
            return v.split(".")[0].split("_")[0].lower()
    try:
        loc = _locale.getlocale()[0]
        if loc:
            return loc.split("_")[0].lower()
    except Exception:
        pass
    return FALLBACK

def _saved_lang():
    try:
        with open(_CONF, encoding="utf-8") as f:
            return json.load(f).get("language")
    except (OSError, ValueError):
        return None

def _persist(lang):
    try:
        os.makedirs(_CONFDIR, exist_ok=True)
        with open(_CONF, "w", encoding="utf-8") as f:
            json.dump({"language": lang}, f)
    except OSError:
        pass

def _load(lang):
    try:
        with open(os.path.join(_DIR, f"{lang}.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}

def init(lang=None):
    global _strings, _fallback, _lang
    _fallback = _load(FALLBACK)
    chosen = lang or _saved_lang() or _system_lang()
    if chosen not in available():
        chosen = FALLBACK
    _lang, _strings = chosen, _load(chosen)

def set_language(lang):
    init(lang)
    _persist(lang)

def current():
    if _lang is None:
        init()
    return _lang

def t(code, **kw):
    if _lang is None:
        init()
    s = _strings.get(code) or _fallback.get(code) or code
    if kw:
        try:
            s = s.format(**kw)
        except (KeyError, IndexError, ValueError):
            pass
    return s
