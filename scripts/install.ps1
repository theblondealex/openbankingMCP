# Install OpenBankingMCP locally for the current Windows user.
$ErrorActionPreference = "Stop"

function Stop-Install([string]$Message) {
    throw "Installation stopped: $Message"
}

if (-not $IsWindows -and $env:OS -ne "Windows_NT") {
    Stop-Install "This installer supports Windows. On macOS or Linux, use scripts/install.sh."
}

$Repository = if ($env:OPENBANKINGMCP_REPOSITORY) { $env:OPENBANKINGMCP_REPOSITORY } else { "https://github.com/theblondealex/openbankingMCP.git" }
$ReleaseVersion = if ($env:OPENBANKINGMCP_VERSION) { $env:OPENBANKINGMCP_VERSION } else { "v0.3.0" }
$DefaultRoot = Join-Path $env:LOCALAPPDATA "OpenBankingMCP"
$InstallRoot = if ($env:OPENBANKINGMCP_INSTALL_DIR) { $env:OPENBANKINGMCP_INSTALL_DIR } else { $DefaultRoot }
$AppDir = Join-Path $InstallRoot "app"
$VenvDir = Join-Path $InstallRoot "venv"

$Git = Get-Command git -ErrorAction SilentlyContinue
if (-not $Git) {
    Stop-Install "Git is required. Install Git for Windows from https://git-scm.com/download/win and run this installer again."
}

$Python = Get-Command python -ErrorAction SilentlyContinue
$PythonPrefix = @()
if (-not $Python) {
    $Python = Get-Command py -ErrorAction SilentlyContinue
    $PythonPrefix = @("-3")
}
if (-not $Python) {
    Stop-Install "Python 3.9 or newer is required. Install it from https://www.python.org/downloads/windows/ and enable 'Add Python to PATH'."
}

& $Python.Source @PythonPrefix -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)"
if ($LASTEXITCODE -ne 0) {
    Stop-Install "Python 3.9 or newer is required. Install the latest Python from https://www.python.org/downloads/windows/."
}

if (Test-Path $AppDir) {
    $Configure = Join-Path $VenvDir "Scripts\openbanking-mcp-configure.exe"
    $Doctor = Join-Path $VenvDir "Scripts\openbanking-mcp-doctor.exe"
    if (Test-Path $Configure) {
        Stop-Install "OpenBankingMCP is already installed at $InstallRoot. Update credentials with '$Configure' or diagnose it with '$Doctor'."
    }
    Stop-Install "An incomplete installation exists at $InstallRoot. Nothing was deleted. Remove only that folder, then run this installer again."
}

New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
& $Git.Source clone --depth 1 --branch $ReleaseVersion $Repository $AppDir
if ($LASTEXITCODE -ne 0) {
    Stop-Install "Could not download OpenBankingMCP $ReleaseVersion. Check your internet connection and release version."
}
if (-not (Test-Path (Join-Path $AppDir "web\dist\index.html"))) {
    Stop-Install "OpenBankingMCP $ReleaseVersion is missing dashboard assets. Use a published release."
}

& $Python.Source @PythonPrefix -m venv $VenvDir
if ($LASTEXITCODE -ne 0) {
    Stop-Install "Could not create the isolated Python environment. Reinstall Python, then try again."
}

$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$Configure = Join-Path $VenvDir "Scripts\openbanking-mcp-configure.exe"
$Service = Join-Path $VenvDir "Scripts\openbanking-mcp-service.exe"
$Doctor = Join-Path $VenvDir "Scripts\openbanking-mcp-doctor.exe"

& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { Stop-Install "Could not update the installer tools. Check your internet connection." }
& $VenvPython -m pip install --editable $AppDir
if ($LASTEXITCODE -ne 0) { Stop-Install "Could not install OpenBankingMCP dependencies. Check your internet connection." }

Write-Host "`nOpenBankingMCP $ReleaseVersion is installed on Windows."
Write-Host "Next, paste your TrueLayer live client ID and secret into the secure setup prompts."
& $Configure
if ($LASTEXITCODE -ne 0) { Stop-Install "TrueLayer setup was not completed. Correct the message above, then run '$Configure'." }
& $Service install
if ($LASTEXITCODE -ne 0) { Stop-Install "Could not start the local dashboard service. Run '$Doctor' for the exact fix." }
& $Doctor
if ($LASTEXITCODE -ne 0) { Stop-Install "Setup completed, but the final health check failed. Run '$Doctor'." }

Write-Host "`nSetup complete. Opening the local dashboard."
Start-Process "http://127.0.0.1:3847"
