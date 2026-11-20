"""Deployment regressions: reject invalid listeners and detect a broken WebSocket proxy."""

from unittest.mock import MagicMock, patch

import pytest

from deploy.serve import nginx_config, wait_ready
from deploy.smoke import check_websocket


@pytest.mark.parametrize("port", [0, 80, 65536])
def test_public_listener_rejects_unsafe_or_invalid_port(port):
    with pytest.raises(ValueError):
        nginx_config(port)


def test_gateway_preserves_health_api_and_streamlit_websocket():
    config = nginx_config(7860)
    assert "listen 7860;" in config
    assert "location = /health { proxy_pass http://127.0.0.1:8000/health; }" in config
    assert "location /api/" in config
    assert "proxy_set_header Upgrade $http_upgrade;" in config
    assert "proxy_set_header Connection $connection_upgrade;" in config
    assert "proxy_buffering off;" in config


def test_startup_rejects_dead_backend_instead_of_advertising_ready():
    child = MagicMock()
    child.poll.return_value = 1
    with pytest.raises(RuntimeError, match="exited during startup"):
        wait_ready("http://127.0.0.1:8000/health", [child])


def test_smoke_detects_a_proxy_that_serves_html_but_breaks_websocket():
    with patch("deploy.smoke.http.client.HTTPSConnection") as factory:
        connection = factory.return_value
        connection.getresponse.return_value.status = 200
        with pytest.raises(AssertionError, match="WebSocket upgrade failed"):
            check_websocket("https://example.invalid")
        connection.close.assert_called_once()
