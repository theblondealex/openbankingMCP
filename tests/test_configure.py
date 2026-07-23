import pytest

from openbankingmcp.configure import DEFAULT_REDIRECT_URI, validate_live_client_id, verify_live_credentials


def test_redirect_uri_is_a_fixed_safe_default():
    assert DEFAULT_REDIRECT_URI == "http://127.0.0.1:3847/oauth/callback"


def test_live_setup_rejects_sandbox_credentials():
    validate_live_client_id("example")
    with pytest.raises(SystemExit): validate_live_client_id("sandbox-example")


def test_live_setup_checks_credentials_before_saving(monkeypatch):
    checked = []
    monkeypatch.setattr("openbankingmcp.configure.TrueLayer.token", lambda self: checked.append((self.client_id, self.client_secret)))
    verify_live_credentials("live-client", "live-secret")
    assert checked == [("live-client", "live-secret")]


def test_live_setup_hides_invalid_credential_details(monkeypatch):
    monkeypatch.setattr("openbankingmcp.configure.TrueLayer.token", lambda self: (_ for _ in ()).throw(RuntimeError("live-secret")))
    with pytest.raises(SystemExit, match="could not verify") as error:
        verify_live_credentials("live-client", "live-secret")
    assert "live-secret" not in str(error.value)
