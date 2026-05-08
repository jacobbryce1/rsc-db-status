"""
Central configuration for RSC Database Status Tool.
All settings, environment variables, and scale profiles.
"""
import os
from datetime import datetime

# ============================================================
# RSC CONNECTION
# ============================================================
RSC_DOMAIN = os.environ.get("RSC_DOMAIN", "your-account.my.rubrik.com")
RSC_CLIENT_ID = os.environ.get("RSC_CLIENT_ID", "")
RSC_CLIENT_SECRET = os.environ.get("RSC_CLIENT_SECRET", "")
RSC_BASE_URL = f"https://{RSC_DOMAIN}"
RSC_TOKEN_URL = f"{RSC_BASE_URL}/api/client_token"
RSC_GRAPHQL_URL = f"{RSC_BASE_URL}/api/graphql"

# ============================================================
# OUTPUT
# ============================================================
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
INTERMEDIATE_DIR = os.environ.get("DB_STATUS_WORK_DIR", "./db_status_work")
INTERMEDIATE_FILE = os.path.join(INTERMEDIATE_DIR, f"raw_fetch_{TIMESTAMP}.json")
EVENTS_FILE = os.path.join(INTERMEDIATE_DIR, f"events_{TIMESTAMP}.json")
OUTPUT_CSV = f"db_status_report_{TIMESTAMP}.csv"
OUTPUT_JSON = f"db_status_report_{TIMESTAMP}.json"
OUTPUT_HTML = f"db_status_report_{TIMESTAMP}.html"

# ============================================================
# BEHAVIOR
# ============================================================
PAGE_SIZE = 200
API_CALL_DELAY = 0.1
ENABLE_MSSQL_EVENT_CHECKS = True
STALE_SNAPSHOT_DAYS = 7
OFFLINE_SNAPSHOT_DAYS = 30
MISSED_SNAPSHOT_LOOKBACK_HOURS = 72

# ============================================================
# SCALE PROFILES
# ============================================================
SCALE_PROFILES = {
    "small": {
        "label": "Small (<1K)",
        "page_size": 200,
        "max_workers": 2,
        "batch_size": 50,
        "stream_to_disk": False,
        "event_checks": True,
        "rate_limit": 10,
    },
    "medium": {
        "label": "Medium (1K-5K)",
        "page_size": 500,
        "max_workers": 4,
        "batch_size": 100,
        "stream_to_disk": False,
        "event_checks": True,
        "rate_limit": 10,
    },
    "large": {
        "label": "Large (5K-10K)",
        "page_size": 1000,
        "max_workers": 8,
        "batch_size": 200,
        "stream_to_disk": False,
        "event_checks": True,
        "rate_limit": 12,
    },
    "xlarge": {
        "label": "XLarge (10K-50K)",
        "page_size": 1000,
        "max_workers": 12,
        "batch_size": 500,
        "stream_to_disk": True,
        "event_checks": True,
        "rate_limit": 15,
    },
    "xxlarge": {
        "label": "XXLarge (50K-100K+)",
        "page_size": 1000,
        "max_workers": 16,
        "batch_size": 1000,
        "stream_to_disk": True,
        "event_checks": False,
        "rate_limit": 15,
    },
}


def get_scale_profile(estimated_total: int) -> dict:
    """Select the appropriate scale profile based on estimated DB count."""
    if estimated_total < 1000:
        return SCALE_PROFILES["small"]
    elif estimated_total < 5000:
        return SCALE_PROFILES["medium"]
    elif estimated_total < 10000:
        return SCALE_PROFILES["large"]
    elif estimated_total < 50000:
        return SCALE_PROFILES["xlarge"]
    else:
        return SCALE_PROFILES["xxlarge"]
