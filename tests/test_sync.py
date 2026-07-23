from pathlib import Path
from datetime import date, datetime, timezone
from cryptography.fernet import Fernet
from openbankingmcp.security import Vault
from openbankingmcp.storage import Store
from openbankingmcp.sync import normalise_transaction, normalise_balance, provider_today
from openbankingmcp.sync import sync_connection
from openbankingmcp.truelayer import ProviderUnavailable
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
    sync_connection(store,Client(),"c")
    assert store.connection_credentials("c")["access_token"] == "new"
    assert store.connections()[0]["provider"] == "Synthetic Bank"
    assert (date.fromisoformat(transaction_ranges[0][1]) - date.fromisoformat(transaction_ranges[0][0])).days == 89
    assert store.transactions("a","2026-01-01","2026-01-03")[0]["amount_minor"] == -250


def test_v1_sync_uses_card_endpoints_without_relying_on_optional_token_scope(tmp_path: Path):
    store=Store(tmp_path/"x.sqlite",Vault(Fernet.generate_key().decode()))
    store.save_connection("c","truelayer-data-v1","connected",{"access_token":"token"},{})
    class Client:
        def v1_accounts(self, token): return []
        def v1_cards(self, token): return [{"account_id":"card-id","display_name":"Credit card","partial_card_number":"0006","currency":"GBP","provider":{"display_name":"Card Bank"}}]
        def card_balance(self, token, account): return {"amount_in_minor":1000,"currency":"GBP"}
        def card_transactions(self, token, account, start, end): return [{"id":"transaction","amount_in_minor":-250,"currency":"GBP","timestamp":"2026-01-02T00:00:00Z","description":"Pretend Coffee Ltd"}]
    sync_connection(store,Client(),"c")
    assert store.accounts("c")[0]["id"] == "card:card-id"
    assert store.transactions("card:card-id","2026-01-01","2026-01-03")[0]["id"] == "card:card-id:transaction"


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
