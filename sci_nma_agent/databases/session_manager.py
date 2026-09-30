"""
Browser Institutional Session Manager & Access Probe.

The direct Chrome DevTools connection is deliberately constrained to a
loopback endpoint.  Chrome 136+ also requires a non-default user-data
directory when remote debugging is enabled; the CLI/documentation provide the
dedicated profile command for that fallback route.
"""

import ipaddress
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlsplit

import requests


class InstitutionalSessionStatus:
    OK = "AUTHENTICATED"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    BLOCKED = "BLOCKED_OR_CAPTCHA"
    VERIFICATION_REQUIRED = "USER_VERIFICATION_REQUIRED"
    SERVER_ERROR = "SERVER_ERROR"
    UNREACHABLE = "UNREACHABLE"
    CDP_UNSAFE = "CDP_UNSAFE_ENDPOINT"


class BrowserSessionManager:
    """
    Manages browser session reuse and institutional access verification.

    The fallback CDP endpoint must be local loopback.  A non-loopback endpoint
    would expose browser cookies and debugging capabilities over the network,
    so it is rejected before any request is made.
    """

    def __init__(self, cdp_url: str = "http://127.0.0.1:9222", timeout_sec: int = 5):
        self.cdp_url = cdp_url.rstrip("/")
        self.timeout_sec = timeout_sec
        self.endpoint_valid, self.endpoint_error = self.validate_cdp_url(self.cdp_url)
        self.last_cdp_status: Dict[str, Any] = {}

    @staticmethod
    def validate_cdp_url(cdp_url: str) -> Tuple[bool, str]:
        """Validate a CDP base URL without making a network request.

        Chrome's remote debugging HTTP endpoint is intended for local use.
        Requiring loopback also prevents accidentally attaching to a browser
        on a LAN/VPN/public address.  ``http`` remains valid on loopback
        because that is Chrome's normal local DevTools transport.
        """
        if not isinstance(cdp_url, str) or not cdp_url.strip():
            return False, "CDP endpoint is empty."

        try:
            parsed = urlsplit(cdp_url.strip())
        except ValueError as exc:
            return False, f"CDP endpoint URL is invalid: {exc}"

        if parsed.scheme.lower() not in {"http", "https"}:
            return False, "CDP endpoint must use http:// or https://."
        if parsed.username or parsed.password:
            return False, "CDP endpoint must not contain embedded credentials."
        if not parsed.hostname:
            return False, "CDP endpoint must include a host."
        try:
            parsed.port
        except ValueError as exc:
            return False, f"CDP endpoint port is invalid: {exc}"
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            return False, "CDP endpoint must be a base URL without path, query, or fragment."

        if not BrowserSessionManager._is_loopback_host(parsed.hostname):
            return (
                False,
                "CDP endpoint must use localhost, 127.0.0.1, or ::1; "
                "remote debugging over a network address is rejected.",
            )
        return True, ""

    @staticmethod
    def _is_loopback_host(hostname: str) -> bool:
        normalized = hostname.rstrip(".").lower()
        if normalized == "localhost":
            return True
        try:
            return ipaddress.ip_address(normalized).is_loopback
        except ValueError:
            return False

    @classmethod
    def _is_safe_websocket_url(cls, websocket_url: Any, cdp_url: str) -> bool:
        """Return whether a CDP WebSocket URL stays on local loopback."""
        try:
            websocket = urlsplit(str(websocket_url))
            endpoint = urlsplit(cdp_url)
            websocket_port = websocket.port or (443 if websocket.scheme.lower() == "wss" else 80)
            endpoint_port = endpoint.port or (443 if endpoint.scheme.lower() == "https" else 80)
        except (TypeError, ValueError):
            return False
        return bool(
            websocket.scheme.lower() in {"ws", "wss"}
            and websocket.hostname
            and not websocket.username
            and not websocket.password
            and cls._is_loopback_host(websocket.hostname)
            and websocket_port == endpoint_port
            and websocket.path.startswith("/devtools/")
            and not websocket.query
            and not websocket.fragment
        )

    @staticmethod
    def recommended_chrome_command(
        chrome_executable: str = "chrome.exe",
        port: int = 9222,
        profile_dir: Optional[str] = None,
    ) -> list:
        """Build the isolated-profile Chrome DevTools fallback command.

        This is intentionally a normal, headed Chrome launch. It does not
        rewrite browser properties or disable site security controls.
        """
        if not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError("CDP port must be an integer between 1 and 65535.")
        if profile_dir is None:
            local_app_data = os.environ.get("LOCALAPPDATA")
            base = Path(local_app_data) if local_app_data else Path.home()
            profile_dir = str(base / "sci-nma-agent" / "chrome-cdp-profile")
        return [
            chrome_executable,
            "--remote-debugging-address=127.0.0.1",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile_dir}",
        ]

    @staticmethod
    def cdp_runtime_policy() -> Dict[str, Any]:
        """Return the auditable browser-automation policy.

        The project uses ordinary headed Chrome/CDP session reuse. It does
        not rewrite ``navigator.webdriver`` or inject an
        ``AutomationControlled`` override. This keeps the authenticated
        session and search evidence reproducible and makes a verification
        page a user-action checkpoint rather than a bypass target.
        """
        return {
            "headed_headless_mode_specific_overrides": False,
            "navigator_webdriver_override": False,
            "automation_controlled_override": False,
            "stealth_injection": False,
            "verification_handling": "user_action_checkpoint_same_profile",
            "endpoint_policy": "loopback_only_dedicated_profile",
        }

    def cdp_connection_status(self) -> Dict[str, Any]:
        """Return a structured, auditable status for the CDP endpoint."""
        if not self.endpoint_valid:
            self.last_cdp_status = {
                "status": InstitutionalSessionStatus.CDP_UNSAFE,
                "connected": False,
                "url": self.cdp_url,
                "error": self.endpoint_error,
                "automation_policy": self.cdp_runtime_policy(),
            }
            return dict(self.last_cdp_status)

        try:
            resp = requests.get(
                f"{self.cdp_url}/json/version",
                timeout=self.timeout_sec,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            self.last_cdp_status = {
                "status": InstitutionalSessionStatus.UNREACHABLE,
                "connected": False,
                "url": self.cdp_url,
                "error": str(exc),
                "automation_policy": self.cdp_runtime_policy(),
            }
            return dict(self.last_cdp_status)
        except Exception as exc:  # pragma: no cover - defensive for custom clients
            self.last_cdp_status = {
                "status": InstitutionalSessionStatus.UNREACHABLE,
                "connected": False,
                "url": self.cdp_url,
                "error": str(exc),
                "automation_policy": self.cdp_runtime_policy(),
            }
            return dict(self.last_cdp_status)

        if resp.status_code != 200:
            self.last_cdp_status = {
                "status": InstitutionalSessionStatus.UNREACHABLE,
                "connected": False,
                "url": self.cdp_url,
                "http_status": resp.status_code,
                "error": f"CDP /json/version returned HTTP {resp.status_code}.",
                "automation_policy": self.cdp_runtime_policy(),
            }
            return dict(self.last_cdp_status)

        try:
            payload = resp.json()
        except (ValueError, TypeError) as exc:
            self.last_cdp_status = {
                "status": InstitutionalSessionStatus.UNREACHABLE,
                "connected": False,
                "url": self.cdp_url,
                "error": f"CDP /json/version returned invalid JSON: {exc}",
                "automation_policy": self.cdp_runtime_policy(),
            }
            return dict(self.last_cdp_status)

        if not isinstance(payload, dict):
            error = "CDP /json/version returned a non-object payload."
            self.last_cdp_status = {
                "status": InstitutionalSessionStatus.UNREACHABLE,
                "connected": False,
                "url": self.cdp_url,
                "error": error,
                "automation_policy": self.cdp_runtime_policy(),
            }
            return dict(self.last_cdp_status)

        # These fields distinguish a real DevTools endpoint from an unrelated
        # HTTP service bound to the same port.
        browser = payload.get("Browser")
        websocket_url = payload.get("webSocketDebuggerUrl")
        if not browser or not websocket_url:
            error = (
                "CDP /json/version is incomplete; expected Browser and "
                "webSocketDebuggerUrl."
            )
            self.last_cdp_status = {
                "status": InstitutionalSessionStatus.UNREACHABLE,
                "connected": False,
                "url": self.cdp_url,
                "error": error,
            }
            return dict(self.last_cdp_status)
        if not self._is_safe_websocket_url(websocket_url, self.cdp_url):
            error = "CDP advertised a WebSocket endpoint that is not local loopback."
            self.last_cdp_status = {
                "status": InstitutionalSessionStatus.CDP_UNSAFE,
                "connected": False,
                "url": self.cdp_url,
                "error": error,
                "automation_policy": self.cdp_runtime_policy(),
            }
            return dict(self.last_cdp_status)

        self.last_cdp_status = {
            "status": "CONNECTED",
            "connected": True,
            "url": self.cdp_url,
            "browser": browser,
            "webSocketDebuggerUrl": websocket_url,
            "protocolVersion": payload.get("Protocol-Version"),
            "automation_policy": self.cdp_runtime_policy(),
        }
        return dict(self.last_cdp_status)

    def is_browser_connected(self) -> bool:
        """Check if remote debugging browser is accessible."""
        return bool(self.cdp_connection_status().get("connected"))

    def get_open_pages(self) -> list:
        """List currently active tabs/pages in the debugging browser."""
        if not self.endpoint_valid or not self.is_browser_connected():
            return []
        try:
            resp = requests.get(
                f"{self.cdp_url}/json/list",
                timeout=self.timeout_sec,
                allow_redirects=False,
            )
            if resp.status_code == 200:
                payload = resp.json()
                if isinstance(payload, list):
                    pages = []
                    for page in payload:
                        if not isinstance(page, dict) or page.get("type") != "page":
                            continue
                        page_ws = page.get("webSocketDebuggerUrl")
                        if not self._is_safe_websocket_url(page_ws, self.cdp_url):
                            continue
                        pages.append(page)
                    return pages
        except Exception:
            pass
        return []

    def probe_database_access(self, database: str, page_text: str, page_url: str) -> Tuple[str, str]:
        """
        Rule-based DOM/Text heuristic to probe institutional login status for a specific database.
        Returns: (status: InstitutionalSessionStatus, description: str)
        """
        db_lower = database.lower()
        text_lower = page_text.lower()

        # Keep explicit user challenges separate from hard access denials so
        # the workflow can pause and resume in the same authenticated context.
        if any(
            w in text_lower
            for w in (
                "captcha",
                "verify you are human",
                "verify you're human",
                "complete the security check",
                "checking your browser",
            )
        ):
            return (
                InstitutionalSessionStatus.VERIFICATION_REQUIRED,
                f"[{database}] Site verification requires user action in the same browser session.",
            )
        if any(w in text_lower for w in ["access denied", "unusual traffic"]):
            return InstitutionalSessionStatus.BLOCKED, f"[{database}] CAPTCHA or Anti-bot challenge detected."

        # A completed challenge can leave the old page mounted while the
        # application request fails.  Do this check before the normal
        # authenticated-page heuristics; otherwise a WoS error page that still
        # contains "Clarivate" and "Search" is incorrectly reported as OK.
        if any(
            token in text_lower
            for token in (
                "server.unexpectederror",
                "server unexpected error",
                "internal server error",
                "unexpected server error",
                "request failed",
            )
        ):
            return (
                InstitutionalSessionStatus.SERVER_ERROR,
                f"[{database}] Search page returned a transient server error after verification; "
                "refresh the search surface and rebuild the query before retrying.",
            )

        if "embase" in db_lower:
            # Embase institutional indicators
            if "sign in to embase" in text_lower or "choose how to sign in" in text_lower:
                return InstitutionalSessionStatus.LOGIN_REQUIRED, "Embase requires user institutional login."
            if "session expired" in text_lower or "your session has timed out" in text_lower:
                return InstitutionalSessionStatus.SESSION_EXPIRED, "Embase institutional session expired. Please re-authenticate."
            if any(term in text_lower for term in ["access provided by", "institution", "elsevier", "document search", "results"]):
                return InstitutionalSessionStatus.OK, "Embase institutional access active."

        elif "wos" in db_lower or "web of science" in db_lower:
            if "sign in" in text_lower and not any(term in text_lower for term in ["clarivate", "core collection", "search"]):
                return InstitutionalSessionStatus.LOGIN_REQUIRED, "Web of Science requires institutional / Shibboleth login."
            if "session has expired" in text_lower:
                return InstitutionalSessionStatus.SESSION_EXPIRED, "Web of Science session expired. Please refresh."
            if any(term in text_lower for term in ["web of science core collection", "clarivate", "search documents"]):
                return InstitutionalSessionStatus.OK, "Web of Science institutional access active."

        elif "cochrane" in db_lower:
            if "sign in" in text_lower and "cochrane library" not in text_lower:
                return InstitutionalSessionStatus.LOGIN_REQUIRED, "Cochrane Library access check requires institutional login."
            return InstitutionalSessionStatus.OK, "Cochrane Library public/institutional search surface accessible."

        elif "pubmed" in db_lower:
            return InstitutionalSessionStatus.OK, "PubMed public E-utilities/Web access accessible."

        # Fallback heuristic
        if "sign in" in text_lower or "log in" in text_lower:
            return InstitutionalSessionStatus.LOGIN_REQUIRED, f"{database} login required."
        return InstitutionalSessionStatus.OK, f"{database} search surface ready."

    @staticmethod
    def is_recoverable_status(status: str) -> bool:
        """Return whether the browser page can be recovered without new credentials."""
        return status in {
            InstitutionalSessionStatus.VERIFICATION_REQUIRED,
            InstitutionalSessionStatus.SERVER_ERROR,
            InstitutionalSessionStatus.SESSION_EXPIRED,
        }

    def prompt_user_for_recovery(self, database: str, target_url: str) -> None:
        """Give a deterministic recovery sequence for a stale post-verification page."""
        print(f"\n[!] SEARCH PAGE RECOVERY REQUIRED FOR {database.upper()}")
        print(f"    Target URL: {target_url}")
        print("    1. Keep the completed verification in the same browser profile.")
        print("    2. Reload or return to the database search page; do not reuse the stale error view.")
        print("    3. Re-enter the recorded query and run a small probe search first.")
        print("    4. If the probe succeeds, rerun the full query and save the visible count/history ID.")
        print("    5. If it repeats, switch to Search History or the protocol-recorded fallback route.")

    def prompt_user_for_verification(self, database: str, target_url: str) -> None:
        """Pause automation for a user-completed challenge in the same session."""
        print(f"\n[!] USER VERIFICATION REQUIRED FOR {database.upper()}")
        print(f"    Target URL: {target_url}")
        print("    1. Keep this browser and profile open; do not create a new session.")
        print("    2. Complete the site's verification directly in the visible browser.")
        print("    3. Return here and re-check the page/session before continuing.")
        print("    4. Resume with the saved query only after the normal search page is restored.")

    def prompt_user_for_login(self, database: str, target_url: str) -> None:
        """
        Display instructions for user to complete institutional login in their browser without collecting credentials.
        """
        print(f"\n[!] INSTITUTIONAL LOGIN REQUIRED FOR {database.upper()}")
        print(f"    Target URL: {target_url}")
        print("    " + "-" * 70)
        print("    1. Open or switch to the Chrome browser window.")
        print(f"    2. Complete your university/hospital institutional SSO / VPN login on {database}.")
        print("    3. Ensure search and full-batch export functions are accessible.")
        print("    4. Once logged in, return here and press Enter to resume automation.")
        print("    " + "-" * 70)
