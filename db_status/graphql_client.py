"""
GraphQL execution with retry, rate limiting, and error handling.

SECURITY F-03: verify=True on all requests; SSLError never retried.
SECURITY F-06: response bodies never printed raw; exceptions sanitized.
"""
import time
import threading
import requests
import requests.exceptions
from .config import RSC_GRAPHQL_URL, REQUEST_TIMEOUT
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


_rate_limiter = RateLimiter(calls_per_second=10)


def set_rate_limit(calls_per_second: int):
    """Update the global rate limiter."""
    global _rate_limiter
    _rate_limiter = RateLimiter(calls_per_second=calls_per_second)


def _safe_error_message(response: requests.Response) -> str:
    """
    SECURITY F-06: extract only the message field from an API error response.
    Never return the full response body — it may contain request echoes with
    variable values (GraphQL variables, partial credentials, etc.).
    """
    try:
        body = response.json()
        msg = body.get("message") or body.get("error") or ""
        return str(msg)[:200]   # bounded, field-specific, not raw body
    except Exception:
        # Return only the status code — no body at all if JSON parse fails
        return f"(non-JSON response, status {response.status_code})"


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
                RSC_GRAPHQL_URL,
                json=payload,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
                verify=True,   # SECURITY F-03: explicit TLS verification
            )

        # SECURITY F-03: TLS errors are fatal — never retry, never suppress.
        except requests.exceptions.SSLError as e:
            raise RuntimeError(
                "TLS certificate verification failed during GraphQL call. "
                "Do not disable SSL verification."
            ) from e

        except requests.exceptions.Timeout:
            print(f"    Warning: request timeout (attempt {attempt+1}/{max_retries})")
            time.sleep(2 ** attempt)
            continue

        except requests.exceptions.ConnectionError:
            # SECURITY F-06: don't log the exception str (contains URL + details)
            print(f"    Warning: connection error (attempt {attempt+1}/{max_retries})")
            time.sleep(2 ** attempt)
            continue

        # Expired token
        if response.status_code in (401, 403):
            print("    Warning: token rejected, refreshing...")
            token_manager.force_refresh()
            continue

        # Rate limit
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 5))
            print(f"    Warning: rate limited, waiting {retry_after}s...")
            time.sleep(retry_after)
            continue

        # Server errors
        if response.status_code >= 500:
            print(f"    Warning: server error {response.status_code} "
                  f"(attempt {attempt+1}/{max_retries})")
            time.sleep(2 ** attempt)
            continue

        if response.status_code != 200:
            # SECURITY F-06: use _safe_error_message, not response.text
            raise RuntimeError(
                f"HTTP {response.status_code}: {_safe_error_message(response)}"
            )

        result = response.json()

        if "errors" in result and "data" not in result:
            # Extract only the message fields — not full error objects
            msgs = [e.get("message", "")[:100] for e in result["errors"]]
            raise RuntimeError(f"GraphQL error: {'; '.join(msgs)}")

        if "errors" in result and "data" in result:
            for err in result["errors"]:
                msg = err.get("message", "")[:100]
                if "features enabled" in msg.lower():
                    raise RuntimeError(f"Feature not licensed: {msg}")

        return result.get("data") or {}

    raise RuntimeError(f"GraphQL call failed after {max_retries} retries")


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
            headers=headers,
            timeout=30,
            verify=True,   # SECURITY F-03
        )
        if resp.status_code != 200:
            return False, f"HTTP {resp.status_code}: {_safe_error_message(resp)}"
        data = resp.json()
        if "errors" in data:
            for err in data.get("errors", []):
                msg = err.get("message", "").lower()
                if "features enabled" in msg:
                    return False, "Feature not licensed"
            if "data" not in data or not data["data"]:
                msgs = [e.get("message", "")[:100] for e in data["errors"]]
                return False, "; ".join(msgs)
        return True, ""
    except requests.exceptions.SSLError:
        return False, "TLS verification failed"
    except Exception:
        # SECURITY F-06: don't propagate exception details from test probes
        return False, "Connection failed"