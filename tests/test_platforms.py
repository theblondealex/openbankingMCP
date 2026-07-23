from pathlib import Path

from openbankingmcp.platforms import data_dir, install_root


def test_platform_paths_use_native_user_data_locations():
    home = Path("/users/alex")
    assert install_root("Darwin", home, {}) == home / "Library/Application Support/OpenBankingMCP"
    assert install_root("Linux", home, {}) == home / ".local/share/openbankingmcp"
    assert install_root("Windows", home, {"LOCALAPPDATA": "C:/Users/Alex/AppData/Local"}) == Path("C:/Users/Alex/AppData/Local/OpenBankingMCP")
    assert data_dir("Windows", home, {"LOCALAPPDATA": "C:/Users/Alex/AppData/Local"}).name == "data"


def test_explicit_data_directory_wins_on_every_platform():
    assert data_dir("Windows", Path("/unused"), {"OPENBANKINGMCP_DATA_DIR": "/secure/data"}) == Path("/secure/data")
