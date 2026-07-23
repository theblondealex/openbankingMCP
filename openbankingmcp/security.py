"""Local security primitives; values deliberately never enter application logs."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
import subprocess
import platform
from pathlib import Path
from typing import Protocol


class SecretStore(Protocol):
    """Minimal interface implemented by each operating system's credential store."""

    display_name: str

    def get(self, name: str) -> str | None: ...

    def set(self, name: str, value: str) -> None: ...


class SecretStoreUnavailable(RuntimeError):
    """The operating system has no usable secure credential store."""


class MacOSKeychain:
    """Small macOS Keychain adapter compatible with existing installations."""

    service = "openbankingmcp"
    display_name = "macOS Keychain"

    def get(self, name: str) -> str | None:
        result = subprocess.run(["security", "find-generic-password", "-s", self.service, "-a", name, "-w"], capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else None

    def set(self, name: str, value: str) -> None:
        result = subprocess.run(["security", "add-generic-password", "-U", "-s", self.service, "-a", name, "-w", value], capture_output=True)
        if result.returncode:
            raise SecretStoreUnavailable()


class KeyringSecretStore:
    """Windows Credential Manager or Linux Secret Service through python-keyring."""

    service = "openbankingmcp"

    def __init__(self, system_name: str, backend=None):
        if backend is None:
            try:
                import keyring
                backend = keyring.get_keyring()
            except Exception:
                raise SecretStoreUnavailable(secret_store_help(system_name)) from None
        backend_module = type(backend).__module__.lower()
        if system_name == "Windows" and "windows" not in backend_module:
            raise SecretStoreUnavailable(secret_store_help(system_name))
        if system_name == "Linux" and not any(name in backend_module for name in ("secretservice", "kwallet")):
            raise SecretStoreUnavailable(secret_store_help(system_name))
        self.backend = backend
        self.display_name = "Windows Credential Manager" if system_name == "Windows" else "Linux Secret Service"

    def get(self, name: str) -> str | None:
        try:
            return self.backend.get_password(self.service, name)
        except Exception:
            raise SecretStoreUnavailable() from None

    def set(self, name: str, value: str) -> None:
        try:
            self.backend.set_password(self.service, name, value)
        except Exception:
            raise SecretStoreUnavailable() from None


def secret_store_help(system_name: str | None = None) -> str:
    system_name = system_name or platform.system()
    if system_name == "Darwin":
        return "Unlock your macOS login Keychain, then try again."
    if system_name == "Windows":
        return "Unlock Windows Credential Manager, then try again."
    if system_name == "Linux":
        return "Start and unlock GNOME Keyring, KWallet, or another Secret Service provider, then try again."
    return "OpenBankingMCP supports macOS, Windows, and desktop Linux."


def system_secret_store(system_name: str | None = None, backend=None) -> SecretStore:
    system_name = system_name or platform.system()
    if system_name == "Darwin":
        return MacOSKeychain()
    if system_name in {"Windows", "Linux"}:
        return KeyringSecretStore(system_name, backend)
    raise SecretStoreUnavailable(secret_store_help(system_name))


def credential_store_name(system_name: str | None = None) -> str:
    system_name = system_name or platform.system()
    return {
        "Darwin": "macOS Keychain",
        "Windows": "Windows Credential Manager",
        "Linux": "Linux Secret Service",
    }.get(system_name, "system credential store")


# Compatibility names for code importing the original macOS-only adapter.
Keychain = MacOSKeychain
KeychainUnavailable = SecretStoreUnavailable


class Vault:
    """Authenticated encryption backed by cryptography's Fernet implementation."""

    def __init__(self, key: str):
        from cryptography.fernet import Fernet
        self._fernet = Fernet(key.encode())

    @classmethod
    def from_secret_store(cls, secret_store: SecretStore) -> "Vault":
        key = secret_store.get("database-encryption-key")
        if not key:
            from cryptography.fernet import Fernet
            key = Fernet.generate_key().decode()
            secret_store.set("database-encryption-key", key)
        return cls(key)

    from_keychain = from_secret_store

    def encrypt(self, value: str) -> bytes:
        return self._fernet.encrypt(value.encode())

    def decrypt(self, value: bytes) -> str:
        return self._fernet.decrypt(value).decode()


def csrf_token() -> str:
    return secrets.token_urlsafe(32)


def redact(value: str | None) -> str | None:
    if not value:
        return value
    value = re.sub(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b", "[redacted IBAN]", value, flags=re.I)
    return value if len(value) <= 24 else value[:10] + "…" + value[-4:]


def masked_identifier(value: str | None) -> str | None:
    return None if not value else "••••" + value[-4:]
