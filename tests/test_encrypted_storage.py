import sqlite3
import stat
from pathlib import Path

from cryptography.fernet import Fernet

from openbankingmcp.security import Vault
from openbankingmcp.storage import MIGRATIONS, Store


def test_financial_rows_are_persisted_only_in_an_encrypted_file(tmp_path: Path):
    path = tmp_path / "finance.sqlite3"
    vault = Vault(Fernet.generate_key().decode())
    store = Store(path, vault)
    store.save_connection("connection", "Monzo", "connected", {"access_token": "token"}, {})
    store.upsert_account({"id": "account", "connection_id": "connection", "alias": "Transaction account", "currency": "GBP"})
    store.upsert_transaction({"id": "transaction", "account_id": "account", "booked_on": "2026-07-23", "amount_minor": -1234, "currency": "GBP", "merchant": "Private Merchant", "reference": "Private reference", "category": "shopping", "raw_payload": {}})

    assert not path.exists()
    assert store.encrypted_path.exists()
    assert b"Private Merchant" not in store.encrypted_path.read_bytes()
    assert stat.S_IMODE(store.encrypted_path.stat().st_mode) == 0o600

    reopened = Store(path, vault)
    assert reopened.transactions("account", "2026-07-23", "2026-07-23")[0]["merchant"] == "Private Merchant"


def test_existing_plaintext_database_is_migrated_then_removed(tmp_path: Path):
    path = tmp_path / "legacy.sqlite3"
    legacy = sqlite3.connect(path)
    legacy.executescript(MIGRATIONS[0])
    legacy.executescript(MIGRATIONS[1])
    legacy.execute("INSERT INTO schema_migrations(version) VALUES (1)")
    legacy.execute("INSERT INTO schema_migrations(version) VALUES (2)")
    legacy.execute("INSERT INTO connections VALUES (?,?,?,?,?,?,?)", ("connection", "Monzo", "connected", b"", b"", "2026-07-23", "2026-07-23"))
    legacy.commit()
    legacy.close()

    store = Store(path, Vault(Fernet.generate_key().decode()))

    assert not path.exists()
    assert store.encrypted_path.exists()
    assert store.connections()[0]["provider"] == "Monzo"


def test_separate_store_processes_reload_before_each_operation(tmp_path: Path):
    path = tmp_path / "app.sqlite"
    vault = Vault(Fernet.generate_key().decode())
    first, second = Store(path, vault), Store(path, vault)

    first.save_connection("first", "First Bank", "connected", {}, {})
    second.save_connection("second", "Second Bank", "connected", {}, {})

    assert {connection["provider"] for connection in first.connections()} == {"First Bank", "Second Bank"}
