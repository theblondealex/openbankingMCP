"""Small cross-platform path helpers."""

from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Mapping


def system_name() -> str:
    return platform.system()


def data_dir(
    system: str | None = None,
    home: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> Path:
    environ = environ or os.environ
    if environ.get("OPENBANKINGMCP_DATA_DIR"):
        return Path(environ["OPENBANKINGMCP_DATA_DIR"]).expanduser()
    system = system or system_name()
    home = home or Path.home()
    if system == "Windows":
        return Path(environ.get("LOCALAPPDATA", home / "AppData/Local")) / "OpenBankingMCP" / "data"
    if system == "Linux":
        return Path(environ.get("XDG_DATA_HOME", home / ".local/share")) / "openbankingmcp"
    # Preserve the original macOS location so existing encrypted data is found.
    return home / ".local/share/openbankingmcp"


def install_root(
    system: str | None = None,
    home: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> Path:
    environ = environ or os.environ
    if environ.get("OPENBANKINGMCP_INSTALL_DIR"):
        return Path(environ["OPENBANKINGMCP_INSTALL_DIR"]).expanduser()
    system = system or system_name()
    home = home or Path.home()
    if system == "Windows":
        return Path(environ.get("LOCALAPPDATA", home / "AppData/Local")) / "OpenBankingMCP"
    if system == "Linux":
        return Path(environ.get("XDG_DATA_HOME", home / ".local/share")) / "openbankingmcp"
    return home / "Library/Application Support/OpenBankingMCP"
