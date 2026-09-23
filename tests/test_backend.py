import subprocess

import pytest

from casei_geofm import llm


def test_auto_prefers_api_when_key_set(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.delenv("CASEI_GEOFM_BACKEND", raising=False)
    assert llm.pick_backend() is llm._call_api


def test_auto_falls_back_to_cli_when_no_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CASEI_GEOFM_BACKEND", raising=False)
    monkeypatch.setattr(llm.shutil, "which", lambda _: "/usr/local/bin/claude")
    assert llm.pick_backend() is llm._call_claude_cli


def test_auto_errors_when_nothing_available(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CASEI_GEOFM_BACKEND", raising=False)
    monkeypatch.setattr(llm.shutil, "which", lambda _: None)
    with pytest.raises(RuntimeError, match="no LLM backend"):
        llm.pick_backend()


def test_explicit_backend_selection(monkeypatch):
    monkeypatch.setenv("CASEI_GEOFM_BACKEND", "claude_cli")
    assert llm.pick_backend() is llm._call_claude_cli
    monkeypatch.setenv("CASEI_GEOFM_BACKEND", "api")
    assert llm.pick_backend() is llm._call_api
    monkeypatch.setenv("CASEI_GEOFM_BACKEND", "bogus")
    with pytest.raises(ValueError):
        llm.pick_backend()


def _fake_run(returncode=0, stdout="", stderr=""):
    def run(cmd, input, capture_output, text, timeout):
        run.cmd = cmd
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)
    return run


def test_cli_call_builds_headless_command(monkeypatch):
    fake = _fake_run(stdout='{"ok": true}')
    monkeypatch.setattr(llm.subprocess, "run", fake)
    out = llm._call_claude_cli("SYS", "USER", "claude-sonnet-5")
    assert out == '{"ok": true}'
    assert fake.cmd[:2] == [llm.CLAUDE_BIN, "-p"]
    assert "--system-prompt" in fake.cmd and "SYS" in fake.cmd
    assert "--model" in fake.cmd and "claude-sonnet-5" in fake.cmd


def test_cli_not_logged_in_raises(monkeypatch):
    monkeypatch.setattr(llm.subprocess, "run",
                        _fake_run(stdout="Not logged in · Please run /login"))
    with pytest.raises(RuntimeError, match="claude CLI call failed"):
        llm._call_claude_cli("SYS", "USER", "")


def test_cli_nonzero_exit_raises(monkeypatch):
    monkeypatch.setattr(llm.subprocess, "run", _fake_run(returncode=1, stderr="boom"))
    with pytest.raises(RuntimeError, match="claude CLI call failed"):
        llm._call_claude_cli("SYS", "USER", "")


@pytest.mark.network
def test_live_cli_roundtrip():
    """Requires a logged-in claude CLI."""
    out = llm._call_claude_cli(
        "Respond with a single JSON object only.",
        'Return {"status": "ok"} exactly.', "")
    assert '"ok"' in out
