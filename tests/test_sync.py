from pathlib import Path
from datetime import date, datetime, timezone
from cryptography.fernet import Fernet
import pytest
from openbankingmcp.security import Vault
from openbankingmcp.storage import Store
from openbankingmcp.sync import ScopeUpdateRequired, normalise_transaction, normalise_balance, provider_today
from openbankingmcp.sync import sync_connection
from openbankingmcp.truelayer import EndpointNotSupported, ProviderUnavailable
from openbankingmcp.retention import DEFAULT_RETENTION_DAYS

def test_normalisation_uses_minor_units_and_deterministic_category(tmp_path: Path):
    store=Store(tmp_path/"x.sqlite",Vault(Fernet.generate_key().decode()))
    item=normalise_transaction("a",{"id":"t","amount_in_minor":-250,"currency":"GBP","timestamp":"2026-01-02T12:00:00Z","merchant_name":"Pretend Coffee Ltd"})
    assert item["amount_minor"] == -250
    assert item["booked_on"] == "2026-01-02"
    assert item["category"] == "dining"

def test_normalisation_converts_documented_v1_major_units():
    item=normalise_transaction("a",{"id":"t","amount":-2.5,"currency":"GBP","timestamp":"2026-01-02T12:00:00Z","description":"Pretend Coffee Ltd"})
    assert item["amount_minor"] == -250


def test_normalisation_uses_documented_v1_transaction_id():
    item=normalise_transaction("a",{"transaction_id":"v1-id","amount":-2.5,"currency":"GBP","timestamp":"2026-01-02T12:00:00Z","description":"Pretend Coffee Ltd"})
    assert item["id"] == "v1-id"


def test_card_debits_and_credits_use_the_internal_cashflow_sign():
    debit=normalise_transaction("card:a",{"transaction_id":"debit","amount":2.5,"currency":"GBP","timestamp":"2026-01-02T12:00:00Z","transaction_type":"DEBIT"},is_card=True)
    credit=normalise_transaction("card:a",{"transaction_id":"credit","amount":-1.25,"currency":"GBP","timestamp":"2026-01-02T12:00:00Z","transaction_type":"CREDIT"},is_card=True)
    assert debit["amount_minor"] == -250
    assert credit["amount_minor"] == 125


def test_balance_normalisation_converts_major_units():
    assert normalise_balance({"available": "10.01"},"GBP") == 1001


def test_provider_dates_use_utc_not_the_macos_local_timezone(monkeypatch):
    class Clock:
        @classmethod
        def now(cls, _timezone): return datetime(2026, 7, 22, 23, 7, tzinfo=timezone.utc)
    monkeypatch.setattr("openbankingmcp.sync.datetime", Clock)
    assert provider_today() == date(2026, 7, 22)

def test_retention_removes_only_expired_transactions(tmp_path: Path):
    store=Store(tmp_path/"x.sqlite",Vault(Fernet.generate_key().decode()))
    assert store.retain_since("2026-01-01") == 0
    assert DEFAULT_RETENTION_DAYS == 365

def test_v1_sync_encrypts_credentials_and_upserts_data(tmp_path: Path):
    store=Store(tmp_path/"x.sqlite",Vault(Fernet.generate_key().decode()))
    store.save_connection("c","truelayer-data-v1","connected",{"access_token":"old","refresh_token":"refresh"},{})
    transaction_ranges=[]
    class Client:
        def refresh(self, token): return {"access_token":"new","refresh_token":"new-refresh"}
        def v1_accounts(self, token): return [{"account_id":"a","display_name":"Synthetic account","currency":"GBP","provider":{"display_name":"Synthetic Bank"}}]
        def balance(self, token, account): return {"amount_in_minor":1000,"currency":"GBP"}
        def transactions(self, token, account, start, end):
            transaction_ranges.append((start,end))
            return [{"id":"t","amount_in_minor":-250,"currency":"GBP","timestamp":"2026-01-02T00:00:00Z","description":"Pretend Coffee Ltd"}]
        def pending_transactions(self, token, account):
            return [{"transaction_id":"pending","amount":-1.5,"currency":"GBP","timestamp":"2026-01-03T00:00:00Z","description":"Pending Coffee"}]
    sync_connection(store,Client(),"c")
    assert store.connection_credentials("c")["access_token"] == "new"
    assert store.connections()[0]["provider"] == "Synthetic Bank"
    assert (date.fromisoformat(transaction_ranges[0][1]) - date.fromisoformat(transaction_ranges[0][0])).days == 89
    items=store.transactions("a","2026-01-01","2026-01-03")
    assert next(item for item in items if item["status"] == "booked")["amount_minor"] == -250
    assert {item["status"] for item in items} == {"booked", "pending"}


def test_v1_sync_uses_card_endpoints_without_relying_on_optional_token_scope(tmp_path: Path):
    store=Store(tmp_path/"x.sqlite",Vault(Fernet.generate_key().decode()))
    store.save_connection("c","truelayer-data-v1","connected",{"access_token":"token"},{})
    class Client:
        def v1_accounts(self, token): return []
        def v1_cards(self, token): return [{"account_id":"card-id","display_name":"Credit card","partial_card_number":"0006","currency":"GBP","provider":{"display_name":"Card Bank"}}]
        def card_balance(self, token, account): return {"amount_in_minor":1000,"currency":"GBP"}
        def card_transactions(self, token, account, start, end): return [{"id":"transaction","amount":2.5,"currency":"GBP","timestamp":"2026-01-02T00:00:00Z","transaction_type":"DEBIT","description":"Pretend Coffee Ltd"}]
        def card_pending_transactions(self, token, account): return [{"transaction_id":"pending","amount":4.75,"currency":"GBP","timestamp":"2026-01-03T00:00:00Z","transaction_type":"DEBIT","description":"Pending Dinner"}]
    sync_connection(store,Client(),"c")
    assert store.accounts("c")[0]["id"] == "card:card-id"
    items=store.transactions("card:card-id","2026-01-01","2026-01-03")
    assert next(item for item in items if item["status"] == "booked")["id"] == "card:card-id:transaction"
    pending=next(item for item in items if item["status"] == "pending")
    assert pending["amount_minor"] == -475
    assert pending["status"] == "pending"


def test_v1_card_sync_succeeds_when_the_account_endpoint_is_unavailable(tmp_path: Path):
    store=Store(tmp_path/"x.sqlite",Vault(Fernet.generate_key().decode()))
    store.save_connection("c","truelayer-data-v1","connected",{"access_token":"token"},{})
    class Client:
        def v1_accounts(self, token): raise ProviderUnavailable("provider_unavailable")
        def v1_cards(self, token): return [{"account_id":"card-id","display_name":"Credit card","currency":"GBP","provider":{"display_name":"Card Bank"}}]
        def card_balance(self, token, account): return {"amount_in_minor":1000,"currency":"GBP"}
        def card_transactions(self, token, account, start, end): return []
    sync_connection(store,Client(),"c")
    assert store.connections()[0]["provider"] == "Card Bank"
    assert store.connections()[0]["status"] == "connected"


def test_v1_card_sync_succeeds_when_account_endpoint_is_not_implemented(tmp_path: Path):
    store=Store(tmp_path/"x.sqlite",Vault(Fernet.generate_key().decode()))
    store.save_connection("c","truelayer-data-v1","connected",{"access_token":"token"},{})
    class Client:
        def v1_accounts(self, token): raise EndpointNotSupported()
        def v1_cards(self, token): return [{"account_id":"card-id","display_name":"Credit card","currency":"GBP"}]
        def card_balance(self, token, account): return {"current":0,"currency":"GBP"}
        def card_transactions(self, token, account, start, end): return []
    sync_connection(store,Client(),"c")
    assert store.connections()[0]["status"] == "connected"


def test_pending_snapshot_removes_transactions_that_have_cleared(tmp_path: Path):
    store=Store(tmp_path/"x.sqlite",Vault(Fernet.generate_key().decode()))
    store.save_connection("c","truelayer-data-v1","connected",{"access_token":"token"},{})
    pending=[[{"transaction_id":"pending","amount":7.5,"currency":"GBP","timestamp":"2026-07-24T00:00:00Z","transaction_type":"DEBIT"}],[]]
    class Client:
        def v1_accounts(self, token): return []
        def v1_cards(self, token): return [{"account_id":"card-id","display_name":"Credit card","currency":"GBP"}]
        def card_balance(self, token, account): return {"current":0,"currency":"GBP"}
        def card_transactions(self, token, account, start, end): return []
        def card_pending_transactions(self, token, account): return pending.pop(0)
    sync_connection(store,Client(),"c")
    assert len(store.transactions("card:card-id","2026-07-24","2026-07-24")) == 1
    sync_connection(store,Client(),"c")
    assert store.transactions("card:card-id","2026-07-24","2026-07-24") == []


def test_booked_snapshot_replaces_changed_provider_ids_and_signs(tmp_path: Path):
    store=Store(tmp_path/"x.sqlite",Vault(Fernet.generate_key().decode()))
    store.save_connection("c","truelayer-data-v1","connected",{"access_token":"token"},{})
    store.upsert_account({"id":"card:card-id","connection_id":"c","alias":"Credit card","currency":"GBP"})
    store.upsert_transaction({"id":"old-id","account_id":"card:card-id","booked_on":"2026-07-23","amount_minor":110,"currency":"GBP","category":"groceries"})
    class Client:
        def v1_accounts(self, token): return []
        def v1_cards(self, token): return [{"account_id":"card-id","display_name":"Credit card","currency":"GBP"}]
        def card_balance(self, token, account): return {"current":0,"currency":"GBP"}
        def card_transactions(self, token, account, start, end): return [{"normalised_provider_transaction_id":"stable-id","transaction_id":"changing-id","amount":1.1,"currency":"GBP","timestamp":"2026-07-23T00:00:00Z","transaction_type":"DEBIT"}]
    sync_connection(store,Client(),"c")
    items=store.transactions("card:card-id","2026-07-23","2026-07-23")
    assert [(item["id"],item["amount_minor"]) for item in items] == [("card:card-id:stable-id",-110)]


def test_connection_metadata_detects_missing_read_only_scopes(tmp_path: Path):
    store=Store(tmp_path/"x.sqlite",Vault(Fernet.generate_key().decode()))
    store.save_connection("c","Bank connection","connected",{"access_token":"token"},{})
    class Client:
        def connection_metadata(self, token): return {"provider":{"display_name":"Example Bank"},"scopes":["accounts","balance","offline_access"]}
    with pytest.raises(ScopeUpdateRequired):
        sync_connection(store,Client(),"c")
    assert store.connections()[0]["provider"] == "Example Bank"
    assert store.connections()[0]["status"] == "scope_update_required"


def test_card_only_connection_has_all_required_read_only_scopes(tmp_path: Path):
    store=Store(tmp_path/"x.sqlite",Vault(Fernet.generate_key().decode()))
    store.save_connection("c","Bank connection","connected",{"access_token":"token"},{})
    class Client:
        def connection_metadata(self, token): return {"scopes":["cards","balance","transactions","offline_access"]}
        def v1_accounts(self, token): raise EndpointNotSupported()
        def v1_cards(self, token): return []
    sync_connection(store,Client(),"c")
    assert store.connections()[0]["status"] == "connected"
