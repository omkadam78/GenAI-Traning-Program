"""Verify a real deployed container; never substitutes a mock for a live service."""

import argparse
import base64
import hashlib
import http.client
import json
import os
import time
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def check_websocket(base: str) -> None:
    """Perform a real RFC6455 handshake through the public Streamlit proxy."""
    target = urlsplit(base)
    cls = http.client.HTTPSConnection if target.scheme == "https" else http.client.HTTPConnection
    connection = cls(target.netloc, timeout=10)
    key = base64.b64encode(os.urandom(16)).decode()
    expected = base64.b64encode(
        hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
    ).decode()
    try:
        connection.request(
            "GET",
            target.path.rstrip("/") + "/_stcore/stream",
            headers={
                "Connection": "Upgrade",
                "Upgrade": "websocket",
                "Sec-WebSocket-Key": key,
                "Sec-WebSocket-Version": "13",
                "Sec-WebSocket-Protocol": "streamlit",
                "Origin": base,
            },
        )
        response = connection.getresponse()
        assert response.status == 101, f"WebSocket upgrade failed: {response.status}"
        assert response.getheader("Sec-WebSocket-Accept") == expected
    finally:
        connection.close()


def check(base_url: str, timeout: float = 120) -> dict:
    base = base_url.rstrip("/")
    deadline = time.monotonic() + timeout
    while True:
        try:
            with urlopen(f"{base}/health", timeout=5) as response:
                health = json.load(response)
            assert health["status"] == "ok"
            assert health["product"] == "FasalBima Sathi"
            assert health["records_count"] >= 20
            break
        except (URLError, TimeoutError):
            if time.monotonic() >= deadline:
                raise
            time.sleep(1)
    for path in ("/", "/_stcore/health", "/api/records?limit=1"):
        with urlopen(f"{base}{path}", timeout=10) as response:
            assert response.status == 200, path
    check_websocket(base)
    # Q6 must refuse even when no LLM keys are present in the container.
    request = Request(
        f"{base}/api/ask",
        data=json.dumps({"question": "Has my PMFBY claim been approved?", "top_k": 3}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=20) as response:
        answer = json.load(response)
    assert "i don't know" in answer["answer"].lower(), answer["answer"]
    return {
        "health": "passed",
        "ui": "passed",
        "websocket": "passed",
        "api": "passed",
        "q6_refusal": "passed",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = json.dumps(check(args.url), indent=2)
    print(result)
    if args.output:
        from pathlib import Path

        Path(args.output).write_text(result + "\n", encoding="utf-8")
