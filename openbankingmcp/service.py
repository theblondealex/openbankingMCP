"""Install the local dashboard as a per-user login service on each supported OS."""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from . import launchd


LABEL = "openbankingmcp"
WINDOWS_TASK_NAME = "OpenBankingMCP"


class ServiceUnavailable(RuntimeError):
    """The current desktop session cannot install a per-user login service."""


def service_help(system_name: str | None = None) -> str:
    system_name = system_name or platform.system()
    if system_name == "Darwin":
        return "launchd refused the per-user service. Sign out and back in, then try again."
    if system_name == "Windows":
        return "Windows Task Scheduler refused the per-user task. Sign in with a normal desktop account, then try again."
    if system_name == "Linux":
        return "No usable systemd user session was found. Sign in to a normal desktop session, then try again."
    return "This operating system is not supported."


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _systemd_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def systemd_unit(python: str, working_directory: str) -> str:
    return "\n".join(
        [
            "[Unit]",
            "Description=OpenBankingMCP local dashboard",
            "After=graphical-session.target network-online.target",
            "",
            "[Service]",
            "Type=simple",
            f"ExecStart={_systemd_quote(python)} -m openbankingmcp.dashboard",
            f"WorkingDirectory={_systemd_quote(working_directory)}",
            "Restart=on-failure",
            "RestartSec=5",
            "",
            "[Install]",
            "WantedBy=default.target",
            "",
        ]
    )


def linux_service_path(home: Path | None = None) -> Path:
    home = home or Path.home()
    config_root = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    return config_root / "systemd/user/openbankingmcp.service"


def windows_task_action(python: str) -> str:
    return subprocess.list2cmdline([python, "-m", "openbankingmcp.dashboard"])


def install_service(
    system_name: str | None = None,
    python: str | None = None,
    root: Path | None = None,
    home: Path | None = None,
) -> Path | None:
    system_name = system_name or platform.system()
    python = python or sys.executable
    root = root or project_root()
    home = home or Path.home()
    if system_name == "Darwin":
        path = launchd.install(python, str(home / "Library/Logs/openbankingmcp.log"))
        launchd.bootstrap(path)
        return path
    if system_name == "Linux":
        if shutil.which("systemctl") is None:
            raise ServiceUnavailable("systemd user services are required on Linux.")
        path = linux_service_path(home)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(systemd_unit(python, str(root)))
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "enable", "--now", path.name], check=True)
        return path
    if system_name == "Windows":
        subprocess.run(
            [
                "schtasks.exe",
                "/Create",
                "/TN",
                WINDOWS_TASK_NAME,
                "/SC",
                "ONLOGON",
                "/RL",
                "LIMITED",
                "/TR",
                windows_task_action(python),
                "/F",
            ],
            check=True,
        )
        subprocess.run(["schtasks.exe", "/Run", "/TN", WINDOWS_TASK_NAME], check=True)
        return None
    raise ServiceUnavailable("OpenBankingMCP supports macOS, Windows, and desktop Linux.")


def uninstall_service(system_name: str | None = None, home: Path | None = None) -> None:
    system_name = system_name or platform.system()
    home = home or Path.home()
    if system_name == "Darwin":
        subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{launchd.LABEL}"], check=False)
        launchd.uninstall()
        return
    if system_name == "Linux":
        path = linux_service_path(home)
        subprocess.run(["systemctl", "--user", "disable", "--now", path.name], check=False)
        if path.exists():
            path.unlink()
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
        return
    if system_name == "Windows":
        subprocess.run(["schtasks.exe", "/Delete", "/TN", WINDOWS_TASK_NAME, "/F"], check=False)
        return
    raise ServiceUnavailable("OpenBankingMCP supports macOS, Windows, and desktop Linux.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage the per-user OpenBankingMCP dashboard service.")
    parser.add_argument("action", choices=("install", "uninstall"))
    args = parser.parse_args()
    try:
        path = install_service() if args.action == "install" else uninstall_service()
    except (ServiceUnavailable, subprocess.CalledProcessError) as error:
        detail = str(error) if isinstance(error, ServiceUnavailable) else service_help()
        raise SystemExit(f"Could not {args.action} the OpenBankingMCP login service. {detail}") from None
    if args.action == "install":
        location = f" ({path})" if path else ""
        print(f"Dashboard login service installed{location}.\nOpen http://127.0.0.1:3847")
    else:
        print("Dashboard login service removed. Local encrypted data was retained.")


if __name__ == "__main__":
    main()
