"""Bilingual UI support.

The English source string is its own lookup key. That makes the retrofit
mechanical, needs no invented key namespace, and means a renamed or
untranslated string degrades to readable English instead of raising or
showing a raw identifier.

Only UI chrome goes through t(). Sheet-sourced mission content (metric
labels, mission name, knowledge base, notes, area names) is already Spanish
and must never be translated again.
"""

import streamlit as st

from app.i18n.es import ES

_LANGS = ("en", "es")
_KEY = "pmg_lang"


def get_lang() -> str:
    lang = st.session_state.get(_KEY, "en")
    return lang if lang in _LANGS else "en"


def set_lang(lang: str) -> None:
    if lang not in _LANGS:
        raise ValueError(f"unsupported language: {lang!r}")
    st.session_state[_KEY] = lang


def t(text: str, **kwargs) -> str:
    """Translate `text` for the active language, then interpolate.

    Lookup happens before formatting so Spanish word order can differ from
    English. Returns `text` unchanged when no translation exists.
    """
    resolved = ES.get(text, text) if get_lang() == "es" else text
    if kwargs:
        try:
            return resolved.format(**kwargs)
        except (KeyError, IndexError):
            # A malformed translation must not break the page.
            return text.format(**kwargs)
    return resolved
