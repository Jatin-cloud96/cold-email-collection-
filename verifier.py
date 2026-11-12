import re
import socket
import smtplib
from typing import Tuple, Dict, Optional
import dns.resolver
import requests
import config
from quota_manager import QuotaManager

class EmailVerifier:
    """
    Multi-stage email verifier:
    1. Syntax Check
    2. DNS MX Record Validation (Unlimited, Free)
    3. SMTP Handshake & Catch-All Detection (Unlimited, Free)
    4. Hunter.io / Snov.io Free Credits (Optional Free API Tiers)
    """
    def __init__(self, quota_mgr: Optional[QuotaManager] = None):
        self.quota_mgr = quota_mgr
        self.mx_cache: Dict[str, Optional[str]] = {}
        self.catch_all_cache: Dict[str, bool] = {}

    def get_mx_record(self, domain: str) -> Optional[str]:
        """Resolves the lowest-preference (highest priority) MX host for domain."""
        if domain in self.mx_cache:
            return self.mx_cache[domain]

        try:
            answers = dns.resolver.resolve(domain, "MX", lifetime=5)
            # Sort by preference
            sorted_mx = sorted(answers, key=lambda r: r.preference)
            if sorted_mx:
                mx_host = str(sorted_mx[0].exchange).rstrip(".")
                self.mx_cache[domain] = mx_host
                return mx_host
        except Exception:
            pass

        self.mx_cache[domain] = None
        return None

    def is_catch_all(self, domain: str, mx_host: str) -> bool:
        """Tests whether the mail server accepts any non-existent random address."""
        if domain in self.catch_all_cache:
            return self.catch_all_cache[domain]

        test_email = f"leadfinder_probe_xyz999@{domain}"
        try:
            with smtplib.SMTP(mx_host, 25, timeout=7) as smtp:
                smtp.ehlo_or_helo_if_needed()
                smtp.mail("verify-probe@domain.com")
                code, _ = smtp.rcpt(test_email)
                # 250 means server accepts non-existent addresses -> Catch-All
                is_catchall = (code == 250)
                self.catch_all_cache[domain] = is_catchall
                return is_catchall
        except Exception:
            # If SMTP blocked or timeout, assume false or unknown
            return False

    def verify_via_smtp(self, email: str, domain: str) -> str:
        """
        Direct SMTP recipient check.
        Returns 'valid', 'invalid', 'catch-all', or 'risky'.
        """
        mx_host = self.get_mx_record(domain)
        if not mx_host:
            return "invalid"

        # Check if domain has catch-all enabled
        if self.is_catch_all(domain, mx_host):
            return "catch-all"

        try:
            with smtplib.SMTP(mx_host, 25, timeout=7) as smtp:
                smtp.ehlo_or_helo_if_needed()
                smtp.mail("verify-check@leadfinder.local")
                code, resp = smtp.rcpt(email)
                if code == 250:
                    return "valid"
                elif code in (550, 551, 552, 553, 554):
                    return "invalid"
                elif code in (450, 451, 452):
                    return "risky"
        except (socket.timeout, smtplib.SMTPConnectError, ConnectionRefusedError, OSError):
            # Port 25 frequently filtered by consumer ISPs; if MX exists, treat as risky
            return "risky"
        except Exception:
            return "risky"

        return "risky"

    def verify_via_hunter(self, email: str) -> Optional[str]:
        """Verify using Hunter.io free tier if key configured."""
        if not config.HUNTER_API_KEY:
            return None
        if self.quota_mgr and not self.quota_mgr.can_use("hunter"):
            return None

        url = "https://api.hunter.io/v2/email-verifier"
        params = {"email": email, "api_key": config.HUNTER_API_KEY}
        try:
            resp = requests.get(url, params=params, timeout=8)
            if self.quota_mgr:
                self.quota_mgr.record_usage("hunter", 1)
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                status = data.get("status")
                # Hunter returns: valid, invalid, accept_all, webmail, disposable, unknown
                if status == "valid":
                    return "valid"
                elif status == "accept_all":
                    return "catch-all"
                elif status == "invalid":
                    return "invalid"
                else:
                    return "risky"
        except Exception:
            pass

        return None

    def verify(self, email: str, domain: str) -> Tuple[str, str]:
        """
        Runs comprehensive validation.
        Returns: (status, method_used)
        Status: 'valid' | 'risky' | 'catch-all' | 'invalid'
        """
        # 1. Syntax check
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            return "invalid", "Syntax check failed"

        # 2. Check MX record
        mx = self.get_mx_record(domain)
        if not mx:
            return "invalid", f"No MX record for {domain}"

        # 3. Check via Hunter free API if available
        hunter_status = self.verify_via_hunter(email)
        if hunter_status:
            return hunter_status, "Hunter.io Free Tier"

        # 4. Check via SMTP handshake
        smtp_status = self.verify_via_smtp(email, domain)
        return smtp_status, "SMTP MX Handshake"

