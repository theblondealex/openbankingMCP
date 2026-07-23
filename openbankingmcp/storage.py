"""Versioned SQLite store. Amounts are always integer minor currency units."""

from __future__ import annotations

import json
import hashlib
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from filelock import FileLock

from .security import Vault


MIGRATIONS = [
    """CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY);
    CREATE TABLE IF NOT EXISTS connections (
      id TEXT PRIMARY KEY, provider TEXT NOT NULL, status TEXT NOT NULL,
      credentials BLOB, payload BLOB, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS accounts (
      id TEXT PRIMARY KEY, connection_id TEXT NOT NULL REFERENCES connections(id) ON DELETE CASCADE,
      alias TEXT NOT NULL, masked_identifier TEXT, account_type TEXT, currency TEXT NOT NULL,
      updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS balances (
      id INTEGER PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
      amount_minor INTEGER NOT NULL, currency TEXT NOT NULL, observed_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS transactions (
      id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
      booked_on TEXT NOT NULL, amount_minor INTEGER NOT NULL, currency TEXT NOT NULL,
      merchant TEXT, reference TEXT, category TEXT NOT NULL, raw_payload BLOB, created_at TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS transactions_account_date ON transactions(account_id, booked_on DESC);
    CREATE TABLE IF NOT EXISTS oauth_states (state_hash TEXT PRIMARY KEY, expires_at TEXT NOT NULL, used_at TEXT);
    CREATE TABLE IF NOT EXISTS audit_events (id INTEGER PRIMARY KEY, at TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL);
    """
,
    "ALTER TABLE oauth_states ADD COLUMN connection_id TEXT",
    "ALTER TABLE transactions ADD COLUMN status TEXT NOT NULL DEFAULT 'booked'"
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: Path, vault: Vault):
        self.path, self.vault = path, vault
        self.encrypted_path = path.with_suffix(path.suffix + ".enc")
        self.lock_path = self.encrypted_path.with_suffix(self.encrypted_path.suffix + ".lock")
        path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(path.parent, 0o700)
        self._lock = threading.RLock()
        self._file_lock = FileLock(str(self.lock_path))
        self._connection = self._new_connection()
        self._legacy_path = path if path.exists() and not self.encrypted_path.exists() else None
        self._load()
        self.migrate()

        if self._legacy_path:
            self._legacy_path.unlink()

    def _new_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(":memory:", check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _load(self) -> None:
        if self.encrypted_path.exists():
            self._connection.execute("PRAGMA foreign_keys=OFF")
            self._connection.executescript(self.vault.decrypt(self.encrypted_path.read_bytes()))
            self._connection.execute("PRAGMA foreign_keys=ON")
        elif self._legacy_path:
            legacy = sqlite3.connect(self._legacy_path)
            try:
                legacy.backup(self._connection)
            finally:
                legacy.close()

    def _reload(self) -> None:
        self._connection.close()
        self._connection = self._new_connection()
        self._load()

    def _persist(self) -> None:
        dump = "\n".join(self._connection.iterdump())
        temporary = self.encrypted_path.with_suffix(self.encrypted_path.suffix + ".tmp")
        temporary.write_bytes(self.vault.encrypt(dump))
        os.chmod(temporary, 0o600)
        os.replace(temporary, self.encrypted_path)
        os.chmod(self.encrypted_path, 0o600)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        with self._lock, self._file_lock:
            os.chmod(self.lock_path, 0o600)
            try:
                self._reload()
                yield self._connection
            except Exception:
                self._connection.rollback()
                raise
            else:
                self._connection.commit()
                self._persist()

    def migrate(self) -> None:
        with self.connect() as con:
            con.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY)")
            current = {row[0] for row in con.execute("SELECT version FROM schema_migrations")}
            for version, sql in enumerate(MIGRATIONS, 1):
                if version not in current:
                    con.executescript(sql)
                    con.execute("INSERT INTO schema_migrations(version) VALUES (?)", (version,))

    def audit(self, actor: str, action: str) -> None:
        with self.connect() as con:
            con.execute("INSERT INTO audit_events(at,actor,action) VALUES (?,?,?)", (now(), actor, action))

    def create_state(self, state: str, expires_at: str, connection_id: str) -> None:
        with self.connect() as con: con.execute("INSERT INTO oauth_states(state_hash,expires_at,connection_id) VALUES (?,?,?)",(hashlib.sha256(state.encode()).hexdigest(),expires_at,connection_id))
    def consume_state(self, state: str) -> str | None:
        with self.connect() as con:
            row=con.execute("SELECT used_at,expires_at,connection_id FROM oauth_states WHERE state_hash=?",(hashlib.sha256(state.encode()).hexdigest(),)).fetchone()
            if not row or row["used_at"] or row["expires_at"]<now(): return None
            con.execute("UPDATE oauth_states SET used_at=? WHERE state_hash=?",(now(),hashlib.sha256(state.encode()).hexdigest())); return row["connection_id"]

    def save_connection(self, connection_id: str, provider: str, status: str, credentials: dict[str, Any], payload: dict[str, Any]) -> None:
        encrypted = self.vault.encrypt(json.dumps(credentials))
        encrypted_payload = self.vault.encrypt(json.dumps(payload))
        with self.connect() as con:
            con.execute("""INSERT INTO connections VALUES (?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
              status=excluded.status,credentials=excluded.credentials,payload=excluded.payload,updated_at=excluded.updated_at""",
              (connection_id, provider, status, encrypted, encrypted_payload, now(), now()))

    def connections(self) -> list[dict[str, Any]]:
        with self.connect() as con:
            connections = [dict(row) for row in con.execute("SELECT id,provider,status,created_at,updated_at FROM connections ORDER BY created_at DESC")]
        for connection in connections:
            if connection["provider"] == "truelayer-data-v1":
                connection["provider"] = "Bank connection"
        return connections
    def connection_credentials(self, connection_id: str) -> dict[str, Any]:
        with self.connect() as con: row=con.execute("SELECT credentials FROM connections WHERE id=?",(connection_id,)).fetchone()
        if not row or not row["credentials"]: raise KeyError(connection_id)
        return json.loads(self.vault.decrypt(row["credentials"]))

    def accounts(self, connection_id: str | None = None) -> list[dict[str, Any]]:
        query, values = "SELECT * FROM accounts", ()
        if connection_id:
            query += " WHERE connection_id=?"; values = (connection_id,)
        with self.connect() as con:
            return [dict(row) for row in con.execute(query + " ORDER BY alias", values)]

    def transactions(self, account_id: str | None, start: str, end: str) -> list[dict[str, Any]]:
        query = "SELECT * FROM transactions WHERE booked_on BETWEEN ? AND ?"
        values: tuple[Any, ...] = (start, end)
        if account_id: query += " AND account_id=?"; values += (account_id,)
        with self.connect() as con:
            return [dict(row) for row in con.execute(query + " ORDER BY booked_on DESC, id", values)]

    def upsert_transaction(self, item: dict[str, Any]) -> None:
        raw = self.vault.encrypt(json.dumps(item.get("raw_payload", {})))
        fields = (item["id"], item["account_id"], item["booked_on"], item["amount_minor"], item["currency"], item.get("merchant"), item.get("reference"), item["category"], raw, now(), item.get("status", "booked"))
        with self.connect() as con:
            con.execute("""INSERT INTO transactions
              (id,account_id,booked_on,amount_minor,currency,merchant,reference,category,raw_payload,created_at,status)
              VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
              booked_on=excluded.booked_on,amount_minor=excluded.amount_minor,currency=excluded.currency,
              merchant=excluded.merchant,reference=excluded.reference,category=excluded.category,
              raw_payload=excluded.raw_payload,status=excluded.status""", fields)

    def replace_pending_transactions(self, account_id: str, items: list[dict[str, Any]]) -> None:
        with self.connect() as con:
            con.execute("DELETE FROM transactions WHERE account_id=? AND status='pending'", (account_id,))
            for item in items:
                raw = self.vault.encrypt(json.dumps(item.get("raw_payload", {})))
                fields = (item["id"], item["account_id"], item["booked_on"], item["amount_minor"], item["currency"], item.get("merchant"), item.get("reference"), item["category"], raw, now(), "pending")
                con.execute("""INSERT INTO transactions
                  (id,account_id,booked_on,amount_minor,currency,merchant,reference,category,raw_payload,created_at,status)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                  booked_on=excluded.booked_on,amount_minor=excluded.amount_minor,currency=excluded.currency,
                  merchant=excluded.merchant,reference=excluded.reference,category=excluded.category,
                  raw_payload=excluded.raw_payload,status='pending'""", fields)

    def replace_booked_transactions(self, account_id: str, start: str, end: str, items: list[dict[str, Any]]) -> None:
        with self.connect() as con:
            con.execute("DELETE FROM transactions WHERE account_id=? AND status='booked' AND booked_on BETWEEN ? AND ?", (account_id, start, end))
            for item in items:
                raw = self.vault.encrypt(json.dumps(item.get("raw_payload", {})))
                fields = (item["id"], item["account_id"], item["booked_on"], item["amount_minor"], item["currency"], item.get("merchant"), item.get("reference"), item["category"], raw, now(), "booked")
                con.execute("""INSERT INTO transactions
                  (id,account_id,booked_on,amount_minor,currency,merchant,reference,category,raw_payload,created_at,status)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                  booked_on=excluded.booked_on,amount_minor=excluded.amount_minor,currency=excluded.currency,
                  merchant=excluded.merchant,reference=excluded.reference,category=excluded.category,
                  raw_payload=excluded.raw_payload,status='booked'""", fields)

    def upsert_account(self, item: dict[str, Any]) -> None:
        with self.connect() as con:
            con.execute("INSERT INTO accounts VALUES (?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET alias=excluded.alias,masked_identifier=excluded.masked_identifier,account_type=excluded.account_type,currency=excluded.currency,updated_at=excluded.updated_at", (item["id"],item["connection_id"],item["alias"],item.get("masked_identifier"),item.get("account_type"),item.get("currency","GBP"),now()))
    def add_balance(self, account_id: str, amount_minor: int, currency: str, observed_at: str | None = None) -> None:
        with self.connect() as con:
            con.execute("INSERT INTO balances(account_id,amount_minor,currency,observed_at) VALUES (?,?,?,?)", (account_id,amount_minor,currency,observed_at or now()))
    def set_connection_status(self, connection_id: str, status: str) -> None:
        with self.connect() as con: con.execute("UPDATE connections SET status=?,updated_at=? WHERE id=?",(status,now(),connection_id))
    def set_connection_provider(self, connection_id: str, provider: str) -> None:
        with self.connect() as con: con.execute("UPDATE connections SET provider=?,updated_at=? WHERE id=?",(provider,now(),connection_id))
    def retain_since(self, day: str) -> int:
        with self.connect() as con:
            result=con.execute("DELETE FROM transactions WHERE booked_on < ?",(day,)); return result.rowcount
    def audit_events(self) -> list[dict[str, Any]]:
        with self.connect() as con: return [dict(row) for row in con.execute("SELECT at,actor,action FROM audit_events ORDER BY id DESC")]
