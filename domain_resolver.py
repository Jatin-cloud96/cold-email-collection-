import json
import re
import urllib.parse
from pathlib import Path
from typing import Optional, Dict
import requests
import config

KNOWN_DOMAINS = {
    "tcs": "tcs.com",
    "tata consultancy services": "tcs.com",
    "infosys": "infosys.com",
    "wipro": "wipro.com",
    "hcl tech": "hcltech.com",
    "hcltech": "hcltech.com",
    "hcl technologies": "hcltech.com",
    "cognizant": "cognizant.com",
    "accenture": "accenture.com",
    "deloitte": "deloitte.com",
    "deloitte india": "deloitte.com",
    "ey": "ey.com",
    "ernst & young": "ey.com",
    "pwc": "pwc.com",
    "pricewaterhousecoopers": "pwc.com",
    "kpmg": "kpmg.com",
    "kpmg india": "kpmg.com",
    "mckinsey & company": "mckinsey.com",
    "mckinsey": "mckinsey.com",
    "boston consulting group": "bcg.com",
    "bcg": "bcg.com",
    "bain & company": "bain.com",
    "bain": "bain.com",
    "capgemini": "capgemini.com",
    "tech mahindra": "techmahindra.com",
    "l&t": "larsentoubro.com",
    "larsen & toubro": "larsentoubro.com",
    "lti": "ltimindtree.com",
    "ltimindtree": "ltimindtree.com",
    "mindtree": "ltimindtree.com",
    "flipkart": "flipkart.com",
    "zomato": "zomato.com",
    "swiggy": "swiggy.in",
    "paytm": "paytm.com",
    "ola": "olacabs.com",
    "razorpay": "razorpay.com",
    "cred": "cred.club",
    "amazon": "amazon.com",
    "google": "google.com",
    "microsoft": "microsoft.com",
    "ibm": "ibm.com",
    "oracle": "oracle.com",
    "sap": "sap.com",
    "cisco": "cisco.com"
}

class DomainResolver:
    """Resolves company names to primary website domains using free tools and caching."""
    def __init__(self, cache_file: Path = config.DOMAIN_CACHE_PATH):
        self.cache_file = cache_file
        self.cache: Dict[str, str] = self._load_cache()

    def _load_cache(self) -> Dict[str, str]:
        cache = dict(KNOWN_DOMAINS)
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    cache.update(json.load(f))
            except Exception:
                pass
        return cache

    def _save_cache(self):
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            print(f"[DomainResolver] Warning saving cache: {e}")

    def clean_company_name(self, name: str) -> str:
        """Removes legal suffixes and noise from company names."""
        cleaned = re.sub(r"\b(Pvt\.?|Private|Ltd\.?|Limited|Inc\.?|LLP|LLC|Corp\.?|Corporation|India|Technologies|Services)\b", "", name, flags=re.IGNORECASE)
        cleaned = re.sub(r"[^\w\s&]", "", cleaned)
        return " ".join(cleaned.split()).strip()

    def resolve(self, company_name: str) -> Optional[str]:
        if not company_name:
            return None

        key = company_name.lower().strip()
        if key in self.cache:
            return self.cache[key]

        cleaned = self.clean_company_name(company_name).lower()
        if cleaned in self.cache:
            domain = self.cache[cleaned]
            self.cache[key] = domain
            self._save_cache()
            return domain

        # Strategy 1: Clearbit free autocomplete API (100% free, no auth)
        domain = self._query_clearbit(cleaned or company_name)
        if domain:
            self.cache[key] = domain
            self._save_cache()
            return domain

        # Strategy 2: DuckDuckGo Instant Answer / HTML search fallback
        domain = self._query_duckduckgo_domain(company_name)
        if domain:
            self.cache[key] = domain
            self._save_cache()
            return domain

        # Strategy 3: Normalized guess e.g. "My Company" -> "mycompany.com"
        normalized = re.sub(r"[^a-zA-Z0-9]", "", cleaned)
        if normalized:
            guess = f"{normalized}.com"
            self.cache[key] = guess
            self._save_cache()
            return guess

        return None

    def _query_clearbit(self, query: str) -> Optional[str]:
        url = "https://autocomplete.clearbit.com/v1/companies/suggest"
        try:
            resp = requests.get(url, params={"query": query}, timeout=5)
            if resp.status_code == 200:
                results = resp.json()
                if results and isinstance(results, list):
                    first_match = results[0]
                    domain = first_match.get("domain")
                    if domain:
                        return domain.lower().strip()
        except Exception:
            pass
        return None

    def _query_duckduckgo_domain(self, company_name: str) -> Optional[str]:
        """Free search for official website domain."""
        query = f"{company_name} official website"
        url = "https://html.duckduckgo.com/html/"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        try:
            resp = requests.post(url, data={"q": query}, headers=headers, timeout=6)
            if resp.status_code == 200:
                # Find result URLs
                links = re.findall(r'class="result__url"[^>]*href="([^"]+)"', resp.text)
                if not links:
                    links = re.findall(r'href="//duckduckgo\.com/l/\?uddg=([^"&]+)', resp.text)
                for link in links:
                    unquoted = urllib.parse.unquote(link)
                    match = re.search(r'https?://(?:www\.)?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', unquoted)
                    if match:
                        found_domain = match.group(1).lower()
                        # Avoid search engines or social media
                        if not any(x in found_domain for x in ["duckduckgo", "google", "linkedin", "wikipedia", "facebook", "twitter", "glassdoor", "ambitionbox"]):
                            return found_domain
        except Exception:
            pass
        return None

