from datetime import date
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from openbankingmcp.security import Vault
from openbankingmcp.server import MAX_LIMIT, TOOL_NAMES, McpConnectionError, build_tools_list, call_tool
from openbankingmcp.storage import Store


@pytest.fixture
def store(tmp_path: Path) -> Store:
    store = Store(tmp_path / "local.sqlite3", Vault(Fernet.generate_key().decode()))
    with store.connect() as con:
        con.execute("INSERT INTO connections VALUES ('c1','truelayer','connected',X'00',X'00','now','now')")
        con.execute("INSERT INTO accounts VALUES ('a1','c1','Daily account','••••1234','current','GBP','now')")
    return store


def test_only_read_only_tools_are_exposed():
    assert {tool["name"] for tool in build_tools_list()} == set(TOOL_NAMES)
    assert not {"payments", "payouts", "exchange_code", "create_data_auth_link"} & set(TOOL_NAMES)
    search=next(tool for tool in build_tools_list() if tool["name"] == "search_transactions")
    assert "query" in search["inputSchema"]["properties"]


def test_transactions_are_capped_redacted_and_deduplicated(store: Store):
    item = {"id": "t1", "account_id": "a1", "booked_on": date.today().isoformat(), "amount_minor": -1234, "currency": "GBP", "merchant": "A very long transfer party name", "reference": "A very long private payment reference", "category": "uncategorised"}
    store.upsert_transaction(item); store.upsert_transaction(item)
    result = call_tool(store, "get_transactions", {"account_id": "a1", "limit": MAX_LIMIT + 20})
    assert result["total"] == 1
    assert result["limit"] == MAX_LIMIT
    assert "…" in result["transactions"][0]["reference"]


def test_date_range_over_ninety_days_is_rejected(store: Store):
    with pytest.raises(ValueError, match="90"):
        call_tool(store, "get_transactions", {"start_date": "2026-01-01", "end_date": "2026-04-02"})

def test_data_tools_direct_user_to_authorize_when_no_connection(tmp_path: Path):
    empty=Store(tmp_path / "empty.sqlite3", Vault(Fernet.generate_key().decode()))
    with pytest.raises(McpConnectionError, match="authorization_required"):
        call_tool(empty,"get_balances",{})
    with pytest.raises(McpConnectionError, match="authorization_required"):
        call_tool(empty,"list_connections",{})
