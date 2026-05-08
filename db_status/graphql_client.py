"""
GraphQL execution with retry, rate limiting, and error handling.
"""
import time
import threading
import requests
from .config import RSC_GRAPHQL_URL
from .auth import TokenManager


class RateLimiter:
    """Token bucket rate limiter for RSC API."""

    def __init__(self, calls_per_second: int = 10):
        self.calls_per_second = calls_per_second
        self.lock = threading.Lock()
        self.tokens = float(calls_per_second)
        self.last_refill = time.time()

    def acquire(self):
        """Block until a token is available."""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_refill
            self.tokens = min(
                float(self.calls_per_second),
                self.tokens + elapsed * self.calls_per_second
            )
            self.last_refill = now
            if self.tokens < 1.0:
                sleep_time = (1.0 - self.tokens) / self.calls_per_second
                time.sleep(sleep_time)
                self.tokens = 0.0
            else:
                self.tokens -= 1.0


# Module-level rate limiter
_rate_limiter = RateLimiter(calls_per_second=10)


def set_rate_limit(calls_per_second: int):
    """Update the global rate limiter."""
    global _rate_limiter
    _rate_limiter = RateLimiter(calls_per_second=calls_per_second)


def execute_graphql(token_manager: TokenManager, query: str,
                    variables: dict, max_retries: int = 3) -> dict:
    """Execute GraphQL with token refresh, rate limiting, and retry."""

    for attempt in range(max_retries):
        _rate_limiter.acquire()
        access_token = token_manager.get_token()

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }
        payload = {"query": query, "variables": variables}

        try:
            response = requests.post(
                RSC_GRAPHQL_URL, json=payload,
                headers=headers, timeout=60
            )
        except requests.exceptions.Timeout:
            print(f"    ⚠️ Timeout (attempt {attempt+1}/{max_retries})")
            time.sleep(2 ** attempt)
            continue
        except requests.exceptions.ConnectionError as e:
            print(f"    ⚠️ Connection error (attempt {attempt+1}): "
                  f"{str(e)[:100]}")
            time.sleep(2 ** attempt)
            continue

        # Handle expired token
        if response.status_code in (401, 403):
            print(f"    ⚠️ Token expired, refreshing...")
            token_manager.force_refresh()
            continue

        # Handle rate limiting
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 5))
            print(f"    ⚠️ Rate limited. Waiting {retry_after}s...")
            time.sleep(retry_after)
            continue

        # Handle server errors
        if response.status_code >= 500:
            print(f"    ⚠️ Server error {response.status_code} "
                  f"(attempt {attempt+1})")
            time.sleep(2 ** attempt)
            continue

        if response.status_code != 200:
            try:
                error_detail = response.json().get("message",
                                                    response.text[:500])
            except Exception:
                error_detail = response.text[:500]
            raise Exception(f"HTTP {response.status_code}: {error_detail}")

        result = response.json()

        if "errors" in result and "data" not in result:
            raise Exception(
                f"GraphQL errors: {result['errors']}")

        if "errors" in result and "data" in result:
            for err in result["errors"]:
                msg = err.get("message", "")[:100]
                if "features enabled" in msg.lower():
                    raise Exception(f"Feature not licensed: {msg}")

        return result.get("data") or {}

    raise Exception(f"Failed after {max_retries} retries")


def test_query(token_manager: TokenManager, query: str, variables: dict):
    """Test a query — returns (success, error_message)."""
    try:
        access_token = token_manager.get_token()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }
        resp = requests.post(
            RSC_GRAPHQL_URL,
            json={"query": query, "variables": variables},
            headers=headers, timeout=30,
        )
        if resp.status_code != 200:
            try:
                msg = resp.json().get("message", "")[:200]
            except Exception:
                msg = resp.text[:200]
            return False, f"HTTP {resp.status_code}: {msg}"
        data = resp.json()
        if "errors" in data:
            for err in data.get("errors", []):
                msg = err.get("message", "").lower()
                if "features enabled" in msg:
                    return False, "Feature not licensed"
            if "data" not in data or not data["data"]:
                return False, data["errors"][0].get("message", "")[:200]
        return True, ""
    except Exception as e:
        return False, str(e)[:200]
