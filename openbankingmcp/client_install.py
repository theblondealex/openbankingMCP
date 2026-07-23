"""Opt-in MCP registration for the locally installed desktop clients."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Callable


SERVER_NAME = "openbankingmcp"


def client_paths(home: Path) -> dict[str, Path]:
    return {
        "Claude Desktop": home / "Library/Application Support/Claude/claude_desktop_config.json",
        "Claude Code": home / ".claude.json",
        "Codex": home / ".codex/config.toml",
    }


def _definition(root: Path) -> dict[str, object]:
    return {"command": sys.executable, "args": ["-m", "openbankingmcp"], "cwd": str(root)}


def install_claude(path: Path, root: Path) -> bool:
    data = json.loads(path.read_text()) if path.exists() and path.read_text().strip() else {}
    servers = data.setdefault("mcpServers", {})
    if SERVER_NAME in servers:
        return False
    servers[SERVER_NAME] = _definition(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
    return True


def install_codex(path: Path, root: Path) -> bool:
    section = f"[mcp_servers.{SERVER_NAME}]"
    current = path.read_text() if path.exists() else ""
    if section in current:
        return False
    addition = "\n".join(["", section, f'command = "{sys.executable}"', 'args = ["-m", "openbankingmcp"]', f'cwd = "{root}"', ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(current.rstrip() + addition)
    return True


def is_detected(name: str, path: Path, home: Path) -> bool:
    if path.exists():
        return True
    if name == "Claude Desktop":
        return (home / "Applications/Claude.app").exists() or Path("/Applications/Claude.app").exists()
    if name == "Claude Code":
        return (home / ".claude").exists() or shutil.which("claude") is not None
    if name == "Codex":
        return (home / ".codex").exists() or shutil.which("codex") is not None
    return False


def offer_install(root: Path, home: Path, ask: Callable[[str], str] = input) -> list[str]:
    installed: list[str] = []
    for name, path in client_paths(home).items():
        if not is_detected(name, path, home):
            continue
        if ask(f"Install OpenBankingMCP for {name}? [y/N]: ").strip().lower() not in {"y", "yes"}:
            continue
        changed = install_codex(path, root) if name == "Codex" else install_claude(path, root)
        installed.append(f"{name}{'' if changed else ' (already configured)'}")
    return installed
