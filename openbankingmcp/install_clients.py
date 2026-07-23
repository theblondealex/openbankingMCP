"""Install the stdio MCP entry without touching TrueLayer credentials."""
from pathlib import Path
from .client_install import offer_install

def main() -> None:
    installed=offer_install(Path(__file__).resolve().parents[1],Path.home())
    print("Configured: " + ", ".join(installed) if installed else "No client configuration changed.")
