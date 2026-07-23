"""Local security primitives; values deliberately never enter application logs."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
import subprocess
from pathlib import Path


class Keychain:
    """Small macOS Keychain adapter with a testable environment-free interface."""

    service = "openbankingmcp"

    def get(self, name: str) -> str | None:
        result = subprocess.run(["security", "find-generic-password", "-s", self.service, "-a", name, "-w"], capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else None

    def set(self, name: str, value: str) -> None:
        result = subprocess.run(["security", "add-generic-password", "-U", "-s", self.service, "-a", name, "-w", value], capture_output=True)
        if result.returncode:
            raise KeychainUnavailable()


class KeychainUnavailable(RuntimeError):
    """macOS refused access to the login Keychain; no provider values are included."""


class Vault:
    """Authenticated encryption backed by cryptography's Fernet implementation."""

    def __init__(self, key: str):
        from cryptography.fernet import Fernet
        self._fernet = Fernet(key.encode())

    @classmethod
    def from_keychain(cls, keychain: Keychain) -> "Vault":
        key = keychain.get("database-encryption-key")
        if not key:
            from cryptography.fernet import Fernet
            key = Fernet.generate_key().decode()
            keychain.set("database-encryption-key", key)
        return cls(key)

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
