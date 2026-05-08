"""
Batched per-database event checks (MSSQL missed snapshots/ranges).
Parallel execution with progress reporting.
Corrected query formats based on RSC schema introspection.
"""
import time
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from .auth import TokenManager
from .graphql_client import execute_graphql
from .config import MISSED_SNAPSHOT_LOOKBACK_HOURS


# ============================================================
# CONFIRMED WORKING QUERIES
# ============================================================

# Missed Snapshots — confirmed working with {id, beforeTime, afterTime}
MSSQL_MISSED_SNAPSHOTS_QUERY = """
query MssqlMissedSnapshots($input: GetMissedMssqlDbSnapshotsInput!) {
    mssqlDatabaseMissedSnapshots(input: $input) {
        data {
            missedSnapshotTime
        }
        hasMore
        total
    }
}
"""

# Missed Recoverable Ranges — uses beginTime/endTime (NOT missedRangeStart/missedRangeEnd)
MSSQL_MISSED_RANGES_QUERY = """
query MssqlMissedRanges($input: GetMssqlDbMissedRecoverableRangesInput!) {
    mssqlDatabaseMissedRecoverableRanges(input: $input) {
        data {
            beginTime
            endTime
        }
        hasMore
        total
    }
}
"""


# ============================================================
# FETCH FUNCTIONS
# ============================================================

def fetch_missed_snapshots(token_manager: TokenManager, db_id: str) -> dict:
    """
    Fetch missed snapshot count for a single MSSQL database.
    Input: GetMissedMssqlDbSnapshotsInput with fields:
      - id: String! (NON_NULL)
      - afterTime: DateTime (optional)
      - beforeTime: DateTime (optional)
    """
    now = datetime.now(timezone.utc)
    before = now.isoformat()
    after = (now - timedelta(hours=MISSED_SNAPSHOT_LOOKBACK_HOURS)).isoformat()

    variables = {
        "input": {
            "id": db_id,
            "beforeTime": before,
            "afterTime": after,
        }
    }

    try:
        data = execute_graphql(token_manager, MSSQL_MISSED_SNAPSHOTS_QUERY, variables)
        result = data.get("mssqlDatabaseMissedSnapshots", {}) or {}
        total = result.get("total", 0) or 0
        missed_data = result.get("data", []) or []

        latest_miss = ""
        if missed_data:
            times = [m.get("missedSnapshotTime", "") for m in missed_data
                     if m.get("missedSnapshotTime")]
            if times:
                latest_miss = max(times)

        return {"total_missed": total, "latest_miss_time": latest_miss}
    except Exception as e:
        return {"total_missed": -1, "latest_miss_time": "", "error": str(e)[:100]}


def fetch_missed_ranges(token_manager: TokenManager, db_id: str) -> dict:
    """
    Fetch missed recoverable range count for a single MSSQL database.
    Input: GetMssqlDbMissedRecoverableRangesInput with fields:
      - id: String! (NON_NULL)
      - afterTime: DateTime (optional)
      - beforeTime: DateTime (optional)
    Response data fields: beginTime, endTime (NOT missedRangeStart/missedRangeEnd)
    """
    now = datetime.now(timezone.utc)
    before = now.isoformat()
    after = (now - timedelta(hours=MISSED_SNAPSHOT_LOOKBACK_HOURS)).isoformat()

    variables = {
        "input": {
            "id": db_id,
            "beforeTime": before,
            "afterTime": after,
        }
    }

    try:
        data = execute_graphql(token_manager, MSSQL_MISSED_RANGES_QUERY, variables)
        result = data.get("mssqlDatabaseMissedRecoverableRanges", {}) or {}
        total = result.get("total", 0) or 0
        return {"total_missed_ranges": total}
    except Exception as e:
        return {"total_missed_ranges": -1, "error": str(e)[:100]}


# ============================================================
# PER-DB CHECK
# ============================================================

def check_single_db_events(token_manager: TokenManager, db_id: str) -> dict:
    """Check events for a single database."""
    snap_result = fetch_missed_snapshots(token_manager, db_id)
    range_result = fetch_missed_ranges(token_manager, db_id)

    missed_snaps = snap_result.get("total_missed", 0)
    missed_ranges = range_result.get("total_missed_ranges", 0)
    latest_miss = snap_result.get("latest_miss_time", "")

    # Handle errors gracefully
    if missed_snaps == -1:
        missed_snaps = 0
    if missed_ranges == -1:
        missed_ranges = 0

    # Determine status
    if missed_snaps > 5 or missed_ranges > 5:
        event_status = "Likely Offline (Many Misses)"
    elif missed_snaps > 0 or missed_ranges > 0:
        event_status = "Warning (Some Misses)"
    else:
        event_status = "Healthy (No Misses)"

    return {
        "total_missed_snapshots": missed_snaps,
        "total_missed_ranges": missed_ranges,
        "latest_miss_time": latest_miss,
        "event_status": event_status,
    }


# ============================================================
# QUERY VALIDATION — Test before bulk execution
# ============================================================

def validate_event_queries(token_manager: TokenManager, test_db_id: str) -> dict:
    """
    Test both event queries against a single DB to confirm they work.
    Returns dict with status of each query.
    """
    print(f"    [Events] Validating queries with DB: {test_db_id[:20]}...")

    results = {
        "snapshots_work": False,
        "ranges_work": False,
    }

    # Test snapshots
    snap_result = fetch_missed_snapshots(token_manager, test_db_id)
    if snap_result.get("total_missed", -1) != -1:
        results["snapshots_work"] = True
        print(f"    [Events] ✅ Missed snapshots query works "
              f"(test DB has {snap_result['total_missed']} missed)")
    else:
        print(f"    [Events] ❌ Missed snapshots query failed: "
              f"{snap_result.get('error', 'unknown')}")

    # Test ranges
    range_result = fetch_missed_ranges(token_manager, test_db_id)
    if range_result.get("total_missed_ranges", -1) != -1:
        results["ranges_work"] = True
        print(f"    [Events] ✅ Missed ranges query works "
              f"(test DB has {range_result['total_missed_ranges']} missed)")
    else:
        print(f"    [Events] ❌ Missed ranges query failed: "
              f"{range_result.get('error', 'unknown')}")

    return results


# ============================================================
# BATCHED EXECUTION
# ============================================================

def batched_event_check(token_manager: TokenManager, db_ids: list,
                         profile: dict) -> dict:
    """Process per-DB event checks in batches with parallelism."""
    batch_size = profile["batch_size"]
    max_workers = profile["max_workers"]
    results = {}
    total = len(db_ids)

    if total == 0:
        return results

    # Step 1: Validate queries work
    test_id = db_ids[0]
    validation = validate_event_queries(token_manager, test_id)

    if not validation["snapshots_work"] and not validation["ranges_work"]:
        print(f"    [Events] ⚠️ Neither event query works. "
              f"Skipping all event checks.")
        for db_id in db_ids:
            results[db_id] = {
                "total_missed_snapshots": 0,
                "total_missed_ranges": 0,
                "latest_miss_time": "",
                "event_status": "Events Not Available",
            }
        return results

    # Step 2: Process in batches
    batches = [db_ids[i:i + batch_size] for i in range(0, total, batch_size)]
    print(f"\n  📦 Processing {total} DBs in {len(batches)} batches "
          f"(batch_size={batch_size}, workers={max_workers})")

    checked = 0
    errors = 0
    start_time = time.time()

    for batch_idx, batch in enumerate(batches):
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(check_single_db_events, token_manager, db_id): db_id
                for db_id in batch
            }
            for future in as_completed(futures):
                db_id = futures[future]
                try:
                    results[db_id] = future.result()
                except Exception as e:
                    results[db_id] = {
                        "total_missed_snapshots": 0,
                        "total_missed_ranges": 0,
                        "latest_miss_time": "",
                        "event_status": f"Error: {str(e)[:80]}",
                    }
                    errors += 1
                checked += 1

        # Progress reporting
        elapsed = time.time() - start_time
        rate = checked / elapsed if elapsed > 0 else 0
        eta = (total - checked) / rate if rate > 0 else 0
        print(f"    Batch {batch_idx + 1}/{len(batches)} | "
              f"{checked}/{total} | {errors} errors | "
              f"{rate:.1f}/s | ETA: {eta:.0f}s")

        # Backpressure between batches
        if batch_idx < len(batches) - 1:
            time.sleep(0.5)

    print(f"  ✅ Event checks complete: {checked} checked, {errors} errors")
    return results