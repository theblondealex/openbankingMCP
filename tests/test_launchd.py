from openbankingmcp.launchd import plist

def test_plist_runs_dashboard_from_project_directory():
    value=plist("/usr/bin/python3","/tmp/openbanking.log","/project")
    assert "WorkingDirectory" in value
    assert "openbankingmcp.dashboard" in value
    assert "KeepAlive" in value
