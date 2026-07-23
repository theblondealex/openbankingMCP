# OpenBankingMCP

Private, read-only financial context for your AI on macOS, Windows, and desktop
Linux. Connect banks through your own TrueLayer Console app, keep an encrypted
local cache, and ask an MCP client questions such as “what did I spend this
week?” or “why did my card balance increase?”.

OpenBankingMCP is not financial advice, a payment service, or a way to make
transfers. It exposes no payment, payout, mandate, VRP, or write-capable tools.

## Quick start

Setup takes about ten minutes, plus any time TrueLayer needs to enable live Data
API access for your Console account.

### 1. Create a live TrueLayer app

Open [TrueLayer Console](https://console.truelayer.com/), create an application,
and switch Console from **Sandbox** to **Live**. Sandbox credentials are
intentionally rejected.

In the live application:

1. Open **Products** and enable Data API. Live access, supported providers, and
   any onboarding requirements are controlled by your TrueLayer account.
2. Open **Settings → Application settings → Redirect URIs** and add:

   ```text
   http://127.0.0.1:3847/oauth/callback
   ```

3. Open **Data API → Auth Link Builder**, select the providers you need, choose
   a personal-finance-management data-use description, and enable:

   ```text
   accounts cards balance transactions offline_access
   ```

   `cards` is needed for credit-card balances and transactions.
   `offline_access` lets the local service refresh an existing consent; neither
   permission allows payments.
4. Copy the **live** client ID and create a live client secret. Do not paste
   either into a shell command, commit them, or send them to an agent.

Official references: [Application settings](https://docs.truelayer.com/docs/application-settings),
[Data API in Console](https://docs.truelayer.com/docs/data-api-in-console).

### 2. Run the installer for your computer

The installer detects macOS or Linux automatically. Windows uses the equivalent
PowerShell installer because Windows does not include a Unix shell.

**macOS or Linux**

```sh
export OPENBANKINGMCP_VERSION=v0.3.0
curl -fsSL "https://raw.githubusercontent.com/theblondealex/openbankingMCP/${OPENBANKINGMCP_VERSION}/scripts/install.sh" -o /tmp/openbankingmcp-install.sh
sh /tmp/openbankingmcp-install.sh
```

**Windows PowerShell**

```powershell
$env:OPENBANKINGMCP_VERSION = "v0.3.0"
Invoke-WebRequest "https://raw.githubusercontent.com/theblondealex/openbankingMCP/$env:OPENBANKINGMCP_VERSION/scripts/install.ps1" -OutFile "$env:TEMP\openbankingmcp-install.ps1"
Unblock-File "$env:TEMP\openbankingmcp-install.ps1"
& "$env:TEMP\openbankingmcp-install.ps1"
```

The installer:

1. checks the operating system, Python, Git, and required desktop services;
2. installs the selected release in an isolated environment;
3. verifies the live TrueLayer credentials before saving them securely;
4. detects Codex, Claude Desktop, and Claude Code and offers to configure the
   MCP without replacing existing servers;
5. starts the loopback dashboard now and at every login; and
6. runs a health check and gives a specific repair instruction if anything is
   not ready.

Credentials are stored in macOS Keychain, Windows Credential Manager, or a
Linux Secret Service provider. They are never written to the repository or an
`.env` file.

### 3. Connect a bank

Open [http://127.0.0.1:3847](http://127.0.0.1:3847), choose **Choose a live bank
with TrueLayer**, approve the accounts or cards to share, and return to the
dashboard.

The dashboard syncs account and card feeds immediately, including both settled
and pending transactions. MCP results label each transaction as `booked` or
`pending`, and summaries report the pending portion separately so recent card
spending is visible without implying it has settled. The dashboard shows a
provider delay when TrueLayer returns a temporary response; use **Refresh** to
retry. If consent expires or is revoked, use **Reconnect**. If a connection
predates the `cards` permission, use **Update access**.

### 4. Ask your AI

Restart the client you enabled during setup, then say:

> Use OpenBankingMCP to review my spending this week.

If no bank is connected, the MCP fails closed with an
`authorization_required` response that points the agent to the local dashboard.
It cannot connect a bank or make a payment itself.

Other useful prompts:

- “Show my Barclays card transactions from 1 July to today.”
- “Compare this month’s spending with last month.”
- “What recurring subscriptions can you find?”
- “Why has my Amex balance increased?”

## Remote setup for an always-on machine

Install and configure OpenBankingMCP on the machine where your agents run. You
can complete bank authorisation in a browser on your Mac or PC without moving
the encrypted database or exposing the dashboard to a network.

1. Install OpenBankingMCP on the remote machine and make sure its dashboard
   service is running.
2. Make sure port `3847` is free on the computer with your browser. Temporarily
   stop a local OpenBankingMCP service if necessary.
3. From the computer with your browser, create a localhost SSH tunnel:

   ```sh
   ssh -N -L 3847:127.0.0.1:3847 YOUR_USER@YOUR_REMOTE_MACHINE
   ```

   If both machines use Tailscale, use the remote machine's Tailscale hostname
   or IP as `YOUR_REMOTE_MACHINE`. The SSH tunnel still keeps the dashboard
   bound to loopback on both ends.
4. Open [http://127.0.0.1:3847](http://127.0.0.1:3847) locally and complete the
   TrueLayer and bank screens. The OAuth callback returns through the same
   tunnel to OpenBankingMCP on the remote machine.
5. Close the SSH tunnel when setup is complete. The remote service keeps
   syncing, and agents running on that machine can use its local stdio MCP.

Repeat the tunnel when a bank asks for reauthorisation. Do not expose port
`3847` with Tailscale Funnel, a public reverse proxy, router port forwarding, or
a public tunnel. OpenBankingMCP's Host allowlist and loopback binding are
deliberate security controls. See
[Tailscale's SSH documentation](https://tailscale.com/docs/reference/ssh-over-tailscale)
for private SSH access over a tailnet.

## Supported systems and prerequisites

| System | Supported setup | Secure credential store | Starts at login with |
| --- | --- | --- | --- |
| macOS | Current supported macOS releases | macOS Keychain | `launchd` |
| Windows | Windows 10 or 11 | Windows Credential Manager | Task Scheduler |
| Linux | Desktop Linux with `systemd --user` | GNOME Keyring, KWallet, or another Secret Service provider | systemd user service |

All systems require Python 3.9 or newer, Git, internet access during setup, and
a TrueLayer Console account with live Data API access. The installer names the
missing prerequisite and stops without deleting existing data.

On Linux, install the normal desktop keyring package for your distribution if
one is not already running. OpenBankingMCP deliberately refuses a plaintext
fallback on headless systems or desktops without an unlocked Secret Service.
The underlying cross-platform integration is provided by
[Python keyring](https://keyring.readthedocs.io/en/stable/).

## If setup does not work

Run the health check for your system:

**macOS**

```sh
~/Library/Application\ Support/OpenBankingMCP/venv/bin/openbanking-mcp-doctor
```

**Linux**

```sh
~/.local/share/openbankingmcp/venv/bin/openbanking-mcp-doctor
```

**Windows PowerShell**

```powershell
& "$env:LOCALAPPDATA\OpenBankingMCP\venv\Scripts\openbanking-mcp-doctor.exe"
```

It checks Python, dashboard files, the local service, the operating-system
credential store, and live TrueLayer credentials without printing secrets.
Common repairs:

- **Python or Git missing:** install the prerequisite named by the installer,
  then run the installer again.
- **Secure credential store unavailable:** unlock macOS Keychain or sign back
  in to Windows. On Linux, sign in to the desktop session and start/unlock GNOME
  Keyring, KWallet, or another Secret Service provider.
- **TrueLayer rejects credentials:** ensure Console is on **Live**, Data API is
  enabled, and both values came from the same live app; then run
  `openbanking-mcp-configure` from the installation's `venv/bin` or
  `venv\Scripts` directory.
- **Dashboard is not running:** run `openbanking-mcp-service install` from that
  same directory.
- **A bank is delayed or card data is missing:** use **Refresh**. If requested,
  use **Update access** and reconnect with `cards` enabled.
- **Installer stopped part way through:** it leaves the incomplete folder in
  place and tells you its exact path. Remove only that folder, then run the
  installer again.

## Manual MCP configuration

Interactive setup normally detects and configures Codex, Claude Desktop, and
Claude Code. If detection misses a client, add a stdio MCP server using the
installed Python executable and app directory:

| System | Command | Working directory |
| --- | --- | --- |
| macOS | `~/Library/Application Support/OpenBankingMCP/venv/bin/python` | `~/Library/Application Support/OpenBankingMCP/app` |
| Linux | `~/.local/share/openbankingmcp/venv/bin/python` | `~/.local/share/openbankingmcp/app` |
| Windows | `%LOCALAPPDATA%\OpenBankingMCP\venv\Scripts\python.exe` | `%LOCALAPPDATA%\OpenBankingMCP\app` |

Use `["-m", "openbankingmcp"]` as the arguments. For example:

```json
{
  "command": "/absolute/path/to/venv/python",
  "args": ["-m", "openbankingmcp"],
  "cwd": "/absolute/path/to/OpenBankingMCP/app"
}
```

## Security and data handling

### Your financial data stays on your device

- The dashboard binds only to `127.0.0.1:3847` and `localhost:3847`; do not
  expose it through a proxy or network.
- The TrueLayer client secret and database encryption key stay in the
  operating system's secure credential store.
- The local cache is authenticated-encrypted inside the current user's private
  application-data directory. SQLite runs in memory, and only its encrypted
  database image is persisted. POSIX systems additionally enforce owner-only
  file permissions.
- MCP output uses account aliases and masked identifiers and redacts long
  references by default. Audit events record tool names and dashboard
  mutations, not sensitive arguments or results.

OpenBankingMCP has no cloud backend and does not upload a separate copy of your
bank data. Your chosen AI client may send tool results to its own model
provider. Review that client's privacy settings and data policy before using it
with financial data.

### Read-only means it cannot move money

TrueLayer authorisation asks only for `accounts`, `cards`, `balance`,
`transactions`, and `offline_access`. These are data-access scopes. It never
requests payment, transfer, payout, VRP, mandate, or payment-link authority.

The MCP server also exposes only read-only reporting tools. It has no payment
endpoint, no write-capable tool, no arbitrary HTTP tool, and no way for an AI
prompt or MCP call to initiate a bank transfer. You can remove access at any
time in the dashboard or through your bank/TrueLayer consent controls.

See [the threat model](docs/threat-model.md) and [SECURITY.md](SECURITY.md).
The complete reviewed TrueLayer surface and the decision for every endpoint is
recorded in [TrueLayer API endpoint coverage](docs/truelayer-api-coverage.md).

## Operations

Use `openbanking-mcp-service install` to start the dashboard now and at login,
or `openbanking-mcp-service uninstall` to stop and unregister it. Run these from
the installed `venv/bin` directory on macOS/Linux or `venv\Scripts` on Windows.

On macOS, the installed LaunchAgent uses both `RunAtLoad` and `KeepAlive`. It
starts after the user logs in, continues running while the screen is locked,
and is relaunched by `launchd` if it exits unexpectedly. After a complete
restart, one user login is still required: a per-user LaunchAgent and that
user's login Keychain are unavailable at the login screen. With FileVault, the
startup disk itself also remains locked until a user authenticates. Running as
a pre-login root LaunchDaemon would bypass the user-security model and is
intentionally unsupported.

Unregistering the service deliberately retains local encrypted data. The
installer uses these locations:

| System | Application | Encrypted data |
| --- | --- | --- |
| macOS | `~/Library/Application Support/OpenBankingMCP` | `~/.local/share/openbankingmcp` |
| Linux | `${XDG_DATA_HOME:-~/.local/share}/openbankingmcp` | same directory |
| Windows | `%LOCALAPPDATA%\OpenBankingMCP` | `%LOCALAPPDATA%\OpenBankingMCP\data` |

Delete only the applicable locations if you intentionally want to remove both
the app and its encrypted cache.

## Development

```sh
python3 -m pytest -q
cd web && yarn build
openbanking-dashboard
```

## Provider notes

OpenBankingMCP uses TrueLayer's hosted Data API v1 authorisation and retrieval
flow for accounts and credit cards. Data API v3 compatibility remains limited
to documented connection-management endpoints. Provider coverage, freshness,
and live availability are determined by TrueLayer and the bank.

## License and attribution

This project is a fork of `tkom04/openbankingMCP` and is distributed under the
[MIT License](LICENSE). Upstream attribution is retained here and in project
metadata.
