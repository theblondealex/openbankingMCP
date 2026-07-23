# Threat model

The service protects data at rest with an encryption key held in macOS Keychain
and stores the TrueLayer client secret there too. SQLite runs only in process
memory; its complete persisted database dump is authenticated-encrypted at
`openbankingmcp.sqlite3.enc` with restrictive owner-only permissions. A legacy
plaintext SQLite file is removed only after a successful encrypted migration.

The dashboard accepts only `Host: 127.0.0.1:3847` or `localhost:3847`, uses a
per-install session secret, SameSite cookies, CSRF checks, and single-use OAuth
state. MCP is stdio-only and exposes no connection-management or payment tools.

The service is local, but an MCP client may transmit the results it receives to
its own model provider. That behaviour is controlled by the chosen MCP client,
not by OpenBankingMCP; users should review that client’s data policy before
asking it to analyse financial data.

Local malware running as the same user, a compromised MCP client, and an
unlocked macOS login session remain outside this application's protection.

Transactions are retained for 365 days by default. Removing a connection deletes
its accounts, balances, and transactions through SQLite foreign-key cascades.
