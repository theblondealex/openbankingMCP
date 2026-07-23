from pathlib import Path

from openbankingmcp.service import linux_service_path, service_help, systemd_unit, windows_task_action


def test_linux_systemd_unit_is_per_user_and_restarts():
    value = systemd_unit("/opt/open banking/python", "/opt/open banking/app")
    assert 'ExecStart="/opt/open banking/python" -m openbankingmcp.dashboard' in value
    assert 'WorkingDirectory="/opt/open banking/app"' in value
    assert "WantedBy=default.target" in value
    assert "Restart=on-failure" in value


def test_windows_task_action_quotes_the_python_path():
    value = windows_task_action(r"C:\Users\Alex\Open Banking\python.exe")
    assert value.startswith('"C:\\Users\\Alex\\Open Banking\\python.exe"')
    assert value.endswith("-m openbankingmcp.dashboard")


def test_linux_service_honours_xdg_config_home(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert linux_service_path() == tmp_path / "systemd/user/openbankingmcp.service"


def test_service_errors_give_platform_specific_recovery():
    assert "Task Scheduler" in service_help("Windows")
    assert "systemd user session" in service_help("Linux")
