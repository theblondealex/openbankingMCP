from pathlib import Path


def test_installer_creates_an_isolated_local_service_then_runs_setup():
    script = (Path(__file__).parents[1] / "scripts" / "install.sh").read_text()
    assert "git clone --depth 1" in script
    assert "python3 -m venv" in script
    assert "openbanking-mcp-service\" install" in script
    assert "openbanking-mcp-configure" in script
    assert "openbanking-mcp-doctor" in script
    assert "Could not download OpenBankingMCP" in script
    assert "--branch \"$RELEASE_VERSION\"" in script
    assert "Darwin)" in script
    assert "Linux)" in script


def test_windows_installer_has_the_same_guided_flow():
    script = (Path(__file__).parents[1] / "scripts" / "install.ps1").read_text()
    assert "Windows Credential Manager" not in script
    assert "openbanking-mcp-configure.exe" in script
    assert "openbanking-mcp-service.exe" in script
    assert "openbanking-mcp-doctor.exe" in script
    assert "v0.3.1" in script
