"""Generate a per-user launchd plist for the local dashboard."""

from pathlib import Path
import subprocess
import sys
import os
from xml.sax.saxutils import escape


LABEL = "com.openbankingmcp.service"


def plist(python: str, log_path: str, working_directory: str) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>Label</key><string>{LABEL}</string><key>ProgramArguments</key><array><string>{escape(python)}</string><string>-m</string><string>openbankingmcp.dashboard</string></array><key>WorkingDirectory</key><string>{escape(working_directory)}</string><key>RunAtLoad</key><true/><key>KeepAlive</key><true/><key>ThrottleInterval</key><integer>5</integer><key>StandardOutPath</key><string>{escape(log_path)}</string><key>StandardErrorPath</key><string>{escape(log_path)}</string></dict></plist>'''


def install_path() -> Path:
    return Path("~/Library/LaunchAgents").expanduser() / f"{LABEL}.plist"

def install(python: str, log_path: str) -> Path:
    path=install_path(); path.parent.mkdir(parents=True,exist_ok=True); path.write_text(plist(python,log_path,str(Path(__file__).resolve().parents[1]))); return path

def uninstall() -> None:
    path=install_path()
    if path.exists(): path.unlink()

def main() -> None:
    import argparse
    parser=argparse.ArgumentParser(); parser.add_argument("action",choices=("install","uninstall")); args=parser.parse_args()
    if args.action == "install":
        path=install(sys.executable, str(Path("~/Library/Logs/openbankingmcp.log").expanduser()))
        subprocess.run(["launchctl","bootout",f"gui/{os.getuid()}/{LABEL}"],check=False,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        subprocess.run(["launchctl","bootstrap",f"gui/{os.getuid()}",str(path)],check=True)
        print(f"Dashboard service installed: {path}\nOpen http://127.0.0.1:3847")
    else:
        path=install_path()
        subprocess.run(["launchctl","bootout",f"gui/{os.getuid()}/{LABEL}"],check=False)
        uninstall()

if __name__ == "__main__":
    main()
