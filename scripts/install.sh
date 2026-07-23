#!/bin/sh
# Install OpenBankingMCP locally for the current macOS user.
set -eu

REPOSITORY="${OPENBANKINGMCP_REPOSITORY:-https://github.com/theblondealex/openbankingMCP.git}"
RELEASE_VERSION="${OPENBANKINGMCP_VERSION:-v0.2.0}"
INSTALL_ROOT="${OPENBANKINGMCP_INSTALL_DIR:-$HOME/Library/Application Support/OpenBankingMCP}"
APP_DIR="$INSTALL_ROOT/app"
VENV_DIR="$INSTALL_ROOT/venv"

fail() {
  printf '\nInstallation stopped: %s\n' "$1" >&2
  exit 1
}

run_or_fail() {
  message="$1"
  shift
  "$@" || fail "$message"
}

[ "$(uname -s)" = "Darwin" ] || fail "OpenBankingMCP currently supports macOS only."
command -v git >/dev/null 2>&1 || fail "Git is required. Install Xcode Command Line Tools with: xcode-select --install"
command -v python3 >/dev/null 2>&1 || fail "Python 3.9 or newer is required. Install it from https://www.python.org/downloads/macos/ or run: brew install python"
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' || fail "Python 3.9 or newer is required. Install it from https://www.python.org/downloads/macos/ or run: brew install python"

if [ -e "$APP_DIR" ]; then
  if [ -x "$VENV_DIR/bin/openbanking-mcp-configure" ]; then
    fail "OpenBankingMCP is already installed at $INSTALL_ROOT. To update credentials, run: $VENV_DIR/bin/openbanking-mcp-configure. To diagnose it, run: $VENV_DIR/bin/openbanking-mcp-doctor"
  fi
  fail "An incomplete OpenBankingMCP install is already at $INSTALL_ROOT. Nothing was deleted. Remove that one folder, then run this installer again."
fi

run_or_fail "Could not create $INSTALL_ROOT. Check that your macOS user account can write to Library/Application Support." mkdir -p "$INSTALL_ROOT"
run_or_fail "Could not download OpenBankingMCP $RELEASE_VERSION. Check your internet connection and release version, then run the installer again." git clone --depth 1 --branch "$RELEASE_VERSION" "$REPOSITORY" "$APP_DIR"
[ -f "$APP_DIR/web/dist/index.html" ] || fail "OpenBankingMCP $RELEASE_VERSION is missing dashboard assets. Use a published release."

run_or_fail "Could not create OpenBankingMCP's isolated Python environment. Reinstall Python 3.9 or newer, then run the installer again." python3 -m venv "$VENV_DIR"
run_or_fail "Could not update the installer tools. Check your internet connection, then run the installer again." "$VENV_DIR/bin/python" -m pip install --upgrade pip
run_or_fail "Could not install OpenBankingMCP's dependencies. Check your internet connection, then run the installer again." "$VENV_DIR/bin/python" -m pip install --editable "$APP_DIR"
run_or_fail "Could not start the local dashboard service. Run $VENV_DIR/bin/openbanking-mcp-doctor after checking macOS launch services are available." "$VENV_DIR/bin/openbanking-mcp-launchd" install

printf '\nOpenBankingMCP %s is installed and running locally.\n\n' "$RELEASE_VERSION"
printf 'Next, paste your TrueLayer live client ID and secret into the secure setup prompts.\n'
"$VENV_DIR/bin/openbanking-mcp-configure" || fail "TrueLayer setup was not completed. Correct the message above, then run: $VENV_DIR/bin/openbanking-mcp-configure"
"$VENV_DIR/bin/openbanking-mcp-doctor" || fail "Setup completed, but the final health check failed. Run: $VENV_DIR/bin/openbanking-mcp-doctor"

printf '\nSetup complete. Open http://127.0.0.1:3847 to connect a bank.\n'
printf 'The installer is at %s and the local dashboard starts automatically at login.\n' "$INSTALL_ROOT"
