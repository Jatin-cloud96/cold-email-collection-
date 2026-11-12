import json
from datetime import datetime
from pathlib import Path
from typing import Dict
import config

class QuotaManager:
    """
    Tracks and enforces daily limits for all third-party free tiers.
    Automatically resets counters every day at midnight.
    """
    def __init__(self, quota_file: Path = config.DAILY_QUOTA_PATH):
        self.quota_file = quota_file
        self.limits = {
            "linkedin_search": getattr(config, "LINKEDIN_DAILY_SEARCH_LIMIT", 20),
            "google_search": config.GOOGLE_SEARCH_DAILY_LIMIT,
            "hunter": config.HUNTER_DAILY_LIMIT,
            "snov": config.SNOV_DAILY_LIMIT,
            "batch_processed": config.DEFAULT_BATCH_SIZE,
        }
        self.data = self._load()

    def _today_str(self) -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def _load(self) -> Dict:
        today = self._today_str()
        if self.quota_file.exists():
            try:
                with open(self.quota_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("date") == today:
                        return data
            except Exception:
                pass
        
        # New day or corrupted file: reset counters
        fresh_data = {
            "date": today,
            "usage": {service: 0 for service in self.limits.keys()}
        }
        self._save(fresh_data)
        return fresh_data

    def _save(self, data: Dict = None):
        if data is None:
            data = self.data
        try:
            with open(self.quota_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[Warning] Failed to save quota data: {e}")

    def can_use(self, service: str) -> bool:
        """Returns True if today's quota for the service has not been exceeded."""
        today = self._today_str()
        if self.data.get("date") != today:
            self.data = self._load()
            
        current = self.data["usage"].get(service, 0)
        limit = self.limits.get(service, 100)
        return current < limit

    def record_usage(self, service: str, count: int = 1):
        """Records usage and saves state."""
        today = self._today_str()
        if self.data.get("date") != today:
            self.data = self._load()
            
        current = self.data["usage"].get(service, 0)
        self.data["usage"][service] = current + count
        self._save()

    def get_remaining(self, service: str) -> int:
        """Returns number of requests left for today."""
        today = self._today_str()
        if self.data.get("date") != today:
            self.data = self._load()
            
        current = self.data["usage"].get(service, 0)
        limit = self.limits.get(service, 0)
        return max(0, limit - current)

    def print_status(self):
        print(f"\n--- Daily Quota Status ({self.data.get('date')}) ---")
        for service, limit in self.limits.items():
            used = self.data["usage"].get(service, 0)
            remaining = max(0, limit - used)
            print(f"  * {service}: {used}/{limit} used ({remaining} remaining today)")
        print("--------------------------------------------------\n")

