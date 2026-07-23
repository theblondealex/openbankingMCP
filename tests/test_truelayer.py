import pytest
from openbankingmcp.truelayer import EndpointNotSupported, ProhibitedEndpoint, ProviderUnavailable, ReauthorizationRequired, TrueLayer, endpoint_allowed
from openbankingmcp.server import truelayer_client

class Response:
    def __init__(self,status,payload=None): self.status_code,self.payload=status,payload or {}
    def json(self): return self.payload
    def raise_for_status(self): raise RuntimeError(self.status_code)

@pytest.mark.parametrize("status,error",[(401,ReauthorizationRequired),(403,ReauthorizationRequired),(429,ProviderUnavailable),(500,ProviderUnavailable),(501,EndpointNotSupported)])
def test_provider_errors_are_mapped_without_response_body(monkeypatch,status,error):
    monkeypatch.setattr("httpx.request",lambda *args,**kwargs: Response(status))
    with pytest.raises(error): TrueLayer("id","secret")._request("GET","https://api.truelayer.com/data/v1/accounts")


def test_invalid_refresh_grant_requires_reauthorization(monkeypatch):
    monkeypatch.setattr("httpx.request",lambda *args,**kwargs: Response(400,{"error":"invalid_grant"}))
    with pytest.raises(ReauthorizationRequired): TrueLayer("id","secret").refresh("expired")


def test_network_client_enforces_the_reviewed_read_only_endpoint_allowlist():
    assert endpoint_allowed("GET","https://api.truelayer.com/data/v1/cards/card/transactions/pending")
    assert endpoint_allowed("DELETE","https://auth.truelayer.com/api/delete")
    assert not endpoint_allowed("POST","https://api.truelayer.com/v3/payments")
    assert not endpoint_allowed("POST","https://api.truelayer.com/v3/payouts")
    with pytest.raises(ProhibitedEndpoint): TrueLayer("id","secret")._request("POST","https://api.truelayer.com/v3/payments")


def test_live_uses_live_auth_host_for_the_bank_selector():
    link = TrueLayer("id", "secret").v1_auth_link("http://127.0.0.1/callback", "state")
    assert link.startswith("https://auth.truelayer.com/?")
    assert "providers=" not in link


def test_keychain_selects_live_endpoints():
    class Keychain:
        def get(self, name): return {"truelayer-client-id": "live", "truelayer-client-secret": "secret"}.get(name)

    assert truelayer_client(Keychain()).auth_base == "https://auth.truelayer.com"


def test_account_and_card_endpoints_are_kept_separate(monkeypatch):
    client = TrueLayer("id", "secret")
    paths = []
    monkeypatch.setattr(client, "v1_get", lambda _token, path, params=None: paths.append(path) or {"results": []})

    assert client.v1_accounts("token") == []
    assert client.v1_cards("token") == []
    assert paths == ["accounts", "cards"]


def test_auth_link_requests_read_only_card_access():
    link = TrueLayer("id", "secret").v1_auth_link("http://127.0.0.1/callback", "state")
    assert "scope=accounts+cards+balance+transactions+offline_access" in link


def test_pending_transaction_endpoints_do_not_apply_a_date_range(monkeypatch):
    calls = []
    client = TrueLayer("id", "secret")
    monkeypatch.setattr(client, "v1_get", lambda token, path, params=None: calls.append((token, path, params)) or {"results": [{"transaction_id": "pending"}]})

    assert client.pending_transactions("token", "account") == [{"transaction_id": "pending"}]
    assert client.card_pending_transactions("token", "card") == [{"transaction_id": "pending"}]
    assert calls == [
        ("token", "accounts/account/transactions/pending", None),
        ("token", "cards/card/transactions/pending", None),
    ]


def test_connection_metadata_and_deletion_use_reviewed_endpoints(monkeypatch):
    calls = []
    client = TrueLayer("id", "secret")
    monkeypatch.setattr(client, "v1_get", lambda token, path, params=None: {"results": [{"scopes": ["accounts"]}]})
    monkeypatch.setattr(client, "_request", lambda method, url, **kwargs: calls.append((method, url, kwargs)))

    assert client.connection_metadata("token") == {"scopes": ["accounts"]}
    client.delete_credential("token")
    assert calls[0][0:2] == ("DELETE", "https://auth.truelayer.com/api/delete")
    assert calls[0][2]["headers"]["Authorization"] == "Bearer token"
