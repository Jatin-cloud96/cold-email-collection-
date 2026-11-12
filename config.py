import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / "cache"
OUTPUT_DIR = BASE_DIR / "output"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Excel Output
EXCEL_OUTPUT_PATH = OUTPUT_DIR / "india_leads.xlsx"

# Load .env file automatically
env_file = BASE_DIR / ".env"
if env_file.exists():
    try:
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k and k not in os.environ:
                        os.environ[k] = v
    except Exception:
        pass

# Also load from Streamlit Cloud Secrets if running in cloud
try:
    import streamlit as st
    if hasattr(st, "secrets"):
        for k, v in st.secrets.items():
            if isinstance(v, (str, int, float)) and str(k) not in os.environ:
                os.environ[str(k)] = str(v)
except Exception:
    pass

# State & Cache Files
SEEN_LEADS_PATH = CACHE_DIR / "seen_leads.json"
DAILY_QUOTA_PATH = CACHE_DIR / "quota_usage.json"
DOMAIN_CACHE_PATH = CACHE_DIR / "domain_cache.json"

# Search Parameters
TARGET_TITLES = [
    "Analyst",
    "Consultant",
    "Project Manager",
    "Senior Analyst",
    "Senior Consultant",
    "IT Project Manager"
]
TARGET_LOCATION = "India"

# Free Tier Daily Limits (Prevent exceeding free quotas)
# Google Programmable Search allows 100 free requests per day
GOOGLE_SEARCH_DAILY_LIMIT = 50
# Hunter.io free tier is 25 free credits per month
HUNTER_DAILY_LIMIT = 5
# Snov.io free tier is 50 free credits per month
SNOV_DAILY_LIMIT = 5
# Overall batch limit per daily run
DEFAULT_BATCH_SIZE = 15

# LinkedIn Automation Settings
LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL", "")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD", "")
LINKEDIN_LI_AT = os.getenv("LINKEDIN_LI_AT", "")
LINKEDIN_DAILY_SEARCH_LIMIT = 20

# API Keys (Loaded from environment or .env file)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "")
HUNTER_API_KEY = os.getenv("HUNTER_API_KEY", "")
SNOV_API_KEY = os.getenv("SNOV_API_KEY", "")
SNOV_API_SECRET = os.getenv("SNOV_API_SECRET", "")
APOLLO_API_KEY = os.getenv("APOLLO_API_KEY", "")

# Email Permutation Patterns
# {first}, {last}, {f}, {l}
EMAIL_PATTERNS = [
    "{first}.{last}@{domain}",
    "{first}{last}@{domain}",
    "{f}{last}@{domain}",
    "{first}@{domain}",
    "{first}_{last}@{domain}",
    "{last}.{first}@{domain}",
]

