"""
Browser Institutional Session Manager & Access Probe.
Enables reusing existing authenticated Chrome sessions (via remote debugging or persistent profile)
for institutional access to commercial medical databases (Embase, Web of Science, Cochrane Library).
"""

import requests
from typing import Dict, Any, Optional, Tuple


class InstitutionalSessionStatus:
    OK = "AUTHENTICATED"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    BLOCKED = "BLOCKED_OR_CAPTCHA"
    UNREACHABLE = "UNREACHABLE"


class BrowserSessionManager:
    """
    Manages browser session reuse and institutional access verification.
    Connects to an existing Chrome browser instance via remote debugging port (default 9222)
    or validates persistent session state.
    """

    def __init__(self, cdp_url: str = "http://127.0.0.1:9222", timeout_sec: int = 5):
        self.cdp_url = cdp_url.rstrip("/")
        self.timeout_sec = timeout_sec

    def is_browser_connected(self) -> bool:
        """Check if remote debugging browser is accessible."""
        try:
            resp = requests.get(f"{self.cdp_url}/json/version", timeout=self.timeout_sec)
            return resp.status_code == 200
        except Exception:
            return False

    def get_open_pages(self) -> list:
        """List currently active tabs/pages in the debugging browser."""
        try:
            resp = requests.get(f"{self.cdp_url}/json/list", timeout=self.timeout_sec)
            if resp.status_code == 200:
                return [p for p in resp.json() if p.get("type") == "page"]
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
        url_lower = page_url.lower()

        # Check for bot / captcha blocks
        if any(w in text_lower for w in ["captcha", "verify you are human", "checking your browser", "access denied", "unusual traffic"]):
            return InstitutionalSessionStatus.BLOCKED, f"[{database}] CAPTCHA or Anti-bot challenge detected."

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
