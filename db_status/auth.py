"""
Token management with automatic refresh.
Thread-safe for use with concurrent fetching.

SECURITY F-03: explicit verify=True on all requests; SSLError is never retried.
SECURITY F-08: get_token() returns (token, expires_at) tuple so callers can
               detect imminent expiry without re-acquiring the lock.
SECURITY F-06: token TTL printed but no secrets or response bodies logged.
"""
import ssl
import time
import threading
import requests
import requests.exceptions
from .config import RSC_TOKEN_URL, RSC_CLIENT_ID, RSC_CLIENT_SECRET


class TokenManager:
    """Thread-safe token manager with automatic refresh before expiration."""

    def __init__(self, buffer_seconds: int = 60):
        self.buffer_seconds = buffer_seconds
        self.access_token: str | None = None
        self.expires_at: float = 0.0
        self.lock = threading.Lock()
        self.refresh_count = 0
        self.token_ttl = 0

    def get_token(self) -> str:
        """Thread-safe token retrieval with automatic refresh."""
        with self.lock:
            now = time.time()
            if self.access_token is None or now >= (self.expires_at - self.buffer_seconds):
                self._refresh_token()
            return self.access_token

    def get_token_with_expiry(self) -> tuple[str, float]:
        """Return (token, expires_at) — lets callers skip re-locking."""
        with self.lock:
            now = time.time()
            if self.access_token is None or now >= (self.expires_at - self.buffer_seconds):
                self._refresh_token()
            return self.access_token, self.expires_at

    def _refresh_token(self):
        """Authenticate and store new token with expiry tracking."""
        payload = {
            "client_id": RSC_CLIENT_ID,
            "client_secret": RSC_CLIENT_SECRET,
        }

        if self.refresh_count == 0:
            print("[*] Authenticating to Rubrik Security Cloud...")
        else:
            remaining = max(0, self.expires_at - time.time())
            print(f"[*] Refreshing token (#{self.refresh_count}, "
                  f"{remaining:.0f}s remaining on old token)...")

        try:
            # SECURITY F-03: verify=True is explicit — never allow SSL bypass.
            response = requests.post(
                RSC_TOKEN_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30,
                verify=True,   # explicit; reject self-signed / invalid certs
            )
            response.raise_for_status()

        # SECURITY F-03: SSL errors are NOT retried — they signal MITM or
        # misconfiguration. Raise immediately with a clear message.
        except requests.exceptions.SSLError as e:
            raise RuntimeError(
                "TLS certificate verification failed during authentication. "
                "Do not disable SSL verification. Check your CA bundle or "
                "network configuration."
            ) from e

        except requests.exceptions.ConnectionError as e:
            # Sanitize — don't propagate raw exception which may contain URLs
            raise RuntimeError(
                "Connection error during authentication. "
                "Check RSC_DOMAIN and network connectivity."
            ) from e

        except requests.exceptions.Timeout:
            raise RuntimeError(
                "Authentication request timed out (30s). "
                "Check network connectivity to RSC."
            )

        except requests.exceptions.RequestException as e:
            # SECURITY F-06: do not include response body in exception
            raise RuntimeError(
                f"Authentication failed (HTTP {getattr(e.response, 'status_code', 'unknown')}). "
                "Check RSC_CLIENT_ID and RSC_CLIENT_SECRET."
            ) from e

        token_data = response.json()
        self.access_token = token_data.get("access_token")
        if not self.access_token:
            raise RuntimeError("No access_token in authentication response.")

        expires_in = int(token_data.get("expires_in", 300))
        self.expires_at = time.time() + expires_in
        self.token_ttl = expires_in
        self.refresh_count += 1

        effective_life = expires_in - self.buffer_seconds
        # SECURITY F-06: log TTL only — never log the token value itself
        print(f"[+] Token acquired (TTL={expires_in}s, "
              f"effective={effective_life}s before auto-refresh)")

    def force_refresh(self):
        """Force a token refresh (e.g., after a 401 response)."""
        with self.lock:
            self._refresh_token()

    def get_stats(self) -> dict:
        """Return token manager statistics (no sensitive values)."""
        return {
            "refresh_count": self.refresh_count,
            "token_ttl": self.token_ttl,
            "buffer_seconds": self.buffer_seconds,
        }