import subprocess

import pytest

from openbankingmcp.security import Keychain, KeychainUnavailable


def test_keychain_save_failure_has_a_safe_error(monkeypatch):
    monkeypatch.setattr(
        "openbankingmcp.security.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 1),
    )
    with pytest.raises(KeychainUnavailable):
        Keychain().set("truelayer-client-secret", "secret")
