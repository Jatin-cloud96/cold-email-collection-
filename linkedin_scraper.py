import os
import time
import random
import urllib.parse
from typing import List, Optional
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import config
from search_providers import LeadCandidate, parse_linkedin_serp_title

# LinkedIn India Geo URN
INDIA_GEO_URN = "102713980"

class LinkedInBrowserScraper:
    """
    Automated LinkedIn scraper using Selenium with persistent Chrome profile.
    Maintains user login session across runs to avoid repeated 2FA/checkpoints.
    """
    def __init__(self, headless: bool = False, profile_dir: Path = None):
        self.headless = headless
        self.profile_dir = profile_dir or (config.CACHE_DIR / "chrome_profile")
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.driver: Optional[webdriver.Chrome] = None

    def _init_driver(self):
        if self.driver:
            return

        chrome_options = Options()
        # Use dedicated persistent profile so session cookies persist
        chrome_options.add_argument(f"--user-data-dir={self.profile_dir}")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        # Anti-bot detection stealth flags
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

        if self.headless:
            chrome_options.add_argument("--headless=new")

        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    def is_logged_in(self) -> bool:
        """Checks if the current browser session is logged into LinkedIn."""
        self._init_driver()
        self.driver.get("https://www.linkedin.com/feed/")
        time.sleep(3)
        current_url = self.driver.current_url.lower()
        return "feed" in current_url or "mynetwork" in current_url

    def login(self, email: str = "", password: str = "", li_at_cookie: str = ""):
        """
        Logs into LinkedIn:
        1. If li_at cookie provided, injects cookie directly.
        2. If email/password provided, fills login form.
        3. If security checkpoint / 2FA appears, waits for user in visible browser.
        """
        self._init_driver()
        
        # Method 1: li_at session cookie injection
        if li_at_cookie:
            print("[LinkedIn] Injecting session cookie li_at...")
            self.driver.get("https://www.linkedin.com")
            time.sleep(2)
            self.driver.add_cookie({
                "name": "li_at",
                "value": li_at_cookie.strip(),
                "domain": ".linkedin.com",
                "path": "/"
            })
            self.driver.get("https://www.linkedin.com/feed/")
            time.sleep(3)
            if self.is_logged_in():
                print("[LinkedIn] Session cookie login successful!")
                return True

        if self.is_logged_in():
            print("[LinkedIn] Already logged in via saved Chrome profile session.")
            return True

        # Method 2: Standard Login
        print("[LinkedIn] Navigating to login page...")
        self.driver.get("https://www.linkedin.com/login")
        time.sleep(2)

        email = email or os.getenv("LINKEDIN_EMAIL", "")
        password = password or os.getenv("LINKEDIN_PASSWORD", "")

        if email and password:
            try:
                username_field = self.driver.find_element(By.ID, "username")
                password_field = self.driver.find_element(By.ID, "password")
                username_field.clear()
                username_field.send_keys(email)
                time.sleep(1)
                password_field.clear()
                password_field.send_keys(password)
                time.sleep(1)
                login_btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                login_btn.click()
                print("[LinkedIn] Submitted login credentials.")
            except Exception as e:
                print(f"[LinkedIn] Autofill error: {e}")

        # Wait for user to be on feed (handles 2FA/verification checkpoints if required)
        print("[LinkedIn] Waiting for feed (if a 2FA code or checkpoint is shown, please complete it in the browser)...")
        wait = WebDriverWait(self.driver, 120)
        try:
            wait.until(lambda d: "feed" in d.current_url.lower() or "checkpoint" not in d.current_url.lower())
            time.sleep(3)
            if self.is_logged_in():
                print("[LinkedIn] Login confirmed! Session saved to profile.")
                return True
        except Exception:
            pass

        return self.is_logged_in()

    def search_people(self, title: str, location: str = "India", max_results: int = 10) -> List[LeadCandidate]:
        """
        Executes an authenticated LinkedIn People Search and extracts candidate cards.
        """
        if not self.is_logged_in():
            print("[LinkedIn] Not logged in. Please call login() first.")
            return []

        candidates = []
        encoded_title = urllib.parse.quote(title)
        
        # Build search URL with India geo filter
        search_url = f'https://www.linkedin.com/search/results/people/?keywords={encoded_title}&geoUrn=["{INDIA_GEO_URN}"]&origin=FACETED_SEARCH'
        print(f"[LinkedIn] Searching: {title} in {location}...")
        self.driver.get(search_url)
        time.sleep(random.uniform(4, 6))

        # Scroll to load full page of results
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
        time.sleep(1.5)
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

        # Result card selectors
        result_cards = self.driver.find_elements(By.CSS_SELECTOR, "li.reusable-search__result-container, div.entity-result")
        print(f"[LinkedIn] Found {len(result_cards)} profile cards on page.")

        for card in result_cards:
            if len(candidates) >= max_results:
                break
            try:
                # Extract Name and Profile URL
                title_elem = card.find_elements(By.CSS_SELECTOR, "span.entity-result__title-text a, a.app-aware-link")
                if not title_elem:
                    continue
                
                raw_name = title_elem[0].text.strip()
                # Remove 'View profile' or extra text
                name = raw_name.split("\n")[0].strip()
                # Ignore 'LinkedIn Member' (out of network)
                if not name or "LinkedIn Member" in name:
                    continue

                profile_url = title_elem[0].get_attribute("href") or ""
                # Strip tracking parameters
                profile_url = profile_url.split("?")[0]

                # Extract headline/role and company
                subtitle_elems = card.find_elements(By.CSS_SELECTOR, "div.entity-result__primary-subtitle")
                headline = subtitle_elems[0].text.strip() if subtitle_elems else ""

                # Extract secondary/location
                secondary_elems = card.find_elements(By.CSS_SELECTOR, "div.entity-result__secondary-subtitle")
                loc_text = secondary_elems[0].text.strip() if secondary_elems else ""

                # Parse company and title from headline (e.g. 'Senior Consultant at Deloitte')
                parsed_title = title
                parsed_company = ""
                if " at " in headline:
                    parts = headline.split(" at ", 1)
                    parsed_title = parts[0].strip()
                    parsed_company = parts[1].strip()
                elif " @ " in headline:
                    parts = headline.split(" @ ", 1)
                    parsed_title = parts[0].strip()
                    parsed_company = parts[1].strip()
                elif " - " in headline:
                    parts = headline.split(" - ", 1)
                    parsed_title = parts[0].strip()
                    parsed_company = parts[1].strip()
                else:
                    parsed_company = headline

                # Clean up company
                parsed_company = parsed_company.split("\n")[0].strip()

                if name and parsed_company:
                    candidates.append(LeadCandidate(
                        name=name,
                        title=parsed_title,
                        company=parsed_company,
                        source="LinkedIn Live Search",
                        profile_url=profile_url
                    ))
                    print(f"  * Found: {name} | {parsed_title} at {parsed_company}")

            except Exception as e:
                continue

        # Humanized delay before next action
        time.sleep(random.uniform(2, 4))
        return candidates

    def close(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

