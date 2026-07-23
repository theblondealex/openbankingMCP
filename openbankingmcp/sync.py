from __future__ import annotations
import hashlib
from .reporting import category
from .security import masked_identifier
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from .truelayer import EndpointNotSupported, ReauthorizationRequired, ProviderUnavailable

REQUIRED_DATA_SCOPES={"balance","transactions","offline_access"}
ACCOUNT_DATA_SCOPES={"accounts","cards"}


class ScopeUpdateRequired(Exception):
    pass


def sync_accounts(store, client, connection_id):
    try: items=client.accounts(connection_id)
    except ReauthorizationRequired:
        store.set_connection_status(connection_id, "reauthorization_required")
        raise
    for item in items:
        identifiers=item.get("account_identifiers",[])
        last=next((str(x.get("account_number") or x.get("iban") or "") for x in identifiers),"")
        store.upsert_account({"id":item["id"],"connection_id":connection_id,"alias":item.get("display_name") or item.get("provider",{}).get("display_name") or "Connected account","masked_identifier":masked_identifier(last),"account_type":item.get("type"),"currency":item.get("currency","GBP")})
    return len(items)

def normalise_transaction(account_id, item, *, status="booked", is_card=False):
    transaction_id=item.get("id") or item.get("normalised_provider_transaction_id") or item.get("provider_transaction_id") or item.get("transaction_id")
    if "amount_in_minor" in item:
        amount=item["amount_in_minor"]
        if not isinstance(amount,int): raise ValueError("amount_in_minor must be an integer")
    elif "amount" in item:
        amount=int((Decimal(str(item["amount"]))*100).quantize(Decimal("1"),rounding=ROUND_HALF_UP))
    else: raise ValueError("provider transaction has no amount")
    if is_card:
        transaction_type=str(item.get("transaction_type") or "").upper()
        if transaction_type == "DEBIT": amount = -abs(amount)
        elif transaction_type == "CREDIT": amount = abs(amount)
        else: amount = -amount
    merchant=item.get("merchant_name") or item.get("merchant") or item.get("description")
    booked_on=(item.get("timestamp") or item.get("booking_date") or item.get("date"))[:10]
    if not transaction_id:
        identity="|".join((account_id,booked_on,str(amount),item.get("currency","GBP"),str(merchant or ""),str(item.get("description") or "")))
        transaction_id=hashlib.sha256(identity.encode()).hexdigest()
    return {"id":transaction_id,"account_id":account_id,"booked_on":booked_on,"amount_minor":amount,"currency":item.get("currency","GBP"),"merchant":merchant,"reference":item.get("transaction_reference") or item.get("description"),"category":category(merchant),"status":status,"raw_payload":item}

def normalise_balance(item, currency):
    if "amount_in_minor" in item: return item["amount_in_minor"]
    value=item.get("current",item.get("available",item.get("balance")))
    if value is None: raise ValueError("provider balance has no amount")
    return int((Decimal(str(value))*100).quantize(Decimal("1"),rounding=ROUND_HALF_UP))


def provider_today():
    return datetime.now(timezone.utc).date()

def sync_connection(store, client, connection_id):
    """Sync provider data if the supplied client supports the documented data methods."""
    try:
        credentials=store.connection_credentials(connection_id)
        if credentials.get("refresh_token"):
            credentials=client.refresh(credentials["refresh_token"])
            store.save_connection(connection_id,"truelayer-data-v1","connected",credentials,{})
        access_token=credentials["access_token"]
        if hasattr(client,"connection_metadata"):
            try: metadata=client.connection_metadata(access_token)
            except EndpointNotSupported: metadata={}
            provider=metadata.get("provider",{})
            if provider.get("display_name"): store.set_connection_provider(connection_id,provider["display_name"])
            scopes=set(metadata.get("scopes") or [])
            if scopes and (not REQUIRED_DATA_SCOPES.issubset(scopes) or not ACCOUNT_DATA_SCOPES.intersection(scopes)):
                store.set_connection_status(connection_id,"scope_update_required")
                raise ScopeUpdateRequired()
        if hasattr(client,"v1_accounts"):
            resources, provider_errors = [], []
            for resource, fetch in (("accounts", client.v1_accounts), ("cards", getattr(client, "v1_cards", lambda _token: []))):
                try:
                    resources.extend((resource, item) for item in fetch(access_token))
                except EndpointNotSupported:
                    continue
                except ProviderUnavailable as error:
                    provider_errors.append(error)
            if not resources and provider_errors:
                raise provider_errors[0]
            today=provider_today()
            since=(today-timedelta(days=89)).isoformat()
            completed_resources = 0
            for resource, item in resources:
                try:
                    provider=item.get("provider", {})
                    provider_name=provider.get("display_name") if isinstance(provider,dict) else None
                    provider_id=provider.get("provider_id") if isinstance(provider,dict) else provider
                    if provider_name or provider_id:
                        provider_label=str(provider_id)
                        if provider_label.startswith("ob-"): provider_label=provider_label[3:]
                        store.set_connection_provider(connection_id, provider_name or provider_label.replace("-", " ").title())
                    provider_account_id=item["account_id"]
                    account_id=provider_account_id if resource == "accounts" else "card:"+provider_account_id
                    store.upsert_account({"id":account_id,"connection_id":connection_id,"alias":item.get("display_name","Connected card"),"masked_identifier":masked_identifier(str(item.get("partial_card_number") or "")),"account_type":item.get("account_type") or resource.rstrip("s"),"currency":item.get("currency","GBP")})
                    if resource == "cards":
                        balance=client.card_balance(access_token,provider_account_id)
                        transactions=client.card_transactions(access_token,provider_account_id,since,today.isoformat())
                        pending_fetch=getattr(client,"card_pending_transactions",None)
                    else:
                        balance=client.balance(access_token,provider_account_id)
                        transactions=client.transactions(access_token,provider_account_id,since,today.isoformat())
                        pending_fetch=getattr(client,"pending_transactions",None)
                    store.add_balance(account_id,normalise_balance(balance,item.get("currency","GBP")),balance.get("currency",item.get("currency","GBP")))
                    booked_items=[]
                    for transaction in transactions:
                        normalised=normalise_transaction(account_id,transaction,is_card=resource == "cards")
                        if resource == "cards": normalised["id"] = account_id+":"+normalised["id"]
                        booked_items.append(normalised)
                    store.replace_booked_transactions(account_id,since,today.isoformat(),booked_items)
                    if pending_fetch:
                        try:
                            pending_transactions=pending_fetch(access_token,provider_account_id)
                        except EndpointNotSupported:
                            pending_transactions=None
                        if pending_transactions is not None:
                            pending_items=[]
                            for transaction in pending_transactions:
                                normalised=normalise_transaction(account_id,transaction,status="pending",is_card=resource == "cards")
                                normalised["id"]=account_id+":pending:"+normalised["id"]
                                pending_items.append(normalised)
                            store.replace_pending_transactions(account_id,pending_items)
                    completed_resources += 1
                except ProviderUnavailable as error:
                    provider_errors.append(error)
                except EndpointNotSupported:
                    continue
            if not completed_resources and provider_errors:
                raise provider_errors[0]
        else: sync_accounts(store,client,connection_id)
        if not hasattr(client,"v1_accounts"):
            for account in store.accounts(connection_id):
                if hasattr(client,"balance"):
                    balance=client.balance(access_token if 'access_token' in locals() else connection_id,account["id"])
                    store.add_balance(account["id"],normalise_balance(balance,account["currency"]),balance.get("currency",account["currency"]))
                if hasattr(client,"transactions"):
                    today=provider_today()
                    since=(today-timedelta(days=89)).isoformat()
                    for item in client.transactions(access_token if 'access_token' in locals() else connection_id,account["id"],since,today.isoformat()): store.upsert_transaction(normalise_transaction(account["id"],item))
        store.set_connection_status(connection_id,"connected"); store.audit("service","connection_synced")
    except ReauthorizationRequired:
        store.set_connection_status(connection_id,"reauthorization_required"); raise
    except ProviderUnavailable:
        store.set_connection_status(connection_id,"sync_delayed"); raise
