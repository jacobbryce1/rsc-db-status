"""
Central configuration for RSC Database Status Tool.
SECURITY F-07: RSC_DOMAIN validated against strict regex at import time.
"""
import os
import re
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

# ============================================================
# RSC CONNECTION
# ============================================================
RSC_DOMAIN = os.environ.get("RSC_DOMAIN", "").strip()
RSC_CLIENT_ID = os.environ.get("RSC_CLIENT_ID", "").strip()
RSC_CLIENT_SECRET = os.environ.get("RSC_CLIENT_SECRET", "").strip()

# SECURITY F-07: validate domain format to prevent URL injection /
# credential redirection to attacker-controlled hosts.
_DOMAIN_RE = re.compile(
    r'^[a-zA-Z0-9][a-zA-Z0-9\-]{1,62}'
    r'(?:\.[a-zA-Z0-9][a-zA-Z0-9\-]{0,62})*'
    r'\.[a-zA-Z]{2,}$'
)

def _validate_config():
    errors = []
    if not RSC_DOMAIN:
        errors.append("RSC_DOMAIN is not set.")
    elif not _DOMAIN_RE.match(RSC_DOMAIN):
        errors.append(
            f"RSC_DOMAIN '{RSC_DOMAIN}' is not a valid hostname. "
            "Expected format: account.my.rubrik.com"
        )
    elif len(RSC_DOMAIN) > 253:
        errors.append("RSC_DOMAIN exceeds maximum hostname length (253 chars).")

    if not RSC_CLIENT_ID:
        errors.append("RSC_CLIENT_ID is not set.")
    if not RSC_CLIENT_SECRET:
        errors.append("RSC_CLIENT_SECRET is not set.")

    if errors:
        print("[!] Configuration errors:")
        for e in errors:
            print(f"    - {e}")
        print("[!] Set environment variables or populate your .env file.")
        sys.exit(1)

_validate_config()

RSC_BASE_URL   = f"https://{RSC_DOMAIN}"
RSC_TOKEN_URL  = f"{RSC_BASE_URL}/api/client_token"
RSC_GRAPHQL_URL = f"{RSC_BASE_URL}/api/graphql"

# ============================================================
# OUTPUT
# ============================================================
TIMESTAMP        = datetime.now().strftime("%Y%m%d_%H%M%S")
INTERMEDIATE_DIR = os.environ.get("DB_STATUS_WORK_DIR", "./db_status_work")
INTERMEDIATE_FILE = os.path.join(INTERMEDIATE_DIR, f"raw_fetch_{TIMESTAMP}.json")
EVENTS_FILE      = os.path.join(INTERMEDIATE_DIR, f"events_{TIMESTAMP}.json")
OUTPUT_CSV  = f"db_status_report_{TIMESTAMP}.csv"
OUTPUT_JSON = f"db_status_report_{TIMESTAMP}.json"
OUTPUT_HTML = f"db_status_report_{TIMESTAMP}.html"

# ============================================================
# LOGGING
# ============================================================
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_FILE  = os.environ.get("LOG_FILE", "")   # e.g. db_status.log; empty = console only

_handlers = [logging.StreamHandler(sys.stdout)]
if LOG_FILE:
    _handlers.append(logging.FileHandler(LOG_FILE, encoding="utf-8"))

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=_handlers,
)
logger = logging.getLogger("db_status")

# ============================================================
# BEHAVIOR
# ============================================================
PAGE_SIZE                      = 200
API_CALL_DELAY                 = 0.1
ENABLE_MSSQL_EVENT_CHECKS      = True
STALE_SNAPSHOT_DAYS            = 7
OFFLINE_SNAPSHOT_DAYS          = 30
MISSED_SNAPSHOT_LOOKBACK_HOURS = 72

# SECURITY F-09: error rate threshold — if more than this fraction of
# event checks fail, emit a prominent warning in the report.
EVENT_ERROR_RATE_THRESHOLD = 0.10

# ============================================================
# WORKER / PAGE SIZE OVERRIDES
# ============================================================
# These cap the scale profile defaults. Useful when the profile is too
# aggressive for a specific RSC instance (e.g. repeated upstream timeouts).
# Set to 0 to use the profile default.
MAX_PAGE_SIZE   = int(os.environ.get("MAX_PAGE_SIZE", "0")) or None   # 0 = profile default
MAX_WORKERS     = int(os.environ.get("MAX_WORKERS",   "0")) or None   # 0 = profile default
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "120"))       # seconds per API call
MIN_PAGE_SIZE   = int(os.environ.get("MIN_PAGE_SIZE", "25"))          # floor for adaptive reduction

# ============================================================
# DISK CACHE
# ============================================================
# Parsed database records are cached to an AES-encrypted file after each
# successful fetch. Subsequent runs load from cache (skipping the 2-hour
# API fetch) until the cache expires. Requires the `cryptography` package.
CACHE_TTL_HOURS = float(os.environ.get("CACHE_TTL_HOURS", "12"))
CACHE_FILE      = os.environ.get("CACHE_FILE",     ".db_status_cache.bin")
CACHE_KEY_FILE  = os.environ.get("CACHE_KEY_FILE", ".db_status_cache.key")

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
        "page_size": 500,
        "max_workers": 8,
        "batch_size": 500,
        "stream_to_disk": True,
        "event_checks": True,
        "rate_limit": 12,
    },
    "xxlarge": {
        "label": "XXLarge (50K-100K+)",
        "page_size": 500,
        "max_workers": 8,
        "batch_size": 1000,
        "stream_to_disk": True,
        "event_checks": False,
        "rate_limit": 12,
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