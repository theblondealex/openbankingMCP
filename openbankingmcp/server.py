"""Loopback dashboard and stdio MCP server for local financial data."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import sys
import threading
from urllib.parse import urlencode
from urllib.request import urlopen
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from .reporting import recurring, summarise
from .security import Keychain, KeychainUnavailable, Vault, csrf_token, redact
from .storage import Store
from .truelayer import ProviderUnavailable, ReauthorizationRequired, TrueLayer

TOOL_NAMES = ("list_connections", "list_accounts", "get_balances", "get_transactions", "weekly_spending_summary", "monthly_spending_summary", "spending_by_category", "compare_periods", "find_recurring_spending", "search_transactions", "largest_transactions", "uncategorised_transactions", "explain_balance_change")
MAX_RANGE_DAYS, DEFAULT_LIMIT, MAX_LIMIT = 90, 25, 100
_dashboard_started = False

class McpConnectionError(Exception):
    """Safe, actionable MCP errors; never include provider credentials or payloads."""


def default_store() -> Store:
    root = Path(os.getenv("OPENBANKINGMCP_DATA_DIR", "~/.local/share/openbankingmcp")).expanduser()
    return Store(root / "openbankingmcp.sqlite3", Vault.from_keychain(Keychain()))


def truelayer_client(keychain: Keychain | None = None) -> TrueLayer:
    keychain = keychain or Keychain()
    return TrueLayer(keychain.get("truelayer-client-id") or "", keychain.get("truelayer-client-secret") or "")


def ensure_dashboard() -> None:
    """Make the authorization URL actionable for MCP clients without exposing a network service."""
    global _dashboard_started
    try:
        with urlopen("http://127.0.0.1:3847/", timeout=0.25): return
    except Exception: pass
    if _dashboard_started: return
    _dashboard_started = True
    threading.Thread(target=start, daemon=True, name="openbankingmcp-dashboard").start()


def _parse_dates(arguments: dict[str, Any]) -> tuple[str, str]:
    today = date.today()
    start = date.fromisoformat(arguments.get("start_date", (today - timedelta(days=6)).isoformat()))
    end = date.fromisoformat(arguments.get("end_date", today.isoformat()))
    if start > end or (end - start).days > MAX_RANGE_DAYS:
        raise ValueError("date range must be ordered and at most 90 days")
    return start.isoformat(), end.isoformat()


def _tool(name: str, description: str, properties: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"name": name, "description": description, "inputSchema": {"type": "object", "properties": properties or {}, "additionalProperties": False}}


def build_tools_list() -> list[dict[str, Any]]:
    dates = {"account_id": {"type": "string"}, "start_date": {"type": "string", "format": "date"}, "end_date": {"type": "string", "format": "date"}}
    summaries=[_tool(name, "Read-only deterministic local financial summary.", dates) for name in ("weekly_spending_summary","monthly_spending_summary","spending_by_category","compare_periods","find_recurring_spending","largest_transactions","uncategorised_transactions","explain_balance_change")]
    return [_tool("list_connections", "List local connection status."), _tool("list_accounts", "List connected accounts with aliases and masked identifiers."), _tool("get_balances", "Return latest local balances.", {"account_id": {"type": "string"}}), _tool("get_transactions", "Return redacted transactions; defaults to seven days and 25 results.", {**dates, "limit": {"type": "integer", "minimum": 1, "maximum": 100}}), *summaries, _tool("search_transactions", "Search redacted local transactions.", {**dates,"query":{"type":"string","minLength":1}})]


def _public_transaction(item: dict[str, Any]) -> dict[str, Any]:
    return {key: (redact(value) if key in {"merchant", "reference"} else value) for key, value in item.items() if key not in {"raw_payload", "created_at"}}


def call_tool(store: Store, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name not in TOOL_NAMES:
        raise ValueError("unknown or prohibited tool")
    store.audit("mcp", "tool:" + name)
    statuses=[connection["status"] for connection in store.connections()]
    if not statuses:
        raise McpConnectionError("authorization_required: Connect an account in the local dashboard at http://127.0.0.1:3847.")
    if "reauthorization_required" in statuses:
        raise McpConnectionError("reauthorization_required: Reconnect the affected account in the local dashboard at http://127.0.0.1:3847.")
    if name == "list_connections": return {"connections": store.connections()}
    if name == "list_accounts": return {"accounts": store.accounts()}
    if name == "get_balances":
        account_id = arguments.get("account_id")
        with store.connect() as con:
            query = "SELECT b.account_id,b.amount_minor,b.currency,b.observed_at FROM balances b WHERE b.id IN (SELECT MAX(id) FROM balances GROUP BY account_id)"
            values: tuple[str, ...] = ()
            if account_id: query += " AND b.account_id=?"; values = (account_id,)
            return {"balances": [dict(row) for row in con.execute(query, values)]}
    start, end = _parse_dates(arguments)
    items = store.transactions(arguments.get("account_id"), start, end)
    if name == "get_transactions":
        limit = min(int(arguments.get("limit", DEFAULT_LIMIT)), MAX_LIMIT)
        return {"transactions": [_public_transaction(item) for item in items[:limit]], "total": len(items), "limit": limit}
    if name in {"weekly_spending_summary", "monthly_spending_summary", "spending_by_category"}: return summarise(items)
    if name == "find_recurring_spending": return {"recurring": recurring(items)}
    if name == "search_transactions":
        term = str(arguments.get("query", "")).lower()
        return {"transactions": [_public_transaction(item) for item in items if term in (item.get("merchant") or "").lower()][:MAX_LIMIT]}
    if name == "largest_transactions": return {"transactions": [_public_transaction(item) for item in sorted(items, key=lambda row: abs(row["amount_minor"]), reverse=True)[:10]]}
    if name == "uncategorised_transactions": return {"transactions": [_public_transaction(item) for item in items if item["category"] == "uncategorised"][:MAX_LIMIT]}
    if name == "compare_periods":
        days = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
        prior_end = date.fromisoformat(start) - timedelta(days=1); prior_start = prior_end - timedelta(days=days - 1)
        return {"current": summarise(items), "previous": summarise(store.transactions(arguments.get("account_id"), prior_start.isoformat(), prior_end.isoformat()))}
    if name == "explain_balance_change":
        summary = summarise(items)
        return {"net_movement_minor": summary["income_minor"] - summary["spending_minor"], "income_minor": summary["income_minor"], "spending_minor": summary["spending_minor"], "categories_minor": summary["by_category_minor"], "largest_contributors": [_public_transaction(item) for item in sorted(items, key=lambda row: abs(row["amount_minor"]), reverse=True)[:10]]}
    raise ValueError("unsupported tool")


def create_app(store: Store | None = None) -> FastAPI:
    store = store or default_store()
    secret = secrets.token_urlsafe(32)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    dashboard_dist=Path(__file__).resolve().parents[1] / "web" / "dist"
    if (dashboard_dist / "assets").is_dir(): app.mount("/assets",StaticFiles(directory=dashboard_dist / "assets"),name="assets")

    @app.middleware("http")
    async def loopback_only(request: Request, call_next):
        host = request.headers.get("host", "").lower()
        if host not in {"127.0.0.1:3847", "localhost:3847"}:
            return Response(status_code=421)
        return await call_next(request)

    def session(request: Request) -> str:
        value = request.cookies.get("obm_session")
        if value != secret: raise HTTPException(401, "local session required")
        return value

    def check_csrf(request: Request) -> None:
        session(request)
        if request.headers.get("x-csrf-token") != request.cookies.get("obm_csrf"): raise HTTPException(403, "invalid CSRF token")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> Response:
        token = csrf_token()
        response = FileResponse(dashboard_dist / "index.html") if (dashboard_dist / "index.html").exists() else HTMLResponse("<main><h1>OpenBankingMCP</h1><p>Run <code>yarn build</code> in web/ to build the local dashboard.</p></main>")
        response.set_cookie("obm_session", secret, httponly=True, samesite="strict")
        response.set_cookie("obm_csrf", token, httponly=False, samesite="strict")
        return response

    @app.get("/api/connections")
    async def connections(request: Request) -> dict[str, Any]:
        session(request); return {"connections": store.connections()}

    @app.get("/api/privacy")
    async def privacy(request: Request) -> dict[str, Any]:
        session(request); return {"local_only": True, "retention_days": 365, "credentials": "macOS Keychain", "financial_data": "encrypted local cache"}

    @app.get("/api/audit-log")
    async def audit_log(request: Request) -> dict[str, Any]:
        session(request); return {"events": store.audit_events()}

    @app.post("/api/connections/{connection_id}/sync")
    async def sync(connection_id: str, request: Request) -> dict[str, str]:
        check_csrf(request)
        from .sync import sync_connection
        keychain=Keychain(); client=truelayer_client(keychain)
        try: sync_connection(store, client, connection_id)
        except ReauthorizationRequired:
            raise HTTPException(409, "reauthorization_required")
        except ProviderUnavailable:
            raise HTTPException(503, "TrueLayer is temporarily unavailable. Your connection is saved; try refresh again shortly.")
        return {"status":"connected"}

    @app.post("/api/connections/{connection_id}/remove")
    async def remove_connection(connection_id: str, request: Request) -> dict[str, bool]:
        check_csrf(request)
        with store.connect() as con: con.execute("DELETE FROM connections WHERE id=?", (connection_id,))
        store.audit("dashboard", "connection_removed")
        return {"removed": True}

    def start_connection(connection_id: str | None = None) -> dict[str, str]:
        state = secrets.token_urlsafe(32)
        keychain = Keychain()
        if (keychain.get("truelayer-client-id") or "").startswith("sandbox-"):
            raise HTTPException(409, "live TrueLayer credentials required; run openbanking-mcp-configure with your live Console credentials")
        client = truelayer_client(keychain)
        callback_uri=keychain.get("truelayer-redirect-uri") or "http://127.0.0.1:3847/oauth/callback"
        connection_id = connection_id or "v1-"+secrets.token_urlsafe(12)
        store.create_state(state, (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(), connection_id)
        return {"authorization_url": client.v1_auth_link(callback_uri, state)}

    @app.post("/api/connect")
    async def connect(request: Request) -> dict[str, str]:
        check_csrf(request)
        store.audit("dashboard", "connection_started")
        return start_connection()

    @app.post("/api/connections/{connection_id}/reconnect")
    async def reconnect(connection_id: str, request: Request) -> dict[str, str]:
        check_csrf(request)
        if not any(connection["id"] == connection_id for connection in store.connections()):
            raise HTTPException(404, "connection not found")
        store.set_connection_status(connection_id, "reconnecting")
        store.audit("dashboard", "connection_reconnect_started")
        return start_connection(connection_id)

    @app.get("/oauth/callback")
    async def callback(state: str, code: Optional[str] = None) -> Response:
        connection_id=store.consume_state(state)
        if not connection_id: raise HTTPException(400, "invalid or expired connection state")
        if not code: raise HTTPException(400,"missing authorization code")
        keychain=Keychain(); client=truelayer_client(keychain)
        token=client.exchange_code(code,keychain.get("truelayer-redirect-uri") or "http://127.0.0.1:3847/oauth/callback")
        store.save_connection(connection_id,"Bank connection","connected",token,{})
        from .sync import sync_connection
        try:
            sync_connection(store, client, connection_id)
        except (ProviderUnavailable, ReauthorizationRequired):
            pass
        store.audit("dashboard", "connection_callback")
        return RedirectResponse("/", status_code=303)

    return app


def run_mcp_server() -> None:
    store = default_store()
    ensure_dashboard()
    for line in sys.stdin:
        try:
            request = json.loads(line); method, request_id = request.get("method"), request.get("id")
            if method == "notifications/initialized": continue
            if method == "initialize": result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "openbankingmcp", "version": "0.2.0"}}
            elif method == "tools/list": result = {"tools": build_tools_list()}
            elif method == "tools/call":
                try:
                    output=call_tool(store, request["params"]["name"], request["params"].get("arguments", {}))
                    result = {"content": [{"type": "text", "text": json.dumps(output)}]}
                except McpConnectionError as error:
                    result = {"isError": True, "content": [{"type": "text", "text": str(error)}]}
            else: raise ValueError("method not found")
            print(json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result}), flush=True)
        except Exception as error:
            print(json.dumps({"jsonrpc": "2.0", "id": request.get("id") if 'request' in locals() else None, "error": {"code": -32602, "message": str(error)}}), flush=True)


def start() -> None:
    try:
        store=default_store()
    except KeychainUnavailable:
        raise SystemExit(
            "OpenBankingMCP could not access macOS Keychain. Unlock your login Keychain, then run openbanking-mcp-launchd install."
        ) from None
    from .scheduler import DailyScheduler
    from .sync import sync_connection
    def refresh():
        keychain=Keychain(); client=truelayer_client(keychain)
        for connection in store.connections():
            if connection["status"] == "connected":
                try: sync_connection(store,client,connection["id"])
                except Exception: pass
        from .retention import enforce
        enforce(store)
    scheduler=DailyScheduler(refresh); scheduler.start()
    try: uvicorn.run(create_app(store), host="127.0.0.1", port=3847)
    finally: scheduler.stop()


run_rest_api_server = start
