import app.i18n as i18n
from app.components.cloud_job_ui import _format_elapsed, _progress_message


def test_format_elapsed_seconds_only():
    assert _format_elapsed(7) == "0:07"


def test_format_elapsed_minutes_and_seconds():
    assert _format_elapsed(75) == "1:15"


def test_format_elapsed_rounds_down_to_whole_seconds():
    assert _format_elapsed(7.9) == "0:07"


def test_format_elapsed_negative_clamped_to_zero():
    assert _format_elapsed(-3) == "0:00"


# ── _progress_message: exercises the real t() call, not a mock. A prior
# version raised "TypeError: t() got multiple values for argument 'text'"
# here — t()'s own first parameter is named `text`, and a status_text= kwarg
# once collided with it. Only a real click in a browser surfaced that; these
# tests exist so the same class of bug fails in CI instead. ─────────────────

def test_progress_message_uses_progress_text_when_present(monkeypatch):
    monkeypatch.setattr(i18n, "get_lang", lambda: "en")
    msg = _progress_message({"progress_text": "Logging into IMOS..."}, 5)
    assert msg == "Logging into IMOS... (0:05 elapsed)"


def test_progress_message_falls_back_to_working_when_no_progress_text(monkeypatch):
    monkeypatch.setattr(i18n, "get_lang", lambda: "en")
    msg = _progress_message({"progress_text": ""}, 65)
    assert msg == "Working... (1:05 elapsed)"


def test_progress_message_missing_progress_text_key(monkeypatch):
    monkeypatch.setattr(i18n, "get_lang", lambda: "en")
    msg = _progress_message({}, 0)
    assert msg == "Working... (0:00 elapsed)"
