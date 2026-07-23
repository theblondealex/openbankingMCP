"""Interactive, local-only TrueLayer credential setup for macOS."""

from __future__ import annotations

import getpass
from pathlib import Path

import httpx

from .client_install import offer_install
from .security import Keychain, KeychainUnavailable
from .truelayer import ProviderUnavailable, ReauthorizationRequired, TrueLayer


DEFAULT_REDIRECT_URI = "http://127.0.0.1:3847/oauth/callback"


def validate_live_client_id(client_id: str) -> None:
    if client_id.startswith("sandbox-"):
        raise SystemExit("OpenBankingMCP is live-only. Enter your separate live TrueLayer client ID.")


def verify_live_credentials(client_id: str, client_secret: str) -> None:
    """Check credentials before storing them, without printing either value."""
    try:
        TrueLayer(client_id, client_secret).token()
    except ProviderUnavailable:
        raise SystemExit("TrueLayer is temporarily unavailable. Wait a few minutes, then run this setup command again.") from None
    except httpx.RequestError:
        raise SystemExit("Could not reach TrueLayer. Check your internet connection, then run this setup command again.") from None
    except ReauthorizationRequired:
        raise SystemExit(
            "TrueLayer did not accept these live credentials. Check that the app is switched to Live, "
            "Data API is enabled, and both values came from the same live app; then run this setup command again."
        ) from None
    except Exception:
        raise SystemExit("TrueLayer could not verify these credentials. Wait a few minutes, then run this setup command again.") from None


def main() -> None:
    print("OpenBankingMCP TrueLayer live setup (stores credentials in macOS Keychain).")
    client_id = input("TrueLayer client ID: ").strip()
    client_secret = getpass.getpass("TrueLayer client secret: ").strip()
    if not client_id or not client_secret:
        raise SystemExit("Client ID and secret are required.")
    validate_live_client_id(client_id)
    verify_live_credentials(client_id, client_secret)
    keychain = Keychain()
    try:
        keychain.set("truelayer-client-id", client_id)
        keychain.set("truelayer-client-secret", client_secret)
        keychain.set("truelayer-redirect-uri", DEFAULT_REDIRECT_URI)
    except KeychainUnavailable:
        raise SystemExit(
            "macOS Keychain could not save the credentials. Unlock your login Keychain, then run this setup command again."
        ) from None
    print("Saved live credentials to macOS Keychain. The local dashboard is http://127.0.0.1:3847.")
    installed = offer_install(Path(__file__).resolve().parents[1], Path.home())
    if installed:
        print("MCP configured for " + ", ".join(installed) + ". Restart the client to load it.")


if __name__ == "__main__":
    main()
