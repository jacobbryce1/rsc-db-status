"""
Token management with automatic refresh.
Thread-safe for use with concurrent fetching.
"""
import time
import threading
import requests
from .config import RSC_TOKEN_URL, RSC_CLIENT_ID, RSC_CLIENT_SECRET


class TokenManager:
    """Thread-safe token manager with automatic refresh before expiration."""

    def __init__(self, buffer_seconds: int = 60):
        """
        buffer_seconds: refresh this many seconds BEFORE actual expiry
        to avoid mid-request failures.
        """
        self.buffer_seconds = buffer_seconds
        self.access_token = None
        self.expires_at = 0
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
            response = requests.post(
                RSC_TOKEN_URL, json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Authentication failed: {e}")

        token_data = response.json()
        self.access_token = token_data.get("access_token")
        if not self.access_token:
            raise Exception("No access_token in response.")

        expires_in = token_data.get("expires_in", 300)
        self.expires_at = time.time() + expires_in
        self.token_ttl = expires_in
        self.refresh_count += 1

        effective_life = expires_in - self.buffer_seconds
        print(f"[+] Token acquired (TTL={expires_in}s, "
              f"effective={effective_life}s before auto-refresh)")

    def force_refresh(self):
        """Force a token refresh (e.g., after a 401 response)."""
        with self.lock:
            self._refresh_token()

    def get_stats(self) -> dict:
        """Return token manager statistics."""
        return {
            "refresh_count": self.refresh_count,
            "token_ttl": self.token_ttl,
            "buffer_seconds": self.buffer_seconds,
        }
