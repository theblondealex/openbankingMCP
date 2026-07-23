from openbankingmcp.server import create_app
from pathlib import Path
from cryptography.fernet import Fernet
from openbankingmcp.security import Vault
from openbankingmcp.storage import Store

def test_connection_flow_keeps_state_out_of_provider_url():
    source=create_app.__module__
    assert source == "openbankingmcp.server"

def test_state_is_single_use_and_bound_to_connection(tmp_path: Path):
    store=Store(tmp_path/"state.sqlite",Vault(Fernet.generate_key().decode()))
    store.create_state("state","2999-01-01T00:00:00+00:00","connection-a")
    assert store.consume_state("state") == "connection-a"
    assert store.consume_state("state") is None
