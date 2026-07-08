"""FastAPI server entry point.

Usage:
    python api_server.py
    # or: uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --reload
"""

import os
import socket
import subprocess
import sys
from typing import Optional

import uvicorn

from app.config import PROJECT_ROOT


def _find_listening_pid(port: int) -> Optional[int]:
    if sys.platform != "win32":
        return None
    try:
        output = subprocess.check_output(
            ["netstat", "-ano"],
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        for line in output.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.split()
                return int(parts[-1])
    except (subprocess.SubprocessError, ValueError, OSError):
        pass
    return None


def ensure_port_available(host: str, port: int) -> None:
    check_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((check_host, port))
    except OSError:
        pid = _find_listening_pid(port)
        lines = [
            f"❌ 端口 {port} 已被占用，无法启动 API 服务（{host}:{port}）。",
        ]
        if pid:
            lines.append(f"   占用进程 PID: {pid}")
            lines.append(f"   结束进程: taskkill /PID {pid} /F")
        else:
            lines.append(f"   查看占用: netstat -ano | findstr :{port}")
        lines.append(f"   或换端口: set API_PORT=8001 && python api_server.py")
        print("\n".join(lines), file=sys.stderr)
        sys.exit(1)
    finally:
        sock.close()


if __name__ == "__main__":
    host = os.getenv("API_HOST", "127.0.0.1")
    port = int(os.getenv("API_PORT", "8000"))
    ensure_port_available(host, port)
    uvicorn.run(
        "app.api.main:app",
        host=host,
        port=port,
        reload=os.getenv("API_RELOAD", "false").lower() == "true",
        reload_dirs=[str(PROJECT_ROOT / "app")],
    )
