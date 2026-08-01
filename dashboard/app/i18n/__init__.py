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
_DEFAULT_KEY = "pmg_lang_default"


def mission_default_lang() -> str:
    """The language this mission runs in, from AGENT_CONFIG's MISSION_LANGUAGE.

    CCSM sets it to `ES`. Before this existed the default was the literal "en",
    so every missionary and every member of a Spanish-speaking mission's
    leadership opened an English dashboard and had to find the toggle — on a
    platform whose forms, metric labels, coaching emails and knowledge base are
    all already Spanish. Nothing was broken enough to report; it just quietly
    made the app feel like it belonged to somebody else.

    Falls back to English only when the sheet does not say. Resolved once and
    cached in the session: get_lang() runs on every single t() call, and a
    config read per translated string would be absurd even against a cache.
    """
    try:
        cached = st.session_state.get(_DEFAULT_KEY)
    except Exception:
        cached = None
    if cached in _LANGS:
        return cached

    lang = "en"
    try:
        from app.db.queries import get_config_value
        raw = (get_config_value("MISSION_LANGUAGE", "") or "").strip().lower()
        if raw[:2] in _LANGS:
            lang = raw[:2]
    except Exception:
        # No session, no secrets, no sheet (tests, import time, a quota blip).
        # English is the safe degrade: readable to everyone, and the switch is
        # still there.
        pass

    try:
        st.session_state[_DEFAULT_KEY] = lang
    except Exception:
        pass
    return lang


def get_lang() -> str:
    """The active display language: the user's choice if they made one,
    otherwise the mission's own."""
    try:
        lang = st.session_state.get(_KEY)
    except Exception:
        lang = None
    if lang in _LANGS:
        return lang
    return mission_default_lang()


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
