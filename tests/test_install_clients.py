from openbankingmcp.install_clients import main

def test_installer_has_a_standalone_entrypoint():
    assert callable(main)
