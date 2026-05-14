"""
Encrypted disk cache for parsed database records.

Modelled on the rsc-events-dashboard incremental_cache approach:
  - AES-256 encryption via Fernet (cryptography package)
  - Random 256-bit key generated on first run, stored in a separate key file
    with permissions 0o600 (owner read/write only)
  - Cache data file is opaque ciphertext; unreadable without the key file
  - Falls back to in-memory-only mode if cryptography is not installed
  - TTL-based validity — expired caches are ignored and regenerated

Usage:
    from .cache import load_cache, save_cache

    # Load
    cached = load_cache(CACHE_FILE, CACHE_KEY_FILE, CACHE_TTL_HOURS)
    if cached:
        databases = cached["databases"]
    else:
        # run full fetch ...
        save_cache(databases, metadata, CACHE_FILE, CACHE_KEY_FILE)
"""

import os
import json
import time
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("db_status.cache")

try:
    from cryptography.fernet import Fernet, InvalidToken
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False
    logger.warning(
        "cryptography package not installed — disk cache is disabled. "
        "Run: pip install 'cryptography>=42.0.0'"
    )


# ---------------------------------------------------------------------------
# Key management
# ---------------------------------------------------------------------------

def _load_or_create_key(key_path: Path) -> Optional[bytes]:
    """Load an existing Fernet key or generate and save a new one (mode 0o600)."""
    if not _CRYPTO_AVAILABLE:
        return None

    if key_path.exists():
        try:
            key = key_path.read_bytes().strip()
            Fernet(key)   # validate
            return key
        except Exception:
            logger.warning("Cache key file is corrupt — regenerating.")
            key_path.unlink(missing_ok=True)

    key = Fernet.generate_key()
    key_path.write_bytes(key)
    os.chmod(key_path, 0o600)
    logger.info("Generated new cache encryption key: %s", key_path)
    return key


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_cache(cache_file: str, key_file: str,
               ttl_hours: float) -> Optional[dict]:
    """
    Load the cache if it exists, can be decrypted, and is within TTL.

    Returns a dict with keys:
        databases  — list of parsed database records
        metadata   — dict with saved_at, profile, total, etc.
    Returns None if cache is missing, expired, or unreadable.
    """
    if not _CRYPTO_AVAILABLE:
        return None

    cache_path = Path(cache_file)
    key_path   = Path(key_file)

    if not cache_path.exists() or not key_path.exists():
        return None

    key = _load_or_create_key(key_path)
    if key is None:
        return None

    try:
        f   = Fernet(key)
        raw = f.decrypt(cache_path.read_bytes())
        payload = json.loads(raw.decode("utf-8"))
    except (InvalidToken, Exception) as e:
        logger.warning("Cache read failed (%s) — will re-fetch.", e)
        return None

    # TTL check
    saved_at_str = payload.get("metadata", {}).get("saved_at", "")
    if saved_at_str:
        try:
            saved_at = datetime.fromisoformat(saved_at_str)
            age_hours = (datetime.now(timezone.utc) - saved_at).total_seconds() / 3600
            if age_hours > ttl_hours:
                logger.info(
                    "Cache expired (age=%.1fh, ttl=%.1fh) — will re-fetch.",
                    age_hours, ttl_hours
                )
                return None
            logger.info(
                "Cache hit — age=%.1fh, %d databases, profile=%s",
                age_hours,
                len(payload.get("databases", [])),
                payload.get("metadata", {}).get("profile", "?"),
            )
        except Exception:
            return None

    return payload


def save_cache(databases: list, metadata: dict,
               cache_file: str, key_file: str) -> bool:
    """
    Encrypt and write the databases list to disk.

    Returns True on success, False if cryptography is unavailable or write fails.
    """
    if not _CRYPTO_AVAILABLE:
        return False

    key_path   = Path(key_file)
    cache_path = Path(cache_file)

    key = _load_or_create_key(key_path)
    if key is None:
        return False

    payload = {
        "metadata": {
            **metadata,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "total": len(databases),
        },
        "databases": databases,
    }

    try:
        f         = Fernet(key)
        plaintext = json.dumps(payload, default=str).encode("utf-8")
        ciphertext = f.encrypt(plaintext)
        cache_path.write_bytes(ciphertext)
        os.chmod(cache_path, 0o600)
        logger.info(
            "Cache saved: %s (%d databases, %.1f MB)",
            cache_path,
            len(databases),
            len(ciphertext) / 1_048_576,
        )
        return True
    except Exception as e:
        logger.warning("Cache write failed: %s", e)
        return False


def clear_cache(cache_file: str, key_file: str):
    """Delete cache data and key files."""
    for path_str in (cache_file, key_file):
        p = Path(path_str)
        if p.exists():
            p.unlink()
            logger.info("Deleted cache file: %s", p)


def cache_info(cache_file: str, key_file: str) -> dict:
    """Return basic info about the cache without fully decrypting it."""
    cache_path = Path(cache_file)
    key_path   = Path(key_file)
    info = {
        "cache_exists": cache_path.exists(),
        "key_exists":   key_path.exists(),
        "crypto_available": _CRYPTO_AVAILABLE,
        "size_mb": None,
        "age_hours": None,
    }
    if cache_path.exists():
        stat = cache_path.stat()
        info["size_mb"] = round(stat.st_size / 1_048_576, 1)
        age_s = time.time() - stat.st_mtime
        info["age_hours"] = round(age_s / 3600, 1)
    return info
