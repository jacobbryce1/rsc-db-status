"""Full orchestrated run — all phases with checkpointing."""
import os
import json
import time
from ..config import (
    get_scale_profile, INTERMEDIATE_DIR, INTERMEDIATE_FILE,
    EVENTS_FILE, OUTPUT_CSV, OUTPUT_JSON, OUTPUT_HTML,
    ENABLE_MSSQL_EVENT_CHECKS
)
from ..auth import TokenManager
from ..graphql_client import set_rate_limit
from ..pagination import get_platform_count, fetch_all_platforms_parallel
from ..platforms.definitions import PLATFORMS
from ..parsers import parse_node
from ..events import batched_event_check
from ..reports.console import print_console_report
from ..reports.csv_report import write_csv_report
from ..reports.json_report import write_json_report
from ..reports.html_report import write_html_report


def run_full():
    """Execute all phases end-to-end."""
    print("=" * 60)
    print("  🔴🟢 Rubrik RSC — Database Status Report")
    print("  Scalable Edition (1K–100K) | All Platforms")
    print("=" * 60)

    os.makedirs(INTERMEDIATE_DIR, exist_ok=True)
    start_time = time.time()

    # Initialize token manager
    token_manager = TokenManager(buffer_seconds=60)
    token_manager.get_token()

    # Phase 1: Count
    print("\n[*] Phase 1: Estimating environment size...")
    total_estimate = 0
    active_platforms = []

    for platform in PLATFORMS:
        count = get_platform_count(
            token_manager, platform["query_name"], platform["uses_filter"])
        if count > 0:
            print(f"    ✅ {platform['name']}: ~{count}")
            active_platforms.append(platform)
            total_estimate += count
        else:
            print(f"    ⬜ {platform['name']}: 0 or not licensed")

    profile = get_scale_profile(total_estimate)
    print(f"\n[*] Estimated total: {total_estimate}")
    print(f"[*] Scale profile: {profile['label']}")
    set_rate_limit(profile["rate_limit"])

    # Phase 2: Fetch
    print("\n[*] Phase 2: Fetching from all platforms...")
    raw_nodes = fetch_all_platforms_parallel(
        token_manager, active_platforms, profile)
    print(f"\n[+] Fetched {len(raw_nodes)} objects")

    # Phase 3: Parse
    print("\n[*] Phase 3: Parsing...")
    databases = []
    parse_errors = 0
    for node in raw_nodes:
        try:
            databases.append(parse_node(node))
        except Exception as e:
            parse_errors += 1
            if parse_errors <= 5:
                print(f"    ⚠️ Parse error: {str(e)[:80]}")
    print(f"    Parsed {len(databases)} records ({parse_errors} errors)")

    # Save intermediate
    with open(INTERMEDIATE_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "total": len(databases),
            "profile": profile["label"],
            "databases": databases,
        }, f, indent=2, default=str)
    print(f"[+] Intermediate saved: {INTERMEDIATE_FILE}")

    # Phase 4: Event checks
    if ENABLE_MSSQL_EVENT_CHECKS and profile["event_checks"]:
        print("\n[*] Phase 4: MSSQL event checks...")
        mssql_ids = [
            db["id"] for db in databases
            if "MSSQL" in db.get("platform", "") and not db.get("is_relic")
        ]
        if mssql_ids:
            print(f"    {len(mssql_ids)} MSSQL databases to check")
            event_results = batched_event_check(
                token_manager, mssql_ids, profile)
            for db in databases:
                if db["id"] in event_results:
                    ev = event_results[db["id"]]
                    db["total_missed_snapshots"] = ev.get(
                        "total_missed_snapshots", 0)
                    db["total_missed_ranges"] = ev.get(
                        "total_missed_ranges", 0)
                    db["event_status"] = ev.get("event_status", "Error")
            # Save events
            with open(EVENTS_FILE, "w") as f:
                json.dump(event_results, f, indent=2, default=str)
        else:
            print("    No MSSQL databases to check.")
    else:
        reason = ("disabled for scale" if not profile.get("event_checks")
                  else "globally disabled")
        print(f"\n[*] Phase 4: Event checks {reason}.")

    # Phase 5: Reports
    print("\n[*] Phase 5: Generating reports...")
    total_time = time.time() - start_time
    token_stats = token_manager.get_stats()

    print_console_report(databases, token_stats, total_time)
    write_csv_report(databases, OUTPUT_CSV)
    write_json_report(databases, OUTPUT_JSON)
    write_html_report(databases, OUTPUT_HTML)

    # Final
    print(f"\n{'=' * 60}")
    print(f"  ✅ EXECUTION COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Total databases: {len(databases)}")
    print(f"  Total time: {total_time:.1f}s")
    print(f"  Token refreshes: {token_stats['refresh_count']}")
    print(f"  Scale profile: {profile['label']}")
    if total_time > 0:
        print(f"  Rate: {len(databases)/total_time:.1f} DBs/sec")
    print(f"  Output:")
    print(f"    📄 {OUTPUT_CSV}")
    print(f"    📋 {OUTPUT_JSON}")
    print(f"    🌐 {OUTPUT_HTML}")
    print(f"{'=' * 60}")
