import sys
import argparse
import logging
from datetime import datetime
from typing import List, Dict

import config
from quota_manager import QuotaManager
from search_providers import GoogleSearchProvider, ApolloSearchProvider, LinkedInExportProvider, LeadCandidate
from linkedin_scraper import LinkedInBrowserScraper
from domain_resolver import DomainResolver
from email_generator import EmailGenerator
from verifier import EmailVerifier
from excel_manager import ExcelManager

# Configure Logging
log_file = config.CACHE_DIR / "lead_finder.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("LeadFinder")

class LeadFinderWorkflow:
    def __init__(self, batch_size: int = config.DEFAULT_BATCH_SIZE, strict_valid_only: bool = True):
        self.batch_size = batch_size
        self.strict_valid_only = strict_valid_only
        self.quota_mgr = QuotaManager()
        self.domain_resolver = DomainResolver()
        self.email_generator = EmailGenerator(self.quota_mgr)
        self.verifier = EmailVerifier(self.quota_mgr)
        self.excel_mgr = ExcelManager()
        self.google_search = GoogleSearchProvider(self.quota_mgr)
        self.apollo_search = ApolloSearchProvider(self.quota_mgr)

    def run(self, titles: List[str] = None, location: str = "India", csv_path: str = None, use_linkedin: bool = False, headless: bool = False) -> int:
        titles = titles or config.TARGET_TITLES
        logger.info(f"Starting Lead Finder Run | Target Titles: {titles} | Location: {location} | Batch Size: {self.batch_size}")
        self.quota_mgr.print_status()

        candidates: List[LeadCandidate] = []

        # Step 1: Collect candidates
        # Method 0: Direct LinkedIn Login & Browser Search
        should_use_linkedin = use_linkedin or bool(config.LINKEDIN_EMAIL or config.LINKEDIN_LI_AT)
        if should_use_linkedin and len(candidates) < self.batch_size:
            logger.info("Initializing direct LinkedIn browser automation...")
            scraper = LinkedInBrowserScraper(headless=headless)
            try:
                logged_in = scraper.login(
                    email=config.LINKEDIN_EMAIL,
                    password=config.LINKEDIN_PASSWORD,
                    li_at_cookie=config.LINKEDIN_LI_AT
                )
                if logged_in:
                    for title in titles:
                        if len(candidates) >= self.batch_size:
                            break
                        if not self.quota_mgr.can_use("linkedin_search"):
                            logger.warning("Daily LinkedIn search safety limit reached. Will resume next day.")
                            break
                        needed = self.batch_size - len(candidates)
                        li_leads = scraper.search_people(title=title, location=location, max_results=needed)
                        candidates.extend(li_leads)
                        self.quota_mgr.record_usage("linkedin_search", 1)
                else:
                    logger.warning("[LinkedIn] Could not complete login. Falling back to alternative providers.")
            except Exception as e:
                logger.error(f"[LinkedIn] Browser search error: {e}", exc_info=True)
            finally:
                scraper.close()

        # Method A: User provided LinkedIn export CSV
        if csv_path:
            logger.info(f"Reading candidates from LinkedIn export: {csv_path}")
            csv_candidates = LinkedInExportProvider.read_csv(csv_path, titles=titles)
            candidates.extend(csv_candidates)
            logger.info(f"Loaded {len(csv_candidates)} matching candidates from CSV.")

        # Method B: Apollo search if API key configured
        if config.APOLLO_API_KEY and len(candidates) < self.batch_size:
            for title in titles:
                if len(candidates) >= self.batch_size:
                    break
                apollo_leads = self.apollo_search.search_leads(title=title, location=location, max_results=5)
                candidates.extend(apollo_leads)

        # Method C: Google Programmable Search API
        if config.GOOGLE_API_KEY and len(candidates) < self.batch_size:
            for title in titles:
                if len(candidates) >= self.batch_size:
                    break
                if not self.quota_mgr.can_use("google_search"):
                    logger.warning("Daily Google Search quota limit reached. Will resume next day.")
                    break
                google_leads = self.google_search.search_leads(title=title, location=location, max_results=5)
                candidates.extend(google_leads)

        if not candidates:
            if not config.GOOGLE_API_KEY and not csv_path and not config.APOLLO_API_KEY:
                logger.warning(
                    "\n[Notice] No active search provider configured!\n"
                    "To find leads automatically, please add your free GOOGLE_API_KEY and GOOGLE_CSE_ID to .env,\n"
                    "or import your LinkedIn Connections data export using: --import-csv <path-to-Connections.csv>\n"
                )
            else:
                logger.info("No new candidates found matching criteria in this batch.")
            return 0

        logger.info(f"Total raw candidates collected: {len(candidates)}")

        valid_leads_to_save: List[Dict[str, str]] = []
        processed_count = 0

        # Step 2 to Step 5: Process each candidate with error isolation
        for candidate in candidates:
            if processed_count >= self.batch_size:
                logger.info(f"Reached batch limit of {self.batch_size} leads for this run.")
                break

            # Error Handling Constraint: Never re-check a person already in the sheet
            if self.excel_mgr.is_person_seen(candidate.name, candidate.company):
                logger.info(f"Skipping already recorded person: {candidate.name} at {candidate.company}")
                continue

            try:
                logger.info(f"\nProcessing [{processed_count + 1}/{self.batch_size}]: {candidate.name} ({candidate.title}) @ {candidate.company}")

                # Step 2: Resolve Company Domain
                domain = self.domain_resolver.resolve(candidate.company)
                if not domain:
                    logger.warning(f"Could not resolve website domain for company '{candidate.company}'. Skipping.")
                    continue
                logger.info(f"  -> Domain: {domain}")

                # Step 3: Generate Email Candidates
                email_candidates = self.email_generator.generate_candidates(candidate.name, domain)
                if not email_candidates:
                    logger.warning(f"  -> Could not generate email candidates for '{candidate.name}'. Skipping.")
                    continue

                best_email = None
                best_status = None
                method_used = None

                # Step 4: Verify email candidates
                for email_candidate in email_candidates:
                    # Skip if email already seen in sheet
                    if self.excel_mgr.is_email_seen(email_candidate):
                        continue

                    status, method = self.verifier.verify(email_candidate, domain)
                    logger.info(f"  -> Probed: {email_candidate} => [{status}] ({method})")

                    if status == "valid":
                        best_email = email_candidate
                        best_status = "valid"
                        method_used = method
                        break # Stop on first confirmed valid email
                    elif status in ("risky", "catch-all") and not best_email:
                        best_email = email_candidate
                        best_status = status
                        method_used = method

                # Step 5: Clean & Filter
                # Requirement: "remove duplicates and every address not marked valid"
                should_save = False
                if best_email:
                    if self.strict_valid_only and best_status == "valid":
                        should_save = True
                    elif not self.strict_valid_only and best_status in ("valid", "risky", "catch-all"):
                        should_save = True

                if should_save:
                    lead_row = {
                        "Name": candidate.name,
                        "Title": candidate.title,
                        "Company": candidate.company,
                        "Domain": domain,
                        "Email": best_email,
                        "Verification status": best_status,
                        "Source": candidate.source,
                        "Date found": datetime.now().strftime("%Y-%m-%d")
                    }
                    valid_leads_to_save.append(lead_row)
                    logger.info(f"  ==> ACCEPTED & SAVED: {best_email} [{best_status}]")
                else:
                    logger.info(f"  ==> DISCARDED: No deliverable valid email confirmed.")
                    # Mark person seen so we don't repeat the lookup tomorrow
                    self.excel_mgr.mark_seen(candidate.name, candidate.company)

                processed_count += 1
                self.quota_mgr.record_usage("batch_processed", 1)

            except Exception as e:
                # Error Handling Constraint: Skip and log rows that fail; never stop the whole run
                logger.error(f"Error processing candidate {candidate.name}: {e}", exc_info=True)
                continue

        # Step 6: Save to Excel
        if valid_leads_to_save:
            added = self.excel_mgr.append_leads(valid_leads_to_save)
            logger.info(f"\nSuccessfully written {added} new verified leads to Excel: {self.excel_mgr.excel_path}")
        else:
            logger.info("\nNo new valid leads to append in this run.")

        self.quota_mgr.print_status()
        return len(valid_leads_to_save)


def main():
    parser = argparse.ArgumentParser(description="India Professional Email Lead Finder")
    parser.add_argument("--titles", nargs="+", help="Target job titles (e.g., Analyst Consultant 'Project Manager')")
    parser.add_argument("--location", default="India", help="Target location (default: India)")
    parser.add_argument("--batch-size", type=int, default=config.DEFAULT_BATCH_SIZE, help="Maximum candidates to process today")
    parser.add_argument("--use-linkedin", action="store_true", help="Log in directly to LinkedIn in Chrome to search leads")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode (background)")
    parser.add_argument("--import-csv", help="Path to LinkedIn data export Connections.csv")
    parser.add_argument("--allow-risky", action="store_true", help="Include risky and catch-all emails in output (default: strict valid only)")
    parser.add_argument("--status", action="store_true", help="Print today's quota usage and exit")

    args = parser.parse_args()

    if args.status:
        qm = QuotaManager()
        qm.print_status()
        return

    workflow = LeadFinderWorkflow(
        batch_size=args.batch_size,
        strict_valid_only=not args.allow_risky
    )
    workflow.run(
        titles=args.titles,
        location=args.location,
        csv_path=args.import_csv,
        use_linkedin=args.use_linkedin,
        headless=args.headless
    )

if __name__ == "__main__":
    main()

