import subprocess

import pytest

from openbankingmcp.security import Keychain, KeyringSecretStore, KeychainUnavailable


def test_keychain_save_failure_has_a_safe_error(monkeypatch):
    monkeypatch.setattr(
        "openbankingmcp.security.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 1),
    )
    with pytest.raises(KeychainUnavailable):
        Keychain().set("truelayer-client-secret", "secret")


def test_windows_uses_credential_manager_backend():
    Backend = type(
        "Keyring",
        (),
        {
            "__module__": "keyring.backends.Windows",
            "values": {},
            "get_password": lambda self, service, name: self.values.get((service, name)),
            "set_password": lambda self, service, name, value: self.values.__setitem__((service, name), value),
        },
    )
    secret_store = KeyringSecretStore("Windows", Backend())
    secret_store.set("client-secret", "secret")
    assert secret_store.get("client-secret") == "secret"
    assert secret_store.display_name == "Windows Credential Manager"


def test_linux_refuses_non_secret_service_backend():
    Backend = type("Keyring", (), {"__module__": "keyring.backends.fail"})
    with pytest.raises(KeychainUnavailable, match="Secret Service"):
        KeyringSecretStore("Linux", Backend())
