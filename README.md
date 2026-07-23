# OpenBankingMCP

Private, read-only financial context for your AI on macOS. Connect banks through
your own TrueLayer Console app, keep an encrypted local cache, and ask an MCP
client questions such as “what did I spend this week?” or “why did my card
balance increase?”.

OpenBankingMCP is not financial advice, a payment service, or a way to make
transfers. It exposes no payment, payout, mandate, VRP, or write-capable tools.

## Quick start

This takes about ten minutes, plus any time TrueLayer needs to enable live Data
API access for your Console account.

1. Create the live TrueLayer app below and keep its live client ID and secret
   ready.
2. Download and run the macOS installer:

   ```sh
   export OPENBANKINGMCP_VERSION=v0.2.0
   curl -fsSL "https://raw.githubusercontent.com/theblondealex/openbankingMCP/${OPENBANKINGMCP_VERSION}/scripts/install.sh" -o /tmp/openbankingmcp-install.sh
   bash /tmp/openbankingmcp-install.sh
   ```

3. Enter the live client ID and secret when prompted. They are saved in macOS
   Keychain, not in a project file.
4. Answer `y` when the installer offers to add OpenBankingMCP to detected
   Codex, Claude Desktop, or Claude Code installations.
5. Open [http://127.0.0.1:3847](http://127.0.0.1:3847), select a bank, and
   complete TrueLayer’s hosted authorisation.

The installer downloads the chosen release tag, creates
`~/Library/Application Support/OpenBankingMCP`, installs an isolated Python
environment, and registers a per-user `launchd` service. The dashboard starts
at login and remains at `127.0.0.1:3847` only. Set `OPENBANKINGMCP_VERSION` to
a newer published release when upgrading.

It stops before saving credentials if the live TrueLayer app rejects them, and
ends by checking that the dashboard and credentials are ready. It never deletes
an existing or incomplete installation automatically.

### Prerequisites

- macOS
- Python 3.9 or later
- Git (install macOS Command Line Tools with `xcode-select --install` if it is
  missing)
- A TrueLayer Console account with live Data API access

The installer explains the exact missing prerequisite if one is not available.

## If setup does not work

Run this one command first:

```sh
~/Library/Application\ Support/OpenBankingMCP/venv/bin/openbanking-mcp-doctor
```

It checks the local dashboard, installed dashboard files, Python version, and
live TrueLayer credentials without printing any secrets. Its message tells you
the next repair step. The common fixes are:

- **Python or Git missing:** install the exact prerequisite named by the
  installer, then run the installer again.
- **TrueLayer rejects credentials:** ensure Console is on **Live**, Data API is
  enabled, and the ID and secret are from that same live app. Then run
  `openbanking-mcp-configure` from the command above's `venv/bin` folder.
- **Dashboard is not running:** run
  `~/Library/Application\ Support/OpenBankingMCP/venv/bin/openbanking-mcp-launchd install`.
- **A bank is delayed or no card data appears:** use **Refresh** in the local
  dashboard. If the dashboard says access needs updating, use **Update access**
  and reconnect with the `cards` permission enabled.
- **Installer stopped part way through:** it leaves the incomplete folder in
  place. Remove only `~/Library/Application Support/OpenBankingMCP`, then run
  the installer again.

## Create the TrueLayer live app

Open [TrueLayer Console](https://console.truelayer.com/), create an application,
and switch Console from **Sandbox** to **Live**. Sandbox credentials are
intentionally rejected by OpenBankingMCP.

In the live application:

1. Open **Products** and make sure Data API is enabled for the app. Live access,
   supported providers, and any onboarding requirements are controlled by your
   own TrueLayer account.
2. Open **Settings → Application settings → Redirect URIs** and add this exact
   local callback:

   ```text
   http://127.0.0.1:3847/oauth/callback
   ```

3. Open **Data API → Auth Link Builder**. Select the providers you want to make
   available, choose a personal-finance-management data-use description, and
   enable these product permissions:

   ```text
   accounts cards balance transactions offline_access
   ```

   `cards` is required for credit-card balances and transactions. `offline_access`
   lets the local service refresh an existing consent; it does not make any
   payment possible.
4. Copy the **live** client ID and create/copy a live client secret from
   **Settings**. Do not paste either into a shell command, commit them, or send
   them to an agent.

TrueLayer’s Console manages client credentials and redirect URIs per app, and
its Data API UI controls the providers and permissions exposed in the hosted
authorisation flow. [Application settings](https://docs.truelayer.com/docs/application-settings), [Data API in Console](https://docs.truelayer.com/docs/data-api-in-console)

## Connect your banks

1. Open [http://127.0.0.1:3847](http://127.0.0.1:3847).
2. Choose **Choose a live bank with TrueLayer**.
3. Select a bank in TrueLayer’s hosted selector, approve the accounts or cards
   you want to share, and return to the dashboard.

The dashboard syncs account and card feeds immediately. It shows a clear
provider-delay message when TrueLayer returns a temporary 429/5xx response.
Use **Refresh** to retry. If consent expires or is revoked, use **Reconnect**;
the existing connection is updated rather than duplicated.

## Use it with your AI

After restarting the client you opted into during setup, simply say:

> Use OpenBankingMCP to review my spending this week.

If no connection exists, the MCP server fails closed with an
`authorization_required` response that points the agent to the local dashboard.
It cannot open a bank connection or make a payment itself.

Useful prompts:

- “What did I spend in the last seven days?”
- “Show my Barclays card transactions from 1 July to today.”
- “Compare this month’s spending with last month.”
- “What recurring subscriptions can you find?”
- “Why has my Amex balance increased?”

The service provides only read-only tools for connections, accounts, balances,
transactions, search, recurring spend, category summaries, comparisons, largest
transactions, and balance-change explanations. Direct transaction queries default
to seven days, cap results at 100, and reject ranges over 90 days.

### Manual MCP configuration

If no client is detected, configure a stdio server with the following values,
substituting your installation directory if you used a custom one:

```json
{
  "command": "/Users/YOU/Library/Application Support/OpenBankingMCP/venv/bin/python",
  "args": ["-m", "openbankingmcp"],
  "cwd": "/Users/YOU/Library/Application Support/OpenBankingMCP/app"
}
```

For Codex, Claude Desktop, and Claude Code the interactive setup detects the
standard local config file and offers to add this entry without replacing any
existing MCP servers.

## Security and data handling

### Your financial data stays on your Mac

- The dashboard binds only to `127.0.0.1:3847` and `localhost:3847`; do not
  proxy or expose it on a network.
- The TrueLayer client secret and encryption key stay in macOS Keychain.
- The persistent local cache is authenticated-encrypted and owner-only. Legacy
  plaintext cache files are removed only after a successful encrypted migration.
- MCP output uses account aliases and masked identifiers, and redacts long
  references by default. Audit events record tool names and dashboard mutations,
  not their sensitive arguments or results.

OpenBankingMCP has no cloud backend and does not upload a separate copy of your
bank data. The important exception is your chosen AI client: when you ask Codex,
Claude, Cursor, or another client to analyse a tool result, that client may send
the result to its model provider. Review that client's privacy settings and data
policy before using it with financial data.

### Read-only means it cannot move money

The TrueLayer authorisation asks only for `accounts`, `cards`, `balance`,
`transactions`, and `offline_access`. These are data-access scopes; it never
requests payment, transfer, payout, VRP, mandate, or payment-link authority.

The MCP server also exposes only read-only reporting tools. It has no payment
endpoint, no write-capable tool, no arbitrary HTTP tool, and no way for an AI
prompt or MCP call to initiate a bank transfer. You can remove access at any
time in the dashboard or through your bank/TrueLayer consent controls.

See [the threat model](docs/threat-model.md) and [SECURITY.md](SECURITY.md).

## Operations

The local dashboard service is managed by `launchd`:

```sh
~/Library/Application\ Support/OpenBankingMCP/venv/bin/openbanking-mcp-launchd install
~/Library/Application\ Support/OpenBankingMCP/venv/bin/openbanking-mcp-launchd uninstall
~/Library/Application\ Support/OpenBankingMCP/venv/bin/openbanking-mcp-doctor
```

Uninstalling the service stops the dashboard but deliberately retains local data.
Remove `~/Library/Application Support/OpenBankingMCP` and
`~/.local/share/openbankingmcp` yourself only if you want to remove the app and
its encrypted cache.

## Development

```sh
python3 -m pytest -q
cd web && yarn build
openbanking-dashboard
```

## Provider notes

OpenBankingMCP uses TrueLayer’s hosted Data API v1 authorisation and retrieval
flow for accounts and credit cards. Data API v3 compatibility remains limited to
documented connection-management endpoints. Provider coverage, freshness, and
live availability are determined by TrueLayer and the bank; the app never
invents payment or transfer APIs.

## License and attribution

This project is a fork of `tkom04/openbankingMCP` and is distributed under the
[MIT License](LICENSE). Upstream attribution is retained here and in project
metadata.
