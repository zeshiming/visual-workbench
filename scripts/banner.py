"""Shared colorful banner — printed by dev / build / serve."""

from __future__ import annotations

import socket


def _get_lan_ip() -> str | None:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        s.connect(("10.254.254.254", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


def banner(lan_ip: str | None = None) -> str:
    if lan_ip is None:
        lan_ip = _get_lan_ip()

    CYAN = "\033[36m"
    YELLOW = "\033[33m"
    GREEN = "\033[32m"
    MAGENTA = "\033[35m"
    BOLD = "\033[1m"
    RESET = "\033[0m"
    DIM = "\033[2m"

    logo = rf"""{CYAN}{BOLD}
  ___     ___   __ __  _____ __ __   ____  ____    ____   ___ {RESET}
 {CYAN}|   \   /   \ |  |  |/ ___/|  |  | /    ||    \  /    | /   \{RESET}
 {CYAN}|    \ |     ||  |  (   \_ |  |  ||  o  ||  o  )|  o  ||     |{RESET}
 {MAGENTA}|  D  ||  O  ||  |  |\__  ||  _  ||     ||     ||     ||  O  |{RESET}
 {MAGENTA}|     ||     ||  :  |/  \ ||  |  ||  _  ||  O  ||  _  ||     |{RESET}
 {MAGENTA}|     ||     ||     |\    ||  |  ||  |  ||     ||  |  ||     |{RESET}
 {MAGENTA}|_____| \___/  \__,_| \___||__|__||__|__||_____||__|__| \___/{RESET}"""

    lines = [
        "",
        logo,
        "",
        f"  {YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}",
        f"  {GREEN}Local {DIM}:{RESET}  http://localhost:8000",
    ]
    if lan_ip and lan_ip != "127.0.0.1":
        lines.append(f"  {GREEN}LAN   {DIM}:{RESET}  http://{lan_ip}:8000")
    lines += [
        f"  {GREEN}API   {DIM}:{RESET}  http://localhost:8000/docs",
        f"  {YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    print(banner())
