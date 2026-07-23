from pathlib import Path


def test_installer_creates_an_isolated_local_service_then_runs_setup():
    script = (Path(__file__).parents[1] / "scripts" / "install.sh").read_text()
    assert "git clone --depth 1" in script
    assert "python3 -m venv" in script
    assert "openbanking-mcp-launchd\" install" in script
    assert "openbanking-mcp-configure" in script
    assert "openbanking-mcp-doctor" in script
    assert "Could not download OpenBankingMCP" in script
