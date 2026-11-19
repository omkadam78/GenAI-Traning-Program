#!/usr/bin/env python3
"""Project-local launcher for FasalBima Sathi.

Ensures:
1. Backend (FastAPI) and Frontend (Streamlit) run in the same Python environment.
2. Backend is started first and verified ready via /health probe before presenting the UI.
3. FASALBIMA_API_URL is automatically set so the UI always communicates with the matching backend port.
4. Clean lifecycle management: terminating the launcher terminates both child processes without leaving stale ports.
"""

from __future__ import annotations

import argparse
import atexit
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a TCP port is currently listening on host."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def check_fasalbima_backend(url: str) -> bool:
    """Verify if a running server at url is an active FasalBima backend."""
    try:
        req = urllib.request.Request(
            f"{url.rstrip('/')}/health", headers={"User-Agent": "FasalBima-Launcher"}
        )
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            if resp.status == 200:
                import json

                data = json.loads(resp.read().decode("utf-8"))
                return data.get("product") == "FasalBima Sathi"
    except Exception:
        pass
    return False


def find_python_executable() -> str:
    """Find the best Python executable with required dependencies."""
    candidates = [
        ROOT / ".venv" / "Scripts" / "python.exe",
        ROOT / ".venv" / "bin" / "python",
        Path(sys.executable),
    ]
    for c in candidates:
        if c.exists():
            try:
                res = subprocess.run(
                    [str(c), "-c", "import uvicorn, streamlit, fastapi; print('ok')"],
                    capture_output=True,
                    text=True,
                    timeout=5.0,
                )
                if res.returncode == 0 and "ok" in res.stdout:
                    return str(c)
            except Exception:
                pass
    return sys.executable


def wait_for_backend(
    url: str, timeout: float = 30.0, process: subprocess.Popen | None = None
) -> bool:
    """Poll the backend health endpoint until it responds with HTTP 200 or timeout expires."""
    start_time = time.time()
    health_url = f"{url.rstrip('/')}/health"
    print(f"Waiting for backend readiness at {health_url}...", flush=True)

    while time.time() - start_time < timeout:
        if process and process.poll() is not None:
            print(
                f"\n[ERROR] Backend process exited unexpectedly with code {process.returncode}.",
                file=sys.stderr,
            )
            return False

        try:
            req = urllib.request.Request(health_url, headers={"User-Agent": "FasalBima-Launcher"})
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError, ConnectionResetError):
            pass

        time.sleep(0.3)

    return False


def stop_process(proc: subprocess.Popen | None, name: str) -> None:
    """Gracefully terminate a child process."""
    if proc is None or proc.poll() is not None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=3.0)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Start FasalBima Sathi backend and Streamlit UI consistently."
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("HOST", "127.0.0.1"),
        help="Host to bind servers (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--backend-port",
        type=int,
        default=int(os.environ.get("FASALBIMA_BACKEND_PORT", os.environ.get("PORT", "8000"))),
        help="FastAPI backend port (default: 8000)",
    )
    parser.add_argument(
        "--ui-port",
        type=int,
        default=int(
            os.environ.get("FASALBIMA_UI_PORT", os.environ.get("STREAMLIT_SERVER_PORT", "8501"))
        ),
        help="Streamlit UI port (default: 8501)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run Streamlit in headless mode without opening a browser window",
    )
    parser.add_argument(
        "--backend-only", action="store_true", help="Start only the FastAPI backend server"
    )
    parser.add_argument(
        "--ui-only",
        action="store_true",
        help="Start only the Streamlit UI (assumes backend is running)",
    )

    args = parser.parse_args()

    python_exe = find_python_executable()
    backend_url = f"http://{args.host}:{args.backend_port}"
    app_url = f"http://{args.host}:{args.ui_port}"

    # Synchronize environment variables for all child processes
    env = os.environ.copy()
    env["FASALBIMA_API_URL"] = backend_url
    env["STREAMLIT_SERVER_PORT"] = str(args.ui_port)
    env["STREAMLIT_SERVER_ADDRESS"] = args.host
    if args.headless:
        env["STREAMLIT_SERVER_HEADLESS"] = "true"

    backend_proc: subprocess.Popen | None = None
    ui_proc: subprocess.Popen | None = None

    def cleanup() -> None:
        print("\nShutting down FasalBima Sathi services...", flush=True)
        stop_process(ui_proc, "Streamlit UI")
        stop_process(backend_proc, "FastAPI Backend")

    atexit.register(cleanup)

    def sig_handler(signum, frame) -> None:
        sys.exit(0)

    try:
        signal.signal(signal.SIGINT, sig_handler)
        signal.signal(signal.SIGTERM, sig_handler)
    except Exception:
        pass

    # 1. Check & Start Backend Server if requested
    if not args.ui_only:
        if is_port_in_use(args.backend_port, args.host):
            if check_fasalbima_backend(backend_url):
                print(
                    f"[INFO] Found already running FasalBima backend at {backend_url}. Reusing it.",
                    flush=True,
                )
            else:
                print(
                    f"[ERROR] Port {args.backend_port} is already in use by another application.\n"
                    f"Please terminate the process holding port {args.backend_port} or run with --backend-port <port>.",
                    file=sys.stderr,
                )
                return 1
        else:
            backend_cmd = [
                python_exe,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                args.host,
                "--port",
                str(args.backend_port),
            ]
            print(f"Starting FastAPI backend ({backend_url})...", flush=True)
            backend_proc = subprocess.Popen(backend_cmd, cwd=str(ROOT), env=env)

            # Wait for backend readiness probe
            if not wait_for_backend(backend_url, timeout=25.0, process=backend_proc):
                print(
                    f"[ERROR] Backend failed to become healthy at {backend_url}/health within timeout.",
                    file=sys.stderr,
                )
                return 1
            print(f"Backend is healthy at {backend_url}", flush=True)

    if args.backend_only:
        print(f"\nBackend running at {backend_url}. Press Ctrl+C to stop.", flush=True)
        try:
            if backend_proc:
                backend_proc.wait()
            else:
                while True:
                    time.sleep(1)
        except KeyboardInterrupt:
            pass
        return 0

    # 2. Check UI Port & Start Streamlit UI
    if is_port_in_use(args.ui_port, args.host):
        print(
            f"[ERROR] Port {args.ui_port} is already in use by another application.\n"
            f"Please terminate the process holding port {args.ui_port} or run with --ui-port <port>.",
            file=sys.stderr,
        )
        return 1

    # 2. Start Streamlit UI
    streamlit_cmd = [
        python_exe,
        "-m",
        "streamlit",
        "run",
        "ui/app.py",
        "--server.port",
        str(args.ui_port),
        "--server.address",
        args.host,
    ]
    if args.headless:
        streamlit_cmd.extend(["--server.headless", "true"])

    print(f"Starting Streamlit Farmer UI at {app_url}...", flush=True)
    ui_proc = subprocess.Popen(streamlit_cmd, cwd=str(ROOT), env=env)

    print("\nFasalBima Sathi is live!")
    print(f"- Web UI:  {app_url}")
    print(f"- Backend: {backend_url}")
    print("Press Ctrl+C to stop all services.\n", flush=True)

    try:
        # Keep launcher running until interrupted or child exits
        while True:
            if backend_proc and backend_proc.poll() is not None:
                print(
                    f"[ERROR] Backend exited with code {backend_proc.returncode}.", file=sys.stderr
                )
                break
            if ui_proc and ui_proc.poll() is not None:
                print(f"[INFO] Streamlit UI closed with code {ui_proc.returncode}.")
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
