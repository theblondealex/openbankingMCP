# Security policy

OpenBankingMCP is local-only and read-only. Do not report secrets, account data,
or tokens in public issues. Use
[GitHub private vulnerability reporting](https://github.com/theblondealex/openbankingMCP/security/advisories/new)
and include steps to reproduce using synthetic data only.

The dashboard binds exclusively to `127.0.0.1`; it is not designed to be
exposed through a reverse proxy or LAN.
