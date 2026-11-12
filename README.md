# India Professional Email Lead Finder (Excel Output)

An automated, quota-aware lead finder that builds a clean, verified list of corporate work emails for **Analysts**, **Consultants**, and **Project Managers** at companies in India, saved directly into a formatted Excel spreadsheet.

---

## What's New: Direct LinkedIn Login & Search

You can now log directly into LinkedIn to search and scrape leads using automated browser navigation:
- **Persistent Chrome Session**: Log in once, and the session is saved in `cache/chrome_profile`. Future runs automatically reuse your authenticated session without asking for credentials or triggering 2FA.
- **Two Login Options**:
  1. **Direct Credentials (`LINKEDIN_EMAIL` & `LINKEDIN_PASSWORD`)**: Auto-fills the login form.
  2. **Session Cookie (`LINKEDIN_LI_AT`) [Safest]**: Injects your `li_at` browser cookie to bypass login forms and 2FA completely.
- **Stealth & Safety**: Employs humanized randomized pauses (3-6s) and daily search limits to protect your personal account from restrictions.

---

## Directory Structure

```text
india_email_lead_finder/
├── config.py                 # Core configuration, default titles, and paths
├── .env.example              # Credentials & API keys template (copy to .env)
├── linkedin_scraper.py       # Selenium Chrome automation for direct LinkedIn login & search
├── quota_manager.py          # Daily quota tracker and daily midnight reset
├── search_providers.py       # Google Search, Apollo, and LinkedIn CSV reader
├── domain_resolver.py        # Clearbit free autocomplete + local domain cache
├── email_generator.py        # Generates corporate permutations and matches patterns
├── verifier.py               # MX record validator, SMTP direct handshake, Hunter fallback
├── excel_manager.py          # Excel sheet creator, deduplicator, and formatter
├── lead_finder.py            # Main CLI runner
├── sample_linkedin_export.csv# Sample test file
├── schedule_daily.bat        # Batch launcher for scheduler
├── install_schedule.ps1      # One-click Windows Task Scheduler installer
├── cache/                    # Local cache (Chrome profile, quotas, domains, seen contacts)
└── output/
    └── india_leads.xlsx      # Output Excel file
```

---

## How to Use Direct LinkedIn Login

### Step 1: Configure Your Credentials in `.env`
Create a `.env` file from `.env.example`:
```bash
cp .env.example .env
```
Choose one of the two methods:

#### Method A: Using `li_at` Session Cookie (Recommended & Safest)
1. Open LinkedIn in Chrome and log in normally.
2. Press `F12` to open DevTools &rarr; go to the **Application** tab &rarr; expand **Cookies** &rarr; `https://www.linkedin.com`.
3. Find the cookie named **`li_at`** and copy its value.
4. In `.env`:
   ```env
   LINKEDIN_LI_AT=AQEDAQE...
   ```

#### Method B: Using Email & Password
In `.env`:
```env
LINKEDIN_EMAIL=your_email@domain.com
LINKEDIN_PASSWORD=your_password
```
*(If LinkedIn presents a 2FA prompt or security challenge on the first login, a visible Chrome window will wait for you to approve it, and then your session is saved permanently in `cache/chrome_profile`)*.

---

## Running the Lead Finder

### 1. Run Live LinkedIn Search
```powershell
python lead_finder.py --use-linkedin --batch-size 15
```

### 2. Run Live LinkedIn Search in Background (Headless)
```powershell
python lead_finder.py --use-linkedin --headless --batch-size 15
```

### 3. Run with Custom Job Titles or Location
```powershell
python lead_finder.py --use-linkedin --titles "Analyst" "Consultant" "Project Manager" --location "Mumbai"
```

### 4. Check Today's Quota Status
```powershell
python lead_finder.py --status
```

---

## How Verification & Deduplication Works

1. **Find People**: Extracted live from LinkedIn Search results in India.
2. **Find Domains**: Auto-resolves company website domains via Clearbit API & local cache.
3. **Generate Permutations**: Constructs `first.last@domain`, `firstlast@domain`, `flast@domain`, `first@domain`, etc.
4. **MX & SMTP Handshake**: Probes DNS MX records and conducts direct SMTP handshake with catch-all detection.
5. **Clean & Save**: Checks previous entries in [`output/india_leads.xlsx`](output/india_leads.xlsx) &mdash; **never re-checks a person already saved**. Appends new verified leads with color-coded formatting.

---

## Daily Schedule Automation

To run the workflow every morning at 9:00 AM automatically via Windows Task Scheduler:
```powershell
.\install_schedule.ps1
```
