import json
from pathlib import Path

from openbankingmcp.client_install import install_claude, install_codex, is_detected


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
    assert is_detected("Claude Desktop", tmp_path / "Library/Application Support/Claude/claude_desktop_config.json", tmp_path)
