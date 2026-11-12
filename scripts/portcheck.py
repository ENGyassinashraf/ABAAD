"""Exit 1 with a clear message if any of the given local TCP ports is in use.

Usage: python scripts/portcheck.py 8000 3000
"""

from __future__ import annotations

import socket
import subprocess
import sys


def listening(port: int) -> bool:
    for family, host in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
        try:
            with socket.socket(family, socket.SOCK_STREAM) as s:
                s.settimeout(0.3)
                if s.connect_ex((host, port)) == 0:
                    return True
        except OSError:
            continue
    return False


def owner(port: int) -> str:
    try:
        out = subprocess.run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
        return out or "(owner unknown)"
    except (OSError, subprocess.SubprocessError):
        return "(lsof not available to show the owner)"


def main(ports: list[int]) -> int:
    busy = [p for p in ports if listening(p)]
    for p in busy:
        print(f"ERROR: port {p} is already in use.\n{owner(p)}", file=sys.stderr)
    if busy:
        print("Stop the program using it (if it is a previous ABAAD run: make stop), then retry.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main([int(a) for a in sys.argv[1:]]))
