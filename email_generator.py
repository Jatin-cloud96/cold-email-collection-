import re
import unicodedata
from typing import List, Dict, Tuple, Optional
import requests
import config
from quota_manager import QuotaManager

PREFIXES = {"dr", "dr.", "ca", "mr", "mr.", "ms", "ms.", "mrs", "mrs.", "prof", "prof.", "adv", "adv."}

class EmailGenerator:
    """Generates standard corporate email permutations for a person and domain."""
    def __init__(self, quota_mgr: Optional[QuotaManager] = None):
        self.quota_mgr = quota_mgr
        self.domain_patterns: Dict[str, str] = {}  # domain -> e.g. "{first}.{last}"

    def clean_name(self, full_name: str) -> Tuple[str, str]:
        """Splits full name into clean first name and last name, stripping titles."""
        # Normalize accents
        normalized = unicodedata.normalize('NFKD', full_name).encode('ASCII', 'ignore').decode('utf-8')
        # Remove non-alphabetical characters except space and hyphens
        cleaned = re.sub(r"[^a-zA-Z\s-]", "", normalized)
        tokens = [w for w in cleaned.split() if w.strip()]
        
        # Filter out common Indian/Global professional prefixes
        while tokens and tokens[0].lower() in PREFIXES:
            tokens.pop(0)

        if not tokens:
            return "", ""
        if len(tokens) == 1:
            return tokens[0].lower(), ""
        
        first = tokens[0].lower()
        last = tokens[-1].lower()
        return first, last

    def detect_domain_pattern(self, domain: str) -> Optional[str]:
        """If Hunter API key is available, check known pattern for the company domain."""
        if domain in self.domain_patterns:
            return self.domain_patterns[domain]

        if not config.HUNTER_API_KEY or (self.quota_mgr and not self.quota_mgr.can_use("hunter")):
            return None

        url = "https://api.hunter.io/v2/domain-search"
        params = {"domain": domain, "api_key": config.HUNTER_API_KEY}
        try:
            resp = requests.get(url, params=params, timeout=5)
            if self.quota_mgr:
                self.quota_mgr.record_usage("hunter", 1)
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                pattern = data.get("pattern")
                if pattern:
                    # Hunter pattern format e.g. "{first}.{last}"
                    self.domain_patterns[domain] = pattern
                    return pattern
        except Exception:
            pass

        return None

    def generate_candidates(self, full_name: str, domain: str) -> List[str]:
        """
        Generates candidate email addresses.
        If a corporate pattern is detected, it is placed first.
        """
        first, last = self.clean_name(full_name)
        if not first or not domain:
            return []

        f = first[0] if first else ""
        l = last[0] if last else ""

        context = {
            "first": first,
            "last": last,
            "f": f,
            "l": l,
            "domain": domain
        }

        candidates = []

        # Check if known pattern exists
        detected_pattern = self.detect_domain_pattern(domain)
        if detected_pattern:
            try:
                candidate = detected_pattern.format(**context)
                if "@" in candidate:
                    candidates.append(candidate)
            except Exception:
                pass

        # Standard permutations
        if last:
            defaults = [
                f"{first}.{last}@{domain}",
                f"{first}{last}@{domain}",
                f"{f}{last}@{domain}",
                f"{first}@{domain}",
                f"{first}_{last}@{domain}",
                f"{last}.{first}@{domain}",
            ]
        else:
            defaults = [f"{first}@{domain}"]

        for email in defaults:
            if email not in candidates:
                candidates.append(email)

        return candidates

