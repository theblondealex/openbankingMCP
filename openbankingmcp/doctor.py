"""Check a local OpenBankingMCP installation without exposing credentials."""

from __future__ import annotations

import argparse
import platform
import sys
import time
from pathlib import Path
from urllib.request import urlopen

import httpx

from . import launchd
from .security import SecretStore, SecretStoreUnavailable, secret_store_help, system_secret_store
from .truelayer import ProviderUnavailable, ReauthorizationRequired, TrueLayer


DASHBOARD_URL = "http://127.0.0.1:3847/"


def report(ok: bool, success: str, failure: str) -> bool:
    print(("✓ " + success) if ok else ("✗ " + failure))
    return ok


def dashboard_is_running(attempts: int = 5) -> bool:
    for attempt in range(attempts):
        try:
            with urlopen(DASHBOARD_URL, timeout=2):
                return True
        except Exception:
            if attempt + 1 < attempts:
                time.sleep(0.5)
    return False


def credentials_work(secret_store: SecretStore) -> tuple[bool, str]:
    try:
        client_id = secret_store.get("truelayer-client-id")
        client_secret = secret_store.get("truelayer-client-secret")
    except SecretStoreUnavailable:
        return False, f"The operating system credential store is unavailable. {secret_store_help()}"
    if not client_id or not client_secret:
        return False, "TrueLayer is not configured. Run openbanking-mcp-configure."
    try:
        TrueLayer(client_id, client_secret).token()
    except ProviderUnavailable:
        return False, "TrueLayer is temporarily unavailable. Try openbanking-mcp-doctor again in a few minutes."
    except httpx.RequestError:
        return False, "Could not reach TrueLayer. Check your internet connection, then run openbanking-mcp-doctor again."
    except ReauthorizationRequired:
        return False, "TrueLayer rejected the saved credentials. Re-run openbanking-mcp-configure with your live app values."
    except Exception:
        return False, "TrueLayer could not verify the saved credentials. Try openbanking-mcp-doctor again in a few minutes."
    return True, "Live TrueLayer credentials are configured and accepted."


def main() -> None:
    parser = argparse.ArgumentParser(description="Check a local OpenBankingMCP installation.")
    parser.add_argument("--offline", action="store_true", help="Skip the live TrueLayer credentials check.")
    args = parser.parse_args()

    failures = 0
    failures += not report(
        sys.version_info >= (3, 9),
        f"Python {sys.version_info.major}.{sys.version_info.minor} is supported.",
        "Python 3.9 or newer is required. Install it, then run the installer again.",
    )
    root = Path(__file__).resolve().parents[1]
    failures += not report(
        (root / "web" / "dist" / "index.html").is_file(),
        "Dashboard files are installed.",
        "Dashboard files are missing. Re-run the installer from a published release.",
    )
    failures += not report(
        dashboard_is_running(),
        "Local dashboard is running at http://127.0.0.1:3847.",
        "Local dashboard is not running. Run openbanking-mcp-service install, then run this check again.",
    )
    if platform.system() == "Darwin":
        failures += not report(
            launchd.is_resilient(),
            "macOS login service starts at login and restarts the dashboard if it exits.",
            "macOS login service is missing or outdated. Run openbanking-mcp-service install, then run this check again.",
        )
    try:
        secret_store = system_secret_store()
    except SecretStoreUnavailable:
        secret_store = None
        message = f"The operating system credential store is unavailable. {secret_store_help()}"
        failures += not report(False, message, message)
    else:
        failures += not report(
            True,
            f"{secret_store.display_name} is available.",
            "The operating system credential store is unavailable.",
        )

    if args.offline:
        print("• Skipped the live TrueLayer credentials check (--offline).")
    elif secret_store is not None:
        ok, message = credentials_work(secret_store)
        failures += not report(ok, message, message)

    if failures:
        raise SystemExit(1)
    print("\nOpenBankingMCP is ready. Open http://127.0.0.1:3847 to manage bank connections.")


if __name__ == "__main__":
    main()
