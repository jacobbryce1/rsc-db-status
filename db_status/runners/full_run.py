"""Full orchestrated run — all phases with checkpointing."""
import os
import json
import time
import logging
from ..config import (
    get_scale_profile, INTERMEDIATE_DIR, INTERMEDIATE_FILE,
    EVENTS_FILE, OUTPUT_CSV, OUTPUT_JSON, OUTPUT_HTML,
    ENABLE_MSSQL_EVENT_CHECKS,
    CACHE_FILE, CACHE_KEY_FILE, CACHE_TTL_HOURS,
    MAX_PAGE_SIZE, MAX_WORKERS,
)
from ..cache import load_cache, save_cache, clear_cache

logger = logging.getLogger("db_status.runner")
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


def inherit_snapshot_dates(databases: list) -> list:
    """
    Post-processing: Inherit snapshot dates between parent/child objects.

    Strategy:
    1. Build lookup: id → database record (with snapshot dates)
    2. For child objects without snapshot dates, look up parent via physicalPath
    3. For MongoDB Sources without dates, look up children (Collections) and use newest
    4. For MySQL instances without snapshot data, query their instance

    SECURITY AU-9: original event_status is preserved in raw_event_status before
    any inheritance mutation so investigators can distinguish a genuinely clean
    database from one whose status was derived from a parent/child snapshot.
    """
    print("\n[*] Phase 3b: Inheriting snapshot dates from parent/child...")

    # Build lookup by ID
    db_by_id = {}
    for db in databases:
        db_by_id[db["id"]] = db

    # Track inheritance stats
    inherited_from_parent = 0
    inherited_from_child = 0

    # --- Step 1: Child inherits from parent ---
    # PostgreSQL Databases → PostgreSQL DB Clusters
    # MySQL Databases → MySQL Instances (via physicalPath)
    # MongoDB Databases → MongoDB Sources (via physicalPath)
    for db in databases:
        # Skip if already has snapshot data
        if db.get("newest_snapshot"):
            continue

        # Skip relics
        if db.get("is_relic"):
            continue

        # Get the raw node to access physicalPath
        # physicalPath is stored in the raw node, we need to look it up
        # The parse_node function doesn't currently preserve physicalPath,
        # so we'll use the _raw_node if available
        raw_node = db.get("_raw_node", {})
        physical_path = raw_node.get("physicalPath", []) or []

        if not physical_path:
            continue

        # Find parent in our lookup
        for path_entry in physical_path:
            parent_fid = path_entry.get("fid", "")
            if parent_fid and parent_fid in db_by_id:
                parent = db_by_id[parent_fid]
                if parent.get("newest_snapshot"):
                    db["newest_snapshot"] = parent["newest_snapshot"]
                    db["oldest_snapshot"] = parent.get("oldest_snapshot", "")
                    # SECURITY AU-9: preserve original status before mutation
                    if "raw_event_status" not in db:
                        db["raw_event_status"] = db.get("event_status", "")
                    if "No Snapshots" in db.get("event_status", ""):
                        db["event_status"] = "Online (Inherited from Parent)"
                    inherited_from_parent += 1
                    break

    # --- Step 2: Parent inherits from children (MongoDB Sources) ---
    # MongoDB Sources have 0 snapshots themselves but their Collections do
    # Find the newest snapshot across all children for each source

    # Build: source_id → list of child collection snapshot dates
    source_children_dates = {}
    for db in databases:
        if db.get("platform") != "MongoDB Collections":
            continue
        if not db.get("newest_snapshot"):
            continue

        raw_node = db.get("_raw_node", {})
        physical_path = raw_node.get("physicalPath", []) or []

        for path_entry in physical_path:
            if path_entry.get("objectType") == "MONGO_SOURCE":
                source_fid = path_entry.get("fid", "")
                if source_fid:
                    if source_fid not in source_children_dates:
                        source_children_dates[source_fid] = []
                    source_children_dates[source_fid].append(
                        db["newest_snapshot"])
                break

    # Apply to MongoDB Sources
    for db in databases:
        if db.get("platform") != "MongoDB Sources":
            continue
        if db.get("newest_snapshot"):
            continue
        if db.get("is_relic"):
            continue

        source_id = db["id"]
        if source_id in source_children_dates:
            dates = source_children_dates[source_id]
            if dates:
                db["newest_snapshot"] = max(dates)  # Most recent
                # SECURITY AU-9: preserve original status before mutation
                if "raw_event_status" not in db:
                    db["raw_event_status"] = db.get("event_status", "")
                if "No Snapshots" in db.get("event_status", ""):
                    db["event_status"] = "Online (Via Collections)"
                inherited_from_child += 1

    # Also apply to MongoDB Databases from their Collections
    db_children_dates = {}
    for db in databases:
        if db.get("platform") != "MongoDB Collections":
            continue
        if not db.get("newest_snapshot"):
            continue

        raw_node = db.get("_raw_node", {})
        physical_path = raw_node.get("physicalPath", []) or []

        for path_entry in physical_path:
            if path_entry.get("objectType") == "MONGO_DATABASE":
                db_fid = path_entry.get("fid", "")
                if db_fid:
                    if db_fid not in db_children_dates:
                        db_children_dates[db_fid] = []
                    db_children_dates[db_fid].append(db["newest_snapshot"])
                break

    for db in databases:
        if db.get("platform") != "MongoDB Databases":
            continue
        if db.get("newest_snapshot"):
            continue
        if db.get("is_relic"):
            continue

        if db["id"] in db_children_dates:
            dates = db_children_dates[db["id"]]
            if dates:
                db["newest_snapshot"] = max(dates)
                # SECURITY AU-9: preserve original status before mutation
                if "raw_event_status" not in db:
                    db["raw_event_status"] = db.get("event_status", "")
                if "No Snapshots" in db.get("event_status", ""):
                    db["event_status"] = "Online (Via Collections)"
                inherited_from_child += 1

    # Ensure raw_event_status is populated for every record, even those not
    # touched by inheritance, so report consumers always have the field present.
    for db in databases:
        if "raw_event_status" not in db:
            db["raw_event_status"] = db.get("event_status", "")

    print(f"    Inherited from parent: {inherited_from_parent}")
    print(f"    Inherited from children: {inherited_from_child}")

    return databases


def run_full(force_refresh: bool = False):
    """Execute all phases end-to-end."""
    print("=" * 60)
    print("  🔴🟢 Rubrik RSC — Database Status Report")
    print("  Scalable Edition (1K–100K) | All Platforms")
    print("=" * 60)

    os.makedirs(INTERMEDIATE_DIR, exist_ok=True)
    start_time = time.time()

    if MAX_PAGE_SIZE or MAX_WORKERS:
        overrides = []
        if MAX_PAGE_SIZE:
            overrides.append(f"MAX_PAGE_SIZE={MAX_PAGE_SIZE}")
        if MAX_WORKERS:
            overrides.append(f"MAX_WORKERS={MAX_WORKERS}")
        print(f"[*] Env overrides active: {', '.join(overrides)}")

    # ── Cache check ─────────────────────────────────────────────────────────
    if force_refresh:
        print("[*] --force-refresh: clearing cache and re-fetching from API.")
        clear_cache(CACHE_FILE, CACHE_KEY_FILE)

    cached = load_cache(CACHE_FILE, CACHE_KEY_FILE, CACHE_TTL_HOURS)
    if cached:
        databases = cached["databases"]
        meta      = cached.get("metadata", {})
        print(f"\n[✓] Loaded {len(databases):,} databases from cache "
              f"(age: {meta.get('age_hint', '?')}, "
              f"profile: {meta.get('profile', '?')})")
        print("[*] Skipping Phases 1–3 (fetch & parse). "
              "Run with --force-refresh to re-fetch.")
        token_manager = TokenManager(buffer_seconds=60)
        token_manager.get_token()
        profile_label = meta.get("profile", "cached")
        # Jump straight to Phase 4
        _run_phases_4_5(databases, token_manager, profile_label, start_time)
        return

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
            parsed = parse_node(node)
            # Preserve raw node for physicalPath inheritance
            parsed["_raw_node"] = node
            databases.append(parsed)
        except Exception as e:
            parse_errors += 1
            if parse_errors <= 5:
                print(f"    ⚠️ Parse error: {str(e)[:80]}")
    print(f"    Parsed {len(databases)} records ({parse_errors} errors)")

    # Phase 3b: Inherit snapshot dates.
    # SECURITY ISO A.8.28: _raw_node cleanup is in a try/finally block so it
    # is guaranteed to run even if inherit_snapshot_dates() raises an exception,
    # preventing raw GraphQL node data from persisting beyond this phase.
    try:
        databases = inherit_snapshot_dates(databases)
    finally:
        for db in databases:
            db.pop("_raw_node", None)

    # Save intermediate
    with open(INTERMEDIATE_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "total": len(databases),
            "profile": profile["label"],
            "databases": databases,
        }, f, indent=2, default=str)
    print(f"[+] Intermediate saved: {INTERMEDIATE_FILE}")

    # Save to encrypted disk cache
    saved = save_cache(
        databases,
        {"profile": profile["label"]},
        CACHE_FILE,
        CACHE_KEY_FILE,
    )
    if saved:
        print(f"[+] Cache updated: {CACHE_FILE}")
    else:
        print("[!] Cache not saved (cryptography package not installed or write error)")

    _run_phases_4_5(databases, token_manager, profile["label"], start_time)


def _run_phases_4_5(databases: list, token_manager, profile_label: str,
                    start_time: float):
    """Run event checks (Phase 4) and report generation (Phase 5)."""

    profile_event_checks = isinstance(profile_label, str) and "small" not in profile_label.lower()

    # Phase 4: Event checks
    if ENABLE_MSSQL_EVENT_CHECKS and profile_event_checks:
        print("\n[*] Phase 4: MSSQL event checks...")
        mssql_ids = [
            db["id"] for db in databases
            if "MSSQL" in db.get("platform", "") and not db.get("is_relic")
        ]
        if mssql_ids:
            print(f"    {len(mssql_ids)} MSSQL databases to check")
            # Build a minimal profile dict for event checks
            from ..config import SCALE_PROFILES
            _profile = next(
                (p for p in SCALE_PROFILES.values()
                 if p["label"] == profile_label),
                SCALE_PROFILES["xxlarge"]
            )
            event_results = batched_event_check(
                token_manager, mssql_ids, _profile)
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
        reason = "disabled for scale" if not profile_event_checks else "globally disabled"
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
    print(f"  Scale profile: {profile_label}")
    if total_time > 0:
        print(f"  Rate: {len(databases)/total_time:.1f} DBs/sec")
    print(f"  Output:")
    print(f"    📄 {OUTPUT_CSV}")
    print(f"    📋 {OUTPUT_JSON}")
    print(f"    🌐 {OUTPUT_HTML}")
    print(f"{'=' * 60}")