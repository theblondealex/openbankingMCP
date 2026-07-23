import json
from pathlib import Path

from openbankingmcp.client_install import client_paths, install_claude, install_codex, is_detected


def test_installs_claude_without_overwriting_existing_servers(tmp_path: Path):
    path = tmp_path / "claude.json"
    path.write_text('{"mcpServers":{"other":{"command":"other"}}}')
    assert install_claude(path, tmp_path)
    data = json.loads(path.read_text())
    assert "other" in data["mcpServers"]
    assert "openbankingmcp" in data["mcpServers"]


def test_installs_codex_without_replacing_config(tmp_path: Path):
    path = tmp_path / "config.toml"
    path.write_text('model = "test"\n')
    assert install_codex(path, tmp_path)
    assert 'model = "test"' in path.read_text()
    assert "[mcp_servers.openbankingmcp]" in path.read_text()


def test_detects_claude_desktop_before_its_config_file_exists(tmp_path: Path):
    app = tmp_path / "Applications" / "Claude.app"
    app.mkdir(parents=True)
    assert is_detected(
        "Claude Desktop",
        tmp_path / "Library/Application Support/Claude/claude_desktop_config.json",
        tmp_path,
        "Darwin",
    )


def test_uses_native_claude_desktop_config_paths(tmp_path: Path):
    windows = client_paths(tmp_path, "Windows", {"APPDATA": "C:/Users/Alex/AppData/Roaming"})
    linux = client_paths(tmp_path, "Linux", {"XDG_CONFIG_HOME": "/home/alex/.config"})
    assert str(windows["Claude Desktop"]).replace("\\", "/").endswith("AppData/Roaming/Claude/claude_desktop_config.json")
    assert linux["Claude Desktop"] == Path("/home/alex/.config/Claude/claude_desktop_config.json")


def test_codex_toml_escapes_windows_paths(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("openbankingmcp.client_install.sys.executable", r"C:\Open Banking\python.exe")
    path = tmp_path / "config.toml"
    install_codex(path, Path(r"C:\Open Banking\app"))
    assert 'command = "C:\\\\Open Banking\\\\python.exe"' in path.read_text()
