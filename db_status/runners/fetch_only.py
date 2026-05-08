"""Phase 1-3 only: Fetch and parse, save intermediate JSON."""
import os
import json
import time
from ..config import (
    get_scale_profile, INTERMEDIATE_DIR, INTERMEDIATE_FILE
)
from ..auth import TokenManager
from ..graphql_client import set_rate_limit
from ..pagination import get_platform_count, fetch_all_platforms_parallel
from ..platforms.definitions import PLATFORMS
from ..parsers import parse_node


def run_fetch():
    """Fetch all platforms and save to intermediate file."""
    os.makedirs(INTERMEDIATE_DIR, exist_ok=True)

    token_manager = TokenManager(buffer_seconds=60)
    token_manager.get_token()

    print("\n[*] Counting platforms...")
    total_estimate = 0
    active_platforms = []
    for platform in PLATFORMS:
        count = get_platform_count(
            token_manager, platform["query_name"], platform["uses_filter"])
        if count > 0:
            print(f"    ✅ {platform['name']}: ~{count}")
            active_platforms.append(platform)
            total_estimate += count

    profile = get_scale_profile(total_estimate)
    set_rate_limit(profile["rate_limit"])
    print(f"\n[*] Profile: {profile['label']} ({total_estimate} est.)")

    print("\n[*] Fetching...")
    start = time.time()
    raw_nodes = fetch_all_platforms_parallel(
        token_manager, active_platforms, profile)

    print(f"\n[*] Parsing {len(raw_nodes)} nodes...")
    databases = [parse_node(n) for n in raw_nodes]

    with open(INTERMEDIATE_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "total": len(databases),
            "profile": profile["label"],
            "databases": databases,
        }, f, indent=2, default=str)

    elapsed = time.time() - start
    print(f"\n[+] Done: {len(databases)} databases in {elapsed:.1f}s")
    print(f"[+] Saved: {INTERMEDIATE_FILE}")
