"""dispatch_workflow() must dispatch against the branch it's actually
running from, not a hardcoded "main" — that hardcoding is what sent the
first live cloud-dispatch tests of the Transfer Flow feature to a branch
whose code didn't exist yet (see docs/superpowers/plans/
2026-08-05-ccsm-transfer-flow.md's Task 8 notes)."""
import subprocess

from app.integrations import github_actions


def test_current_ref_returns_the_checked_out_branch(monkeypatch):
    def fake_run(cmd, **kwargs):
        assert cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]
        return subprocess.CompletedProcess(cmd, 0, stdout="feat/some-branch\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert github_actions._current_ref() == "feat/some-branch"


def test_current_ref_falls_back_to_main_when_git_unavailable(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert github_actions._current_ref() == "main"


def test_current_ref_falls_back_to_main_on_detached_head(monkeypatch):
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout="HEAD\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert github_actions._current_ref() == "main"


def test_dispatch_workflow_uses_current_ref_by_default(monkeypatch):
    monkeypatch.setattr(github_actions, "_get_token", lambda: "fake-token")
    monkeypatch.setattr(github_actions, "_current_ref", lambda: "feat/some-branch")

    captured = {}

    class FakeResponse:
        status_code = 204
        text = ""

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr(github_actions.requests, "post", fake_post)

    github_actions.dispatch_workflow("some-workflow.yml", {"job_id": "abc"})

    assert captured["json"]["ref"] == "feat/some-branch"


def test_dispatch_workflow_explicit_ref_overrides_current_ref(monkeypatch):
    monkeypatch.setattr(github_actions, "_get_token", lambda: "fake-token")
    monkeypatch.setattr(github_actions, "_current_ref", lambda: "feat/some-branch")

    captured = {}

    class FakeResponse:
        status_code = 204
        text = ""

    def fake_post(url, headers, json, timeout):
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr(github_actions.requests, "post", fake_post)

    github_actions.dispatch_workflow("some-workflow.yml", {}, ref="main")

    assert captured["json"]["ref"] == "main"
