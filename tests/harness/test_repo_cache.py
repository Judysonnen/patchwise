"""install-registry tests. don't actually call pip — patch _try_pip_install."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import harness.repo_cache as rc


@pytest.fixture
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("PATCHWISE_CACHE", str(tmp_path))
    return tmp_path


def test_ensure_installed_records_sha_after_first_success(tmp_cache, monkeypatch):
    calls = []

    def fake_install(repo_path, extras):
        calls.append(extras)
        return (extras == "[test]"), ""

    monkeypatch.setattr(rc, "_try_pip_install", fake_install)
    extras = rc.ensure_installed("foo/bar", "abc123", Path("/fake"))
    assert extras == "[test]"
    assert calls == ["[test]"]
    # registry now records this (repo, sha)
    data = json.loads((tmp_cache / "installed.json").read_text())
    assert data["foo/bar"] == "abc123"
    assert data["foo/bar::extras"] == "[test]"


def test_ensure_installed_falls_back_through_extras(tmp_cache, monkeypatch):
    calls = []

    def fake_install(repo_path, extras):
        calls.append(extras)
        return (extras == ""), ""  # only bare succeeds

    monkeypatch.setattr(rc, "_try_pip_install", fake_install)
    extras = rc.ensure_installed("foo/bar", "abc", Path("/fake"))
    assert extras == ""
    assert calls == ["[test]", "[dev]", ""]


def test_ensure_installed_is_noop_when_already_recorded(tmp_cache, monkeypatch):
    (tmp_cache / "installed.json").write_text(
        json.dumps({"foo/bar": "abc", "foo/bar::extras": "[test]"})
    )
    called = []
    monkeypatch.setattr(rc, "_try_pip_install", lambda p, e: called.append(e) or (True, ""))
    extras = rc.ensure_installed("foo/bar", "abc", Path("/fake"))
    assert extras == "[test]"
    assert called == []  # no pip invocation


def test_ensure_installed_reinstalls_when_sha_changes(tmp_cache, monkeypatch):
    (tmp_cache / "installed.json").write_text(
        json.dumps({"foo/bar": "old_sha", "foo/bar::extras": "[test]"})
    )
    called = []

    def fake_install(repo_path, extras):
        called.append(extras)
        return True, ""

    monkeypatch.setattr(rc, "_try_pip_install", fake_install)
    rc.ensure_installed("foo/bar", "new_sha", Path("/fake"))
    assert called == ["[test]"]
    data = json.loads((tmp_cache / "installed.json").read_text())
    assert data["foo/bar"] == "new_sha"


def test_ensure_installed_raises_when_all_attempts_fail(tmp_cache, monkeypatch):
    monkeypatch.setattr(rc, "_try_pip_install",
                        lambda p, e: (False, f"failed for {e}"))
    with pytest.raises(RuntimeError, match="pip install of foo/bar failed"):
        rc.ensure_installed("foo/bar", "abc", Path("/fake"))
