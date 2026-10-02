"""Leadership's nightly goals on Metas — queries.save_nightly_overrides /
clear_nightly_overrides (PLAN-2026-10-02-goals.md, G9, decision G-D10)."""

from app.db import queries as Q


def _capture(monkeypatch):
    written = {}
    monkeypatch.setattr(Q, "_write_overrides",
                        lambda area, values: written.setdefault("over", (area, values)))
    monkeypatch.setattr(Q, "save_area_goals",
                        lambda area, goals: written.setdefault("cfg", (area, dict(goals))))
    return written


def test_only_values_that_differ_from_the_computed_goal_are_leaderships(monkeypatch):
    w = _capture(monkeypatch)
    Q.save_nightly_overrides(
        "A", {"contacts_attempted": 160, "roleplays": 6, "church_invites": 0},
        {"contacts_attempted": 146, "roleplays": 6, "church_invites": 30})
    assert w["over"] == ("A", {"contacts_attempted": 160})
    # GOALS_CONFIG takes the typed values at once, for the emails.
    assert w["cfg"][1]["contacts_attempted"] == 160


def test_a_metric_with_no_computed_goal_is_not_made_an_override(monkeypatch):
    w = _capture(monkeypatch)
    Q.save_nightly_overrides("A", {"ki_new_people_real": 5}, {"roleplays": 6})
    assert w["over"] == ("A", {})


def test_reset_clears_leadership_and_restores_the_computed_goals(monkeypatch):
    w = _capture(monkeypatch)
    monkeypatch.setattr(Q, "get_area_goals", lambda area: {"roleplays": 9, "x": 3})
    Q.clear_nightly_overrides("A", {"roleplays": 6})
    assert w["over"] == ("A", {})
    assert w["cfg"] == ("A", {"roleplays": 6, "x": 3})
