from pathlib import Path
import subprocess

from openbankingmcp import launchd
from openbankingmcp.launchd import bootstrap, is_resilient, plist


def test_plist_runs_dashboard_from_project_directory_and_restarts(tmp_path: Path):
    value=plist("/usr/bin/python3","/tmp/openbanking.log","/project")
    assert "WorkingDirectory" in value
    assert "openbankingmcp.dashboard" in value
    assert "<key>RunAtLoad</key><true/>" in value
    assert "<key>KeepAlive</key><true/>" in value
    path = tmp_path / "service.plist"
    path.write_text(value)
    assert is_resilient(path)


def test_outdated_plist_without_keepalive_is_not_resilient(tmp_path: Path):
    path = tmp_path / "service.plist"
    path.write_text(plist("/usr/bin/python3", "/tmp/openbanking.log", "/project").replace("<key>KeepAlive</key><true/>", ""))
    assert not is_resilient(path)


def test_bootstrap_retries_while_previous_job_finishes(monkeypatch, tmp_path: Path):
    bootstrap_attempts = 0

    def run(arguments, **_kwargs):
        nonlocal bootstrap_attempts
        if arguments[1] == "bootstrap":
            bootstrap_attempts += 1
            if bootstrap_attempts == 1:
                raise subprocess.CalledProcessError(5, arguments)
        return subprocess.CompletedProcess(arguments, 0)

    monkeypatch.setattr(launchd.subprocess, "run", run)
    monkeypatch.setattr(launchd.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(launchd.os, "getuid", lambda: 501, raising=False)

    bootstrap(tmp_path / "service.plist")

    assert bootstrap_attempts == 2
