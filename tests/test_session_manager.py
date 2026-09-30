from __future__ import annotations

from sci_nma_agent.databases.session_manager import (
    BrowserSessionManager,
    InstitutionalSessionStatus,
)


class _FakeResponse:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_cdp_url_accepts_local_loopback_endpoints():
    for url in (
        "http://127.0.0.1:9222",
        "http://localhost:9222/",
        "https://[::1]:9222",
    ):
        valid, error = BrowserSessionManager.validate_cdp_url(url)
        assert valid is True
        assert error == ""


def test_cdp_url_rejects_remote_hosts_and_embedded_credentials():
    for url in (
        "http://192.168.1.10:9222",
        "http://example.test:9222",
        "http://user:secret@127.0.0.1:9222",
    ):
        valid, error = BrowserSessionManager.validate_cdp_url(url)
        assert valid is False
        assert error


def test_cdp_url_rejects_non_base_urls_and_unsupported_schemes():
    for url in (
        "file:///tmp/cdp",
        "http://127.0.0.1:9222/json",
        "http://127.0.0.1:9222?token=secret",
    ):
        valid, error = BrowserSessionManager.validate_cdp_url(url)
        assert valid is False
        assert error


def test_recommended_chrome_command_uses_isolated_loopback_profile():
    command = BrowserSessionManager.recommended_chrome_command(
        chrome_executable="chrome.exe",
        port=9333,
        profile_dir=r"C:\Temp\sci-nma-cdp",
    )

    assert command == [
        "chrome.exe",
        "--remote-debugging-address=127.0.0.1",
        "--remote-debugging-port=9333",
        r"--user-data-dir=C:\Temp\sci-nma-cdp",
    ]
    assert all("disable-blink-features" not in part for part in command)


def test_cdp_runtime_policy_does_not_spoof_automation_signals():
    policy = BrowserSessionManager.cdp_runtime_policy()

    assert policy["headed_headless_mode_specific_overrides"] is False
    assert policy["navigator_webdriver_override"] is False
    assert policy["automation_controlled_override"] is False
    assert policy["stealth_injection"] is False
    assert policy["verification_handling"] == "user_action_checkpoint_same_profile"


def test_cdp_status_rejects_unsafe_endpoint_without_network_call(monkeypatch):
    calls = []

    def fail_if_called(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("unsafe endpoint must be rejected before HTTP")

    monkeypatch.setattr(
        "sci_nma_agent.databases.session_manager.requests.get",
        fail_if_called,
    )
    manager = BrowserSessionManager("http://203.0.113.10:9222")

    status = manager.cdp_connection_status()

    assert status["status"] == InstitutionalSessionStatus.CDP_UNSAFE
    assert status["connected"] is False
    assert calls == []


def test_cdp_status_requires_real_devtools_version_payload(monkeypatch):
    monkeypatch.setattr(
        "sci_nma_agent.databases.session_manager.requests.get",
        lambda *args, **kwargs: _FakeResponse(200, {"status": "ok"}),
    )
    manager = BrowserSessionManager()

    status = manager.cdp_connection_status()

    assert status["status"] == InstitutionalSessionStatus.UNREACHABLE
    assert status["connected"] is False
    assert "Browser and webSocketDebuggerUrl" in status["error"]


def test_cdp_status_accepts_local_devtools_payload(monkeypatch):
    monkeypatch.setattr(
        "sci_nma_agent.databases.session_manager.requests.get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            {
                "Browser": "Chrome/136.0.0.0",
                "Protocol-Version": "1.3",
                "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/browser/fixture",
            },
        ),
    )
    manager = BrowserSessionManager()

    status = manager.cdp_connection_status()

    assert status["status"] == "CONNECTED"
    assert status["connected"] is True
    assert status["browser"] == "Chrome/136.0.0.0"
    assert status["automation_policy"]["navigator_webdriver_override"] is False


def test_cdp_status_rejects_remote_advertised_websocket(monkeypatch):
    monkeypatch.setattr(
        "sci_nma_agent.databases.session_manager.requests.get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            {
                "Browser": "Chrome/136.0.0.0",
                "webSocketDebuggerUrl": "ws://192.168.1.10:9222/devtools/browser/fixture",
            },
        ),
    )
    manager = BrowserSessionManager()

    status = manager.cdp_connection_status()

    assert status["status"] == InstitutionalSessionStatus.CDP_UNSAFE
    assert status["connected"] is False


def test_cdp_status_rejects_websocket_on_unexpected_loopback_port(monkeypatch):
    monkeypatch.setattr(
        "sci_nma_agent.databases.session_manager.requests.get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            {
                "Browser": "Chrome/136.0.0.0",
                "webSocketDebuggerUrl": "ws://127.0.0.1:9333/devtools/browser/fixture",
            },
        ),
    )
    manager = BrowserSessionManager("http://127.0.0.1:9222")

    status = manager.cdp_connection_status()

    assert status["status"] == InstitutionalSessionStatus.CDP_UNSAFE
    assert status["connected"] is False


def test_database_probe_pauses_for_user_verification_and_is_recoverable():
    manager = BrowserSessionManager()

    status, message = manager.probe_database_access(
        "Web of Science",
        "Please verify you are human to continue",
        "https://www.webofscience.com/",
    )

    assert status == InstitutionalSessionStatus.VERIFICATION_REQUIRED
    assert "user action" in message
    assert manager.is_recoverable_status(status)


def test_get_open_pages_ignores_untrusted_page_websocket_urls(monkeypatch):
    responses = iter(
        [
            _FakeResponse(
                200,
                {
                    "Browser": "Chrome/136.0.0.0",
                    "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/browser/fixture",
                },
            ),
            _FakeResponse(
                200,
                [
                    {
                        "type": "page",
                        "title": "trusted",
                        "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/ok",
                    },
                    {
                        "type": "page",
                        "title": "unexpected port",
                        "webSocketDebuggerUrl": "ws://127.0.0.1:9333/devtools/page/bad",
                    },
                ],
            ),
        ]
    )
    monkeypatch.setattr(
        "sci_nma_agent.databases.session_manager.requests.get",
        lambda *args, **kwargs: next(responses),
    )
    manager = BrowserSessionManager()

    pages = manager.get_open_pages()

    assert [page["title"] for page in pages] == ["trusted"]
