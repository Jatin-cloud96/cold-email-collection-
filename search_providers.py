import os
import re
import csv
import urllib.parse
from typing import List, Dict, Optional
import requests
import config
from quota_manager import QuotaManager

class LeadCandidate:
    def __init__(self, name: str, title: str, company: str, source: str, profile_url: str = ""):
        self.name = name.strip()
        self.title = title.strip()
        self.company = company.strip()
        self.source = source.strip()
        self.profile_url = profile_url.strip()

    def to_dict(self):
        return {
            "name": self.name,
            "title": self.title,
            "company": self.company,
            "source": self.source,
            "profile_url": self.profile_url
        }

    def __repr__(self):
        return f"<LeadCandidate {self.name} | {self.title} at {self.company}>"


def parse_linkedin_serp_title(title_text: str) -> Optional[Dict[str, str]]:
    """
    Parses typical LinkedIn SERP title formats:
    - 'First Last - Senior Consultant - McKinsey & Company | LinkedIn'
    - 'First Last - Project Manager at Tata Consultancy Services | LinkedIn'
    - 'First Last - Business Analyst - Deloitte India | LinkedIn'
    """
    cleaned = title_text.replace(" | LinkedIn", "").replace(" - LinkedIn", "").strip()
    
    # Try pattern: Name - Title - Company
    parts = [p.strip() for p in cleaned.split(" - ") if p.strip()]
    if len(parts) >= 3:
        name = parts[0]
        job_title = parts[1]
        company = " - ".join(parts[2:])
        return {"name": name, "title": job_title, "company": company}
    
    # Try pattern: Name - Title at Company
    if len(parts) == 2:
        name = parts[0]
        rem = parts[1]
        if " at " in rem:
            sub = rem.split(" at ", 1)
            return {"name": name, "title": sub[0].strip(), "company": sub[1].strip()}
        elif " @ " in rem:
            sub = rem.split(" @ ", 1)
            return {"name": name, "title": sub[0].strip(), "company": sub[1].strip()}
            
    return None


class GoogleSearchProvider:
    """Uses Google Programmable Search Engine API (100 free queries/day)."""
    def __init__(self, quota_mgr: QuotaManager):
        self.quota_mgr = quota_mgr
        self.api_key = config.GOOGLE_API_KEY
        self.cse_id = config.GOOGLE_CSE_ID

    def search_leads(self, title: str, location: str = "India", max_results: int = 10) -> List[LeadCandidate]:
        candidates = []
        if not self.api_key or not self.cse_id:
            print("[GoogleSearch] Skipped: GOOGLE_API_KEY or GOOGLE_CSE_ID not configured.")
            return candidates

        if not self.quota_mgr.can_use("google_search"):
            print("[GoogleSearch] Daily search quota reached. Stopping search.")
            return candidates

        query = f'site:linkedin.com/in "{location}" "{title}"'
        endpoint = "https://www.googleapis.com/customsearch/v1"
        
        # Paginate in batches of 10
        start = 1
        while len(candidates) < max_results and self.quota_mgr.can_use("google_search"):
            params = {
                "key": self.api_key,
                "cx": self.cse_id,
                "q": query,
                "num": min(10, max_results - len(candidates)),
                "start": start
            }
            try:
                resp = requests.get(endpoint, params=params, timeout=10)
                self.quota_mgr.record_usage("google_search", 1)
                
                if resp.status_code == 429:
                    print("[GoogleSearch] 429 Rate limited. Halting search for today.")
                    break
                elif resp.status_code != 200:
                    print(f"[GoogleSearch] Error {resp.status_code}: {resp.text[:100]}")
                    break

                data = resp.json()
                items = data.get("items", [])
                if not items:
                    break

                for item in items:
                    title_text = item.get("title", "")
                    parsed = parse_linkedin_serp_title(title_text)
                    if parsed and len(parsed["name"].split()) >= 2:
                        candidates.append(LeadCandidate(
                            name=parsed["name"],
                            title=parsed["title"],
                            company=parsed["company"],
                            source="Google PSE",
                            profile_url=item.get("link", "")
                        ))

                start += len(items)
                if "nextPage" not in data.get("queries", {}):
                    break
            except Exception as e:
                print(f"[GoogleSearch] Request error: {e}")
                break

        return candidates


class ApolloSearchProvider:
    """Searches people via Apollo.io free search API if key is present."""
    def __init__(self, quota_mgr: QuotaManager):
        self.quota_mgr = quota_mgr
        self.api_key = config.APOLLO_API_KEY

    def search_leads(self, title: str, location: str = "India", max_results: int = 10) -> List[LeadCandidate]:
        candidates = []
        if not self.api_key:
            return candidates

        url = "https://api.apollo.io/v1/mixed_people/search"
        payload = {
            "api_key": self.api_key,
            "q_organization_domains": "",
            "page": 1,
            "per_page": min(max_results, 10),
            "person_titles": [title],
            "person_locations": [location]
        }
        try:
            resp = requests.post(url, json=payload, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                for person in data.get("people", []):
                    name = person.get("name") or f"{person.get('first_name', '')} {person.get('last_name', '')}".strip()
                    org = person.get("organization", {}) or {}
                    company_name = org.get("name") or person.get("headline", "")
                    job_title = person.get("title", title)
                    if name and company_name:
                        candidates.append(LeadCandidate(
                            name=name,
                            title=job_title,
                            company=company_name,
                            source="Apollo Free Search",
                            profile_url=person.get("linkedin_url", "")
                        ))
        except Exception as e:
            print(f"[ApolloSearch] Error: {e}")

        return candidates


class LinkedInExportProvider:
    """Reads connections from user's official LinkedIn archive (Connections.csv)."""
    @staticmethod
    def read_csv(csv_path: str, titles: List[str] = None) -> List[LeadCandidate]:
        candidates = []
        if not os.path.exists(csv_path):
            return candidates

        titles_lower = [t.lower() for t in (titles or config.TARGET_TITLES)]

        try:
            with open(csv_path, mode="r", encoding="utf-8-sig", errors="replace") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    first = row.get("First Name", "").strip()
                    last = row.get("Last Name", "").strip()
                    company = row.get("Company", "").strip()
                    position = row.get("Position", "").strip()
                    url = row.get("URL", "").strip()

                    if not first or not company or not position:
                        continue

                    # Filter by target titles if provided
                    matches_title = True
                    if titles_lower:
                        matches_title = any(t in position.lower() for t in titles_lower)

                    if matches_title:
                        candidates.append(LeadCandidate(
                            name=f"{first} {last}",
                            title=position,
                            company=company,
                            source="LinkedIn Export CSV",
                            profile_url=url
                        ))
        except Exception as e:
            print(f"[LinkedInExport] Error reading CSV: {e}")

        return candidates

