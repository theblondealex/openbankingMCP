"""Deterministic reporting over locally stored transactions."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any


RULES = {"coffee": "dining", "restaurant": "dining", "uber": "transport", "train": "transport", "tesco": "groceries", "sainsbury": "groceries", "netflix": "subscriptions"}

def category(merchant: str | None) -> str:
    text = (merchant or "").lower()
    return next((kind for needle, kind in RULES.items() if needle in text), "uncategorised")

def summarise(items: list[dict[str, Any]]) -> dict[str, Any]:
    spending = [item for item in items if item["amount_minor"] < 0]
    totals: dict[str, int] = defaultdict(int)
    for item in spending: totals[item["category"]] += -item["amount_minor"]
    pending = [item for item in items if item.get("status") == "pending"]
    booked = [item for item in items if item.get("status", "booked") == "booked"]
    return {
        "spending_minor": sum(-item["amount_minor"] for item in spending),
        "income_minor": sum(item["amount_minor"] for item in items if item["amount_minor"] > 0),
        "booked_spending_minor": sum(-item["amount_minor"] for item in booked if item["amount_minor"] < 0),
        "pending_spending_minor": sum(-item["amount_minor"] for item in pending if item["amount_minor"] < 0),
        "pending_transaction_count": len(pending),
        "by_category_minor": dict(sorted(totals.items())),
    }

def recurring(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        if item["amount_minor"] < 0: groups[((item.get("merchant") or "").lower(), abs(item["amount_minor"]))].append(item)
    return [{"merchant": values[0].get("merchant"), "amount_minor": amount, "occurrences": len(values)} for (merchant, amount), values in groups.items() if merchant and len(values) >= 2]
