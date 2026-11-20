"""Supervise the API, Streamlit and an unprivileged, WebSocket-aware nginx gateway."""

from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def nginx_config(port: int) -> str:
    if not 1024 <= port <= 65535:
        raise ValueError("Public port must be between 1024 and 65535")
    return """pid /tmp/fasalbima-nginx.pid;
error_log /dev/stderr warn;
events { worker_connections 256; }
http {
    include /etc/nginx/mime.types;
    access_log off;
    client_body_temp_path /tmp/fasalbima-client;
    proxy_temp_path /tmp/fasalbima-proxy;
    fastcgi_temp_path /tmp/fasalbima-fastcgi;
    uwsgi_temp_path /tmp/fasalbima-uwsgi;
    scgi_temp_path /tmp/fasalbima-scgi;
    client_max_body_size 1m;
    map $http_upgrade $connection_upgrade { default upgrade; '' close; }
    server {
        listen PORT;
        location = /health { proxy_pass http://127.0.0.1:8000/health; }
        location /api/ {
            proxy_pass http://127.0.0.1:8000/;
            proxy_read_timeout 190s;
            proxy_set_header Host $host;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
        location / {
            proxy_pass http://127.0.0.1:8501;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
            proxy_set_header Host $host;
            proxy_read_timeout 86400s;
            proxy_buffering off;
        }
    }
}
""".replace("listen PORT;", f"listen {port};")


def wait_ready(url: str, children: list[subprocess.Popen], timeout: float = 90) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if any(child.poll() is not None for child in children):
            raise RuntimeError("A service exited during startup")
        try:
            with urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError):
            pass
        time.sleep(0.5)
    raise RuntimeError(f"Service did not become ready: {url}")


def main() -> None:
    port = int(os.environ.get("PORT", "7860"))
    config = nginx_config(port)
    config_file = Path("/tmp/fasalbima-nginx.conf")
    config_file.write_text(config, encoding="utf-8")
    children: list[subprocess.Popen] = []

    def stop(_signum=None, _frame=None):
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
        for child in reversed(children):
            try:
                child.wait(timeout=8)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()

    def interrupt(_signum, _frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGINT, interrupt)
    env = dict(os.environ, FASALBIMA_API_URL="http://127.0.0.1:8000")
    try:
        children.append(
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8000",
                    "--root-path",
                    "/api",
                ],
                cwd=ROOT,
                env=env,
            )
        )
        wait_ready("http://127.0.0.1:8000/health", children)
        children.append(
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "streamlit",
                    "run",
                    "ui/app.py",
                    "--server.address=127.0.0.1",
                    "--server.port=8501",
                    "--server.headless=true",
                    "--browser.gatherUsageStats=false",
                ],
                cwd=ROOT,
                env=env,
            )
        )
        wait_ready("http://127.0.0.1:8501/_stcore/health", children)
        children.append(
            subprocess.Popen(["nginx", "-c", str(config_file), "-g", "daemon off;"], cwd=ROOT)
        )
        while all(child.poll() is None for child in children):
            time.sleep(0.5)
        raise RuntimeError("A hosted service exited unexpectedly")
    finally:
        stop()


if __name__ == "__main__":
    main()
