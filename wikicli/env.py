"""Device and network facts recorded with evidence (for the offline proof)."""
from __future__ import annotations

import platform
import shutil
import socket
import subprocess


def network_status() -> str:
    """'offline' if no external host is reachable. Checked by opening a TCP socket to
    two public DNS servers; nothing is sent."""
    for host in ("1.1.1.1", "8.8.8.8"):
        try:
            with socket.create_connection((host, 53), timeout=1.5):
                return "online"
        except OSError:
            continue
    return "offline"


def _sysctl(key: str) -> str:
    try:
        return subprocess.run(["sysctl", "-n", key], capture_output=True, text=True).stdout.strip()
    except OSError:
        return ""


def device_specs() -> dict:
    mem = _sysctl("hw.memsize")
    disk = shutil.disk_usage("/")
    return {
        "os": f"macOS {platform.mac_ver()[0]}" if platform.mac_ver()[0] else f"{platform.system()} {platform.release()}",
        "chip": _sysctl("machdep.cpu.brand_string") or platform.processor(),
        "cpu_cores": _sysctl("hw.ncpu"),
        "memory_gb": round(int(mem) / 2**30, 1) if mem.isdigit() else None,
        "memory_type": "unified (CPU+GPU shared)" if platform.machine() == "arm64" else "system RAM",
        "free_disk_gb": round(disk.free / 1e9, 1),
        "python": platform.python_version(),
    }
