from datetime import date, timedelta
DEFAULT_RETENTION_DAYS = 365
def enforce(store, days=DEFAULT_RETENTION_DAYS):
    removed=store.retain_since((date.today()-timedelta(days=days)).isoformat())
    store.audit("service","retention_enforced")
    return removed
