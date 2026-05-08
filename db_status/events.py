"""
Batched per-database event checks (MSSQL missed snapshots/ranges).
Parallel execution with progress reporting.
"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from .auth import TokenManager
from .graphql_client import execute_graphql


def fetch_missed_snapshots(token_manager: TokenManager, db_id: str) -> int:
    """Fetch missed snapshot count for a single MSSQL database."""
    query = """
    query($id: String!) {
        mssqlDatabase(fid: $id) {
            missedSnapshotConnection {
                nodes { missedSnapshotTime }
            }
        }
    }
    """
    data = execute_graphql(token_manager, query, {"id": db_id})
    db_data = data.get("mssqlDatabase", {}) or {}
    conn = db_data.get("missedSnapshotConnection", {}) or {}
    nodes = conn.get("nodes", []) or []
    return len(nodes)


def fetch_missed_ranges(token_manager: TokenManager, db_id: str) -> int:
    """Fetch missed recoverable range count for a single MSSQL database."""
    query = """
    query($id: String!) {
        mssqlDatabase(fid: $id) {
            missedRecoverableRangeConnection {
                nodes { missedRecoverableRangeTime }
            }
        }
    }
    """
    data = execute_graphql(token_manager, query, {"id": db_id})
    db_data = data.get("mssqlDatabase", {}) or {}
    conn = db_data.get("missedRecoverableRangeConnection", {}) or {}
    nodes = conn.get("nodes", []) or []
    return len(nodes)


def check_single_db_events(token_manager: TokenManager, db_id: str) -> dict:
    """Check events for a single database."""
    missed_snaps = fetch_missed_snapshots(token_manager, db_id)
    missed_ranges = fetch_missed_ranges(token_manager, db_id)

    if missed_snaps > 5 or missed_ranges > 5:
        event_status = "Likely Offline (Many Misses)"
    elif missed_snaps > 0 or missed_ranges > 0:
        event_status = "Warning (Some Misses)"
    else:
        event_status = "Healthy (No Misses)"

    return {
        "total_missed_snapshots": missed_snaps,
        "total_missed_ranges": missed_ranges,
        "event_status": event_status,
    }


def batched_event_check(token_manager: TokenManager, db_ids: list,
                         profile: dict) -> dict:
    """Process per-DB event checks in batches with parallelism."""
    batch_size = profile["batch_size"]
    max_workers = profile["max_workers"]
    results = {}
    total = len(db_ids)

    if total == 0:
        return results

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
                        "total_missed_snapshots": -1,
                        "total_missed_ranges": -1,
                        "event_status": f"Error: {str(e)[:80]}",
                    }
                    errors += 1
                checked += 1

        elapsed = time.time() - start_time
        rate = checked / elapsed if elapsed > 0 else 0
        eta = (total - checked) / rate if rate > 0 else 0
        print(f"    Batch {batch_idx + 1}/{len(batches)} | "
              f"{checked}/{total} | {errors} errors | "
              f"{rate:.1f}/s | ETA: {eta:.0f}s")

        if batch_idx < len(batches) - 1:
            time.sleep(0.5)

    print(f"  ✅ Event checks complete: {checked} checked, {errors} errors")
    return results
