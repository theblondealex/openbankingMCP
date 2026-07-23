from pathlib import Path
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from openbankingmcp.security import Vault
from openbankingmcp.server import create_app
from openbankingmcp import server
from openbankingmcp.storage import Store

def client(tmp_path: Path):
    return TestClient(create_app(Store(tmp_path/"app.sqlite",Vault(Fernet.generate_key().decode()))),base_url="http://127.0.0.1:3847")

def test_host_allowlist_and_session_gate(tmp_path: Path):
    app=client(tmp_path)
    assert app.get("/api/connections",headers={"host":"example.com"}).status_code == 421
    assert app.get("/api/connections").status_code == 401

def test_mutation_requires_csrf(tmp_path: Path):
    app=client(tmp_path); app.get("/")
    assert app.post("/api/connections/nope/remove").status_code == 403

def test_mcp_starts_dashboard_when_loopback_is_unavailable(monkeypatch):
    started=[]
    monkeypatch.setattr(server,"_dashboard_started",False)
    monkeypatch.setattr(server,"urlopen",lambda *args,**kwargs: (_ for _ in ()).throw(OSError()))
    monkeypatch.setattr(server.threading.Thread,"start",lambda self: started.append(True))
    server.ensure_dashboard()
    assert started == [True]
