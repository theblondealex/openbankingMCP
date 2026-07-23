from pathlib import Path
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from openbankingmcp.security import Vault
from openbankingmcp.server import create_app
from openbankingmcp.storage import Store
from openbankingmcp.truelayer import ProviderUnavailable


class FakeSecretStore:
    display_name = "Test credential store"

    def __init__(self, values):
        self.values = values

    def get(self, name):
        return self.values.get(name)


def use_secret_store(monkeypatch, values):
    monkeypatch.setattr("openbankingmcp.server.system_secret_store", lambda: FakeSecretStore(values))


def test_connect_returns_hosted_authorization_url_without_user_profile(tmp_path: Path, monkeypatch):
    store = Store(tmp_path / "app.sqlite", Vault(Fernet.generate_key().decode()))
    app = create_app(store)
    use_secret_store(monkeypatch, {
        "truelayer-client-id": "client-id", "truelayer-client-secret": "secret",
        "truelayer-redirect-uri": "http://127.0.0.1:3847/oauth/callback",
    })
    client = TestClient(app, base_url="http://127.0.0.1:3847")
    client.get("/")
    response = client.post("/api/connect", headers={"x-csrf-token": client.cookies["obm_csrf"]})

    assert response.status_code == 200
    assert response.json()["authorization_url"].startswith("https://auth.truelayer.com/?")
    assert store.connections() == []


def test_connect_rejects_sandbox_credentials_before_creating_state(tmp_path: Path, monkeypatch):
    store = Store(tmp_path / "app.sqlite", Vault(Fernet.generate_key().decode()))
    use_secret_store(monkeypatch, {
        "truelayer-client-id": "sandbox-client-id", "truelayer-client-secret": "secret",
    })
    client = TestClient(create_app(store), base_url="http://127.0.0.1:3847")
    client.get("/")
    response = client.post("/api/connect", headers={"x-csrf-token": client.cookies["obm_csrf"]})

    assert response.status_code == 409
    assert "live TrueLayer credentials required" in response.json()["detail"]
    assert store.connections() == []


def test_connect_state_expires_ten_minutes_after_creation(tmp_path: Path, monkeypatch):
    store = Store(tmp_path / "app.sqlite", Vault(Fernet.generate_key().decode()))
    use_secret_store(monkeypatch, {
        "truelayer-client-id": "client-id", "truelayer-client-secret": "secret",
        "truelayer-redirect-uri": "http://127.0.0.1:3847/oauth/callback",
    })
    client = TestClient(create_app(store), base_url="http://127.0.0.1:3847")
    client.get("/")
    client.post("/api/connect", headers={"x-csrf-token": client.cookies["obm_csrf"]})
    with store.connect() as con:
        expires_at = datetime.fromisoformat(con.execute("SELECT expires_at FROM oauth_states").fetchone()[0])

    assert timedelta(minutes=9) < expires_at - datetime.now(timezone.utc) <= timedelta(minutes=10)


def test_callback_syncs_and_replaces_the_placeholder_provider(tmp_path: Path, monkeypatch):
    store = Store(tmp_path / "app.sqlite", Vault(Fernet.generate_key().decode()))
    store.create_state("state", "2999-01-01T00:00:00+00:00", "connection")

    class Client:
        def exchange_code(self, code, redirect_uri): return {"access_token": "token"}
        def v1_accounts(self, token): return [{"account_id": "account", "display_name": "Amex", "currency": "GBP", "provider": {"display_name": "American Express"}}]
        def balance(self, token, account_id): return {"amount_in_minor": 0, "currency": "GBP"}
        def transactions(self, token, account_id, start, end): return []

    monkeypatch.setattr("openbankingmcp.server.truelayer_client", lambda _keychain: Client())
    use_secret_store(monkeypatch, {"truelayer-redirect-uri": "http://127.0.0.1:3847/oauth/callback"})
    response = TestClient(create_app(store), base_url="http://127.0.0.1:3847").get("/oauth/callback?state=state&code=code", follow_redirects=False)

    assert response.status_code == 303
    assert store.connections()[0]["provider"] == "American Express"
    assert store.connections()[0]["status"] == "connected"


def test_callback_keeps_connection_when_provider_is_temporarily_unavailable(tmp_path: Path, monkeypatch):
    store = Store(tmp_path / "app.sqlite", Vault(Fernet.generate_key().decode()))
    store.create_state("state", "2999-01-01T00:00:00+00:00", "connection")

    class Client:
        def exchange_code(self, code, redirect_uri): return {"access_token": "token"}
        def v1_accounts(self, token): raise ProviderUnavailable("provider_unavailable")

    monkeypatch.setattr("openbankingmcp.server.truelayer_client", lambda _keychain: Client())
    use_secret_store(monkeypatch, {"truelayer-redirect-uri": "http://127.0.0.1:3847/oauth/callback"})
    response = TestClient(create_app(store), base_url="http://127.0.0.1:3847").get("/oauth/callback?state=state&code=code", follow_redirects=False)

    assert response.status_code == 303
    assert store.connections()[0]["provider"] == "Bank connection"
    assert store.connections()[0]["status"] == "sync_delayed"


def test_remove_revokes_provider_credential_before_deleting_local_data(tmp_path: Path, monkeypatch):
    store = Store(tmp_path / "app.sqlite", Vault(Fernet.generate_key().decode()))
    store.save_connection("connection", "Example Bank", "connected", {"access_token": "token"}, {})
    deleted = []
    class Client:
        def delete_credential(self, token): deleted.append(token)
    monkeypatch.setattr("openbankingmcp.server.truelayer_client", lambda _secret_store: Client())
    use_secret_store(monkeypatch, {})
    client = TestClient(create_app(store), base_url="http://127.0.0.1:3847")
    client.get("/")
    response = client.post("/api/connections/connection/remove", headers={"x-csrf-token": client.cookies["obm_csrf"]})

    assert response.status_code == 200
    assert deleted == ["token"]
    assert store.connections() == []
