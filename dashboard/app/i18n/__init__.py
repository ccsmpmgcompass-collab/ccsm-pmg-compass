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


def _lookup(text: str) -> str:
    """Resolve `text`, tolerating surrounding whitespace.

    The extractor records each string stripped, so a triple-quoted block keeps
    its leading and trailing newlines at the call site but is keyed in ES
    without them. Looking up only the raw string would miss every such block:
    coverage would report it translated while the page silently rendered
    English. Falls back to the stripped key and reattaches the original
    whitespace so layout and markdown spacing are unchanged.
    """
    if text in ES:
        return ES[text]
    stripped = text.strip()
    if stripped in ES:
        lead = text[:len(text) - len(text.lstrip())]
        trail = text[len(text.rstrip()):]
        return f"{lead}{ES[stripped]}{trail}"
    return text


def t(text: str, **kwargs) -> str:
    """Translate `text` for the active language, then interpolate.

    Lookup happens before formatting so Spanish word order can differ from
    English. Returns `text` unchanged when no translation exists.
    """
    resolved = _lookup(text) if get_lang() == "es" else text
    if kwargs:
        try:
            return resolved.format(**kwargs)
        except (KeyError, IndexError):
            # A malformed translation must not break the page.
            return text.format(**kwargs)
    return resolved
