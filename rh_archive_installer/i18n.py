"""Traductions : français (langue source) et English.

Le texte français sert de clé : ``_("Installation terminée")``. Un texte sans traduction
retombe sur le français. Les textes à variables utilisent ``{nom}`` : ``_("Copie : {nom}", nom=x)``.
"""
from __future__ import annotations

import os

LANGS = (("fr", "Français"), ("en", "English"))
CODES = tuple(c for c, _n in LANGS)

_lang = "fr"


def set_lang(code: str) -> None:
    global _lang
    _lang = code if code in CODES else "fr"


def get_lang() -> str:
    return _lang


def detect_lang() -> str:
    """Langue du système (RH_LANG, puis variables de locale) ; anglais à défaut."""
    for var in ("RH_LANG", "LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG"):
        value = os.environ.get(var, "").strip().lower()
        if value:
            code = value.replace("-", "_").split("_")[0].split(":")[0]
            if code in CODES:
                return code
    return "en"


def _(text: str, **kw) -> str:
    from .catalog import CATALOG
    out = CATALOG.get(_lang, {}).get(text, text)
    return out.format(**kw) if kw else out
