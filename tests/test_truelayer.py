import pytest
from openbankingmcp.truelayer import ProviderUnavailable, ReauthorizationRequired, TrueLayer
from openbankingmcp.server import truelayer_client

class Response:
    def __init__(self,status): self.status_code=status
    def raise_for_status(self): raise RuntimeError(self.status_code)

@pytest.mark.parametrize("status,error",[(401,ReauthorizationRequired),(403,ReauthorizationRequired),(429,ProviderUnavailable),(500,ProviderUnavailable)])
def test_provider_errors_are_mapped_without_response_body(monkeypatch,status,error):
    monkeypatch.setattr("httpx.request",lambda *args,**kwargs: Response(status))
    with pytest.raises(error): TrueLayer("id","secret")._request("GET","https://example.test")


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
