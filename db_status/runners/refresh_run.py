"""
Incremental refresh runner — PATH A + PATH C.

PATH C — Age re-evaluation (always runs):
    Recalculate event_status for every cached record using today's date.
    Zero API calls. Catches records that crossed a staleness threshold
    since the last full run (e.g., a backup that was "Online" yesterday
    is now "Warning (Stale: 8d)").

PATH A — Activity-based targeted re-fetch (default, skipped with --age-only):
    1. Query activitySeriesConnection since the cache save timestamp
    2. Client-side filter for DB-related objectTypes
    3. Group FIDs by platform
    4. OBJECT_ID targeted re-fetch only for platforms that support the
       filter parameter — only changed records are re-fetched
    5. Merge updated records into the in-memory database list

After merge: save updated cache, regenerate Phase 4 event checks and
Phase 5 reports for the full (merged) dataset.

Usage:
    python -m db_status refresh              # PATH C + PATH A
    python -m db_status refresh --age-only   # PATH C only (instant, zero API)
"""
import os
import time
import logging
from datetime import datetime, timezone

from ..config import (
    CACHE_FILE, CACHE_KEY_FILE, CACHE_TTL_HOURS,
    STALE_SNAPSHOT_DAYS, OFFLINE_SNAPSHOT_DAYS,
    OUTPUT_CSV, OUTPUT_JSON, OUTPUT_HTML,
    ENABLE_MSSQL_EVENT_CHECKS,
    INTERMEDIATE_DIR, INTERMEDIATE_FILE, EVENTS_FILE,
    SCALE_PROFILES,
)
from ..cache import load_cache, save_cache
from ..auth import TokenManager
from ..graphql_client import execute_graphql, set_rate_limit
from ..parsers import parse_node
from ..platforms.definitions import (
    PLATFORMS,
    MSSQL_QUERY, ORACLE_QUERY, SAP_HANA_QUERY, DB2_QUERY, EXCHANGE_QUERY,
)
from ..events import batched_event_check
from ..reports.console import print_console_report
from ..reports.csv_report import write_csv_report
from ..reports.json_report import write_json_report
from ..reports.html_report import write_html_report

logger = logging.getLogger("db_status.refresh")

# ── Activity objectType → platform data_key mapping ──────────────────────────
# Based on ActivityObjectTypeEnum values discovered in API exploration.
# Platforms marked uses_filter=False (Azure, GCP, AWS, Cassandra) cannot use
# OBJECT_ID filter — their activity events are noted but not targeted.
ACTIVITY_TYPE_TO_PLATFORM = {
    # On-prem CDM (static queries, filterable)
    "Mssql":                       "mssqlDatabases",
    "Oracle":                      "oracleDatabases",
    "OracleDb":                    "oracleDatabases",
    "OracleHost":                  "oracleDatabases",
    "OracleRac":                   "oracleDatabases",
    "SapHanaDb":                   "sapHanaDatabases",
    "SapHanaSystem":               "sapHanaDatabases",
    "Db2Database":                 "db2Databases",
    "Db2Instance":                 "db2Databases",
    "ExchangeDatabase":            "exchangeDatabases",
    # On-prem smart-discovery (filterable)
    "POSTGRES_DB_CLUSTER":         "postgreSQLDbClusters",
    "MYSQLDB_INSTANCE":            "mysqlInstances",
    "MONGO_SOURCE":                "mongoSources",
    "MONGO_DATABASE":              "mongoDatabases",
    "MONGODB_DATABASE":            "mongoDatabases",
    "MONGO_COLLECTION":            "mongoCollections",
    "MONGODB_COLLECTION":          "mongoCollections",
    # Cloud-native (NOT filterable — noted only, no targeted re-fetch)
    "AzureSqlDatabase":            "azureSqlDatabases",
    "AzureSqlDatabaseServer":      "azureSqlDatabases",
    "AzureSqlManagedInstance":     "azureSqlManagedInstanceDatabases",
    "AzureSqlManagedInstanceDatabase": "azureSqlManagedInstanceDatabases",
    "GCP_CLOUD_SQL_INSTANCE":      "gcpCloudSqlInstances",
    "AwsNativeRdsInstance":        "awsNativeRdsInstances",
    "CASSANDRA_KEYSPACE":          "cassandraKeyspaces",
    "CASSANDRA_COLUMN_FAMILY":     "cassandraKeyspaces",
    "CASSANDRA_SOURCE":            "cassandraSources",
}

# Platforms that support the OBJECT_ID HierarchyFilter (uses_filter=True).
# Only these receive targeted re-fetches; cloud-native ones are skipped.
FILTERABLE_PLATFORMS = {
    p["data_key"] for p in PLATFORMS if p.get("uses_filter")
}

# ── Minimal re-fetch queries for smart-discovery filterable platforms ─────────
# These don't have static queries in definitions.py; we use safe field subsets.

_POSTGRES_CLUSTER_REFRESH = """
query($first: Int!, $after: String, $filter: [Filter!]) {
    postgreSQLDbClusters(first: $first, after: $after, filter: $filter) {
        count
        edges { node {
            id name isRelic slaPauseStatus
            cluster { id name }
            configuredSlaDomain { id name }
            effectiveSlaDomain { id name }
            effectiveSlaSourceObject { fid name objectType }
            physicalPath { fid name objectType }
            logicalPath { fid name objectType }
            oldestSnapshot { id date }
            newestSnapshot { id date }
        } }
        pageInfo { endCursor hasNextPage }
    }
}
"""

_MYSQL_INSTANCE_REFRESH = """
query($first: Int!, $after: String, $filter: [Filter!]) {
    mysqlInstances(first: $first, after: $after, filter: $filter) {
        count
        edges { node {
            id name isRelic slaPauseStatus
            cluster { id name }
            configuredSlaDomain { id name }
            effectiveSlaDomain { id name }
            effectiveSlaSourceObject { fid name objectType }
            physicalPath { fid name objectType }
            logicalPath { fid name objectType }
            newestSnapshot { id date }
        } }
        pageInfo { endCursor hasNextPage }
    }
}
"""

_MONGO_SOURCE_REFRESH = """
query($first: Int!, $after: String, $filter: [Filter!]) {
    mongoSources(first: $first, after: $after, filter: $filter) {
        count
        edges { node {
            id name isRelic slaPauseStatus
            cluster { id name }
            configuredSlaDomain { id name }
            effectiveSlaDomain { id name }
            effectiveSlaSourceObject { fid name objectType }
            physicalPath { fid name objectType }
            logicalPath { fid name objectType }
            newestSnapshot { id date }
        } }
        pageInfo { endCursor hasNextPage }
    }
}
"""

_MONGO_DATABASE_REFRESH = """
query($first: Int!, $after: String, $filter: [Filter!]) {
    mongoDatabases(first: $first, after: $after, filter: $filter) {
        count
        edges { node {
            id name isRelic slaPauseStatus
            cluster { id name }
            configuredSlaDomain { id name }
            effectiveSlaDomain { id name }
            effectiveSlaSourceObject { fid name objectType }
            physicalPath { fid name objectType }
            logicalPath { fid name objectType }
        } }
        pageInfo { endCursor hasNextPage }
    }
}
"""

_MONGO_COLLECTION_REFRESH = """
query($first: Int!, $after: String, $filter: [Filter!]) {
    mongoCollections(first: $first, after: $after, filter: $filter) {
        count
        edges { node {
            id name isRelic slaPauseStatus
            cluster { id name }
            configuredSlaDomain { id name }
            effectiveSlaDomain { id name }
            effectiveSlaSourceObject { fid name objectType }
            physicalPath { fid name objectType }
            logicalPath { fid name objectType }
            newestSnapshot { id date }
            oldestSnapshot { id date }
        } }
        pageInfo { endCursor hasNextPage }
    }
}
"""

# PostgreSQL Databases and MySQL Databases are child objects — they don't appear
# directly in the activity feed (activity is at the cluster/instance level).
# Refresh queries are included for completeness but will rarely be triggered.
_POSTGRES_DB_REFRESH = """
query($first: Int!, $after: String, $filter: [Filter!]) {
    postgreSQLDatabases(first: $first, after: $after, filter: $filter) {
        count
        edges { node {
            id name isRelic slaPauseStatus
            cluster { id name }
            configuredSlaDomain { id name }
            effectiveSlaDomain { id name }
            effectiveSlaSourceObject { fid name objectType }
            physicalPath { fid name objectType }
            logicalPath { fid name objectType }
        } }
        pageInfo { endCursor hasNextPage }
    }
}
"""

_MYSQL_DB_REFRESH = """
query($first: Int!, $after: String, $filter: [Filter!]) {
    mysqlDatabases(first: $first, after: $after, filter: $filter) {
        count
        edges { node {
            id name isRelic slaPauseStatus
            cluster { id name }
            configuredSlaDomain { id name }
            effectiveSlaDomain { id name }
            effectiveSlaSourceObject { fid name objectType }
            physicalPath { fid name objectType }
            logicalPath { fid name objectType }
        } }
        pageInfo { endCursor hasNextPage }
    }
}
"""

# Map platform data_key → (query, data_key_in_response)
PLATFORM_REFRESH_QUERIES = {
    "mssqlDatabases":              (MSSQL_QUERY,              "mssqlDatabases"),
    "oracleDatabases":             (ORACLE_QUERY,             "oracleDatabases"),
    "sapHanaDatabases":            (SAP_HANA_QUERY,           "sapHanaDatabases"),
    "db2Databases":                (DB2_QUERY,                "db2Databases"),
    "exchangeDatabases":           (EXCHANGE_QUERY,           "exchangeDatabases"),
    "postgreSQLDbClusters":        (_POSTGRES_CLUSTER_REFRESH, "postgreSQLDbClusters"),
    "mysqlInstances":              (_MYSQL_INSTANCE_REFRESH,  "mysqlInstances"),
    "mongoSources":                (_MONGO_SOURCE_REFRESH,    "mongoSources"),
    "mongoDatabases":              (_MONGO_DATABASE_REFRESH,  "mongoDatabases"),
    "mongoCollections":            (_MONGO_COLLECTION_REFRESH, "mongoCollections"),
    # Child objects — activity appears at parent level, but included for completeness
    "postgreSQLDatabases":         (_POSTGRES_DB_REFRESH,     "postgreSQLDatabases"),
    "mysqlDatabases":              (_MYSQL_DB_REFRESH,         "mysqlDatabases"),
}

# Platform name lookup for display
PLATFORM_DISPLAY_NAME = {p["data_key"]: p["name"] for p in PLATFORMS}


# ── PATH C: Age re-evaluation ─────────────────────────────────────────────────

def _recalculate_age_status(row: dict) -> str:
    """
    Recalculate the age-based component of event_status using today's date.

    Only updates statuses that are purely age-driven ("Online", "Warning (Stale:…)",
    "Offline (Stale:…)"). Non-age statuses like Relic, SLA Paused, Offline (Unprotectable),
    and inherited statuses are left untouched — those are refreshed by PATH A
    when the underlying record actually changes.
    """
    existing = row.get("event_status", "Online")

    # Preserve statuses that aren't driven by snapshot age
    skip_prefixes = (
        "Relic",
        "Offline (Unprotectable)",
        "Offline (DB Offline)",
        "Offline (STOPPED",
        "Offline (SUSPENDED",
        "Offline (stopped",
        "Offline (failed",
        "Warning (SLA Paused)",
        "Online (Inherited",
        "Online (Via",
    )
    if any(existing.startswith(pfx) for pfx in skip_prefixes):
        return existing

    newest_snap = row.get("newest_snapshot", "")
    if not newest_snap:
        return existing

    try:
        snap_dt = datetime.fromisoformat(newest_snap.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        age_days = (now - snap_dt).days
        if age_days > OFFLINE_SNAPSHOT_DAYS:
            return f"Offline (Stale: {age_days}d)"
        elif age_days > STALE_SNAPSHOT_DAYS:
            return f"Warning (Stale: {age_days}d)"
        else:
            # Snapshot is fresh — return "Online" (normalise any stale labels)
            return "Online" if "Online" not in existing else existing
    except (ValueError, TypeError):
        return existing


def _apply_age_reeval(databases: list) -> tuple[list, int]:
    """Apply PATH C age re-evaluation to all records. Returns (databases, changes)."""
    changes = 0
    for row in databases:
        new_status = _recalculate_age_status(row)
        if new_status != row.get("event_status"):
            row["event_status"] = new_status
            changes += 1
    return databases, changes


# ── PATH A: Activity-based targeted re-fetch ──────────────────────────────────

_ACTIVITY_QUERY = """
query($filters: ActivitySeriesFilter, $first: Int!, $after: String) {
    activitySeriesConnection(filters: $filters, first: $first, after: $after) {
        count
        pageInfo { endCursor hasNextPage }
        nodes { fid objectType }
    }
}
"""


def _fetch_activity_fids(token_manager: TokenManager,
                         since_timestamp: str,
                         max_pages: int = 50) -> dict[str, set]:
    """
    Paginate activitySeriesConnection since since_timestamp.
    Returns a dict: {platform_data_key: set(fid, …)} for DB-type objects.

    objectType filter is broken server-side (all 400s) so we paginate all
    events and filter client-side. Max pages caps runaway scenarios.
    """
    fids_by_platform: dict[str, set] = {}
    cursor = None
    total_scanned = 0
    db_types_seen = set()

    for page in range(max_pages):
        data = execute_graphql(
            token_manager,
            _ACTIVITY_QUERY,
            {
                "first": 200,
                "after": cursor,
                "filters": {"lastUpdatedTimeGt": since_timestamp},
            },
        )
        conn = data.get("activitySeriesConnection", {})
        nodes = conn.get("nodes", []) or []
        total_scanned += len(nodes)

        for node in nodes:
            obj_type = node.get("objectType", "")
            fid = node.get("fid", "")
            if not obj_type or not fid:
                continue

            platform_key = ACTIVITY_TYPE_TO_PLATFORM.get(obj_type)
            if not platform_key:
                continue  # not a DB type

            db_types_seen.add(obj_type)
            if platform_key in FILTERABLE_PLATFORMS:
                fids_by_platform.setdefault(platform_key, set()).add(fid)
            else:
                # Cloud-native — noted but not targeted
                fids_by_platform.setdefault(f"_cloud:{platform_key}", set()).add(fid)

        pi = conn.get("pageInfo", {})
        if not pi.get("hasNextPage"):
            total_count = conn.get("count", total_scanned)
            logger.info(
                "Activity scan complete: %d events scanned (total=%s, pages=%d)",
                total_scanned, total_count, page + 1,
            )
            break
        cursor = pi.get("endCursor")

    return fids_by_platform


def _targeted_refetch(token_manager: TokenManager,
                      platform_key: str,
                      fids: set,
                      batch_size: int = 200) -> list:
    """
    Re-fetch specific records from a platform using OBJECT_ID filter.
    Returns a list of parsed records with _platform set.
    """
    query, response_key = PLATFORM_REFRESH_QUERIES.get(
        platform_key, (None, platform_key))
    if query is None:
        logger.warning("No refresh query for platform %s — skipping", platform_key)
        return []

    # Find the platform name for _platform tag
    platform_name = PLATFORM_DISPLAY_NAME.get(platform_key, platform_key)

    all_records = []
    fid_list = list(fids)

    for i in range(0, len(fid_list), batch_size):
        batch = fid_list[i:i + batch_size]
        cursor = None

        while True:
            try:
                data = execute_graphql(
                    token_manager,
                    query,
                    {
                        "first": 500,
                        "after": cursor,
                        "filter": [{"field": "OBJECT_ID", "texts": batch}],
                    },
                )
            except RuntimeError as e:
                logger.warning(
                    "OBJECT_ID re-fetch failed for %s (batch %d-%d): %s",
                    platform_key, i, i + len(batch), str(e)[:120],
                )
                break

            conn = data.get(response_key, {})
            nodes = [e["node"] for e in conn.get("edges", [])]
            for node in nodes:
                node["_platform"] = platform_name
                try:
                    parsed = parse_node(node)
                    all_records.append(parsed)
                except Exception as exc:
                    logger.debug("Parse error in refresh: %s", exc)

            pi = conn.get("pageInfo", {})
            if not pi.get("hasNextPage"):
                break
            cursor = pi.get("endCursor")

    return all_records


def _merge_records(databases: list, updated: list) -> tuple[list, int, int]:
    """
    Merge updated records into the databases list.

    Returns (merged_list, updated_count, new_count).
    """
    db_by_id = {db["id"]: idx for idx, db in enumerate(databases)}
    updated_count = 0
    new_count = 0

    for record in updated:
        idx = db_by_id.get(record["id"])
        if idx is not None:
            databases[idx] = record
            updated_count += 1
        else:
            # New record — appeared since last full run
            databases.append(record)
            db_by_id[record["id"]] = len(databases) - 1
            new_count += 1

    return databases, updated_count, new_count


# ── Main entry point ──────────────────────────────────────────────────────────

def run_refresh(age_only: bool = False):
    """Execute the incremental refresh."""
    print("=" * 60)
    print("  🔄 Rubrik RSC — Database Status Refresh")
    print("  Incremental mode (PATH C + PATH A)")
    print("=" * 60)

    start_time = time.time()
    os.makedirs(INTERMEDIATE_DIR, exist_ok=True)

    # ── Load cache (required) ────────────────────────────────────────────────
    print("\n[*] Loading cache...")
    # Use a permissive TTL (10 × normal) so we never expire for refresh
    cached = load_cache(CACHE_FILE, CACHE_KEY_FILE, ttl_hours=CACHE_TTL_HOURS * 10)
    if not cached:
        print("""
  ❌  No valid cache found.

  The refresh command updates an existing dataset — it does not do a
  full API pull from scratch. Run a full pull first:

      python -m db_status run

  Then use 'refresh' for fast incremental updates.
""")
        return

    databases = cached["databases"]
    meta = cached.get("metadata", {})
    saved_at_str = meta.get("saved_at", "")
    profile_label = meta.get("profile", "cached")

    print(f"  ✅  Loaded {len(databases):,} databases "
          f"(saved: {saved_at_str[:19]}, profile: {profile_label})")

    # ── PATH C: Age re-evaluation ────────────────────────────────────────────
    print("\n[*] PATH C: Age re-evaluation (recalculating staleness thresholds)...")
    databases, age_changes = _apply_age_reeval(databases)
    print(f"    Status updated for {age_changes:,} records based on today's date")

    if age_only:
        print("\n[*] --age-only: skipping API activity query (PATH A)")
    else:
        # ── PATH A: Activity-based targeted re-fetch ─────────────────────────
        if not saved_at_str:
            print("\n[!] Cache has no saved_at timestamp — cannot determine activity "
                  "window. Skipping PATH A. Use --force-refresh for a full re-fetch.")
        else:
            print(f"\n[*] PATH A: Querying activity since {saved_at_str[:19]}...")
            token_manager = TokenManager(buffer_seconds=60)
            token_manager.get_token()
            set_rate_limit(10)

            # Paginate activity events
            try:
                fids_by_platform = _fetch_activity_fids(token_manager, saved_at_str)
            except Exception as e:
                print(f"  ❌  Activity query failed: {str(e)[:200]}")
                fids_by_platform = {}

            # Summarise what was found
            filterable_fids = {
                k: v for k, v in fids_by_platform.items()
                if not k.startswith("_cloud:")
            }
            cloud_fids = {
                k.replace("_cloud:", ""): v
                for k, v in fids_by_platform.items()
                if k.startswith("_cloud:")
            }

            total_filterable = sum(len(v) for v in filterable_fids.values())
            total_cloud = sum(len(v) for v in cloud_fids.values())

            print(f"\n  DB FIDs found in activity:")
            for pk, fids in sorted(filterable_fids.items(),
                                   key=lambda x: -len(x[1])):
                print(f"    {PLATFORM_DISPLAY_NAME.get(pk, pk):35s} "
                      f"{len(fids):4d} FIDs  → targeted re-fetch")
            for pk, fids in sorted(cloud_fids.items(),
                                   key=lambda x: -len(x[1])):
                print(f"    {PLATFORM_DISPLAY_NAME.get(pk, pk):35s} "
                      f"{len(fids):4d} FIDs  → skipped (no OBJECT_ID filter)")

            if not total_filterable and not total_cloud:
                print("    (none — no DB activity since last save)")

            # Targeted re-fetch for filterable platforms
            total_updated = 0
            total_new = 0

            if filterable_fids:
                print(f"\n[*] Re-fetching {total_filterable} records via "
                      f"OBJECT_ID filter ({len(filterable_fids)} platforms)...")

                for platform_key, fids in filterable_fids.items():
                    t0 = time.time()
                    refreshed = _targeted_refetch(token_manager, platform_key, fids)
                    elapsed = time.time() - t0

                    databases, upd, new = _merge_records(databases, refreshed)
                    total_updated += upd
                    total_new += new
                    pname = PLATFORM_DISPLAY_NAME.get(platform_key, platform_key)
                    print(f"    {pname:35s} "
                          f"queried={len(fids):4d}  "
                          f"returned={len(refreshed):4d}  "
                          f"updated={upd}  new={new}  "
                          f"({elapsed:.1f}s)")

            if cloud_fids:
                print(f"\n  ℹ️  {total_cloud} cloud-native DB FIDs detected but not "
                      "targeted (Azure/GCP/AWS don't support OBJECT_ID filter).\n"
                      "     Run 'python -m db_status run --force-refresh' to "
                      "update those platforms fully.")

            print(f"\n  ✅  Merge complete: "
                  f"{total_updated} updated, {total_new} new records")

    # ── Save updated cache ───────────────────────────────────────────────────
    print("\n[*] Saving updated cache...")
    saved = save_cache(
        databases,
        {"profile": profile_label},
        CACHE_FILE,
        CACHE_KEY_FILE,
    )
    if saved:
        print(f"    ✅  Cache saved ({len(databases):,} records)")
    else:
        print("    ⚠️  Cache not saved (cryptography not installed or write error)")

    # ── Phase 4: Event checks (MSSQL only, on updated records) ───────────────
    profile_event_checks = "small" not in profile_label.lower()
    if not age_only and ENABLE_MSSQL_EVENT_CHECKS and profile_event_checks:
        print("\n[*] Phase 4: MSSQL event checks (changed records only)...")
        mssql_ids = [
            db["id"] for db in databases
            if "MSSQL" in db.get("platform", "") and not db.get("is_relic")
        ]
        if mssql_ids:
            _profile = next(
                (p for p in SCALE_PROFILES.values()
                 if p["label"] == profile_label),
                SCALE_PROFILES["xxlarge"],
            )
            try:
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
            except Exception as e:
                print(f"    ⚠️  Event checks failed: {str(e)[:120]}")
        else:
            print("    No active MSSQL databases.")
    else:
        reason = ("--age-only" if age_only
                  else ("disabled for scale" if not profile_event_checks
                        else "globally disabled"))
        print(f"\n[*] Phase 4: Event checks {reason}.")

    # ── Phase 5: Reports ─────────────────────────────────────────────────────
    print("\n[*] Phase 5: Generating reports...")
    total_time = time.time() - start_time

    if age_only:
        # Minimal token stats for age-only run
        class _FakeStats:
            def get_stats(self):
                return {"refresh_count": 0}
        token_stats = _FakeStats().get_stats()
    else:
        token_stats = token_manager.get_stats()

    print_console_report(databases, token_stats, total_time)
    write_csv_report(databases, OUTPUT_CSV)
    write_json_report(databases, OUTPUT_JSON)
    write_html_report(databases, OUTPUT_HTML)

    print(f"\n{'=' * 60}")
    print(f"  ✅ REFRESH COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Total databases: {len(databases):,}")
    print(f"  Total time: {total_time:.1f}s")
    mode = "age-only" if age_only else "activity + age"
    print(f"  Refresh mode: {mode}")
    print(f"  Output:")
    print(f"    📄 {OUTPUT_CSV}")
    print(f"    📋 {OUTPUT_JSON}")
    print(f"    🌐 {OUTPUT_HTML}")
    print(f"{'=' * 60}")
