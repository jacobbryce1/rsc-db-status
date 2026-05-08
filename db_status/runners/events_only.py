"""Phase 4 only: Run MSSQL event checks from intermediate file.

SECURITY F-02: intermediate file path validated via safe_input_path().
SECURITY F-05: updated intermediate file written with secure_open_write().
"""
import json
from ..config import (
    INTERMEDIATE_FILE, INTERMEDIATE_DIR, EVENTS_FILE,
    get_scale_profile, ENABLE_MSSQL_EVENT_CHECKS
)
from ..auth import TokenManager
from ..graphql_client import set_rate_limit
from ..events import batched_event_check
from ..security import safe_input_path, secure_open_write


def run_events(intermediate_file: str = None):
    """Load intermediate, run event checks, update file."""
    if intermediate_file is None:
        intermediate_file = INTERMEDIATE_FILE

    # SECURITY F-02: validate the path is inside the work directory
    try:
        intermediate_file = safe_input_path(intermediate_file, INTERMEDIATE_DIR)
    except (ValueError, FileNotFoundError) as e:
        print(f"[!] {e}")
        return

    if not ENABLE_MSSQL_EVENT_CHECKS:
        print("[*] Event checks globally disabled.")
        return

    token_manager = TokenManager(buffer_seconds=60)
    token_manager.get_token()

    with open(intermediate_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    databases = data["databases"]
    profile = get_scale_profile(len(databases))
    set_rate_limit(profile["rate_limit"])

    mssql_ids = [
        db["id"] for db in databases
        if "MSSQL" in db.get("platform", "") and not db.get("is_relic")
    ]

    if not mssql_ids:
        print("[*] No MSSQL databases found.")
        return

    print(f"[*] Checking {len(mssql_ids)} MSSQL databases...")
    event_results = batched_event_check(token_manager, mssql_ids, profile)

    # Merge results back into the database list
    for db in databases:
        if db["id"] in event_results:
            ev = event_results[db["id"]]
            db["total_missed_snapshots"] = ev.get("total_missed_snapshots", 0)
            db["total_missed_ranges"]    = ev.get("total_missed_ranges", 0)
            db["event_status"]           = ev.get("event_status", "Error")

    # SECURITY F-05: write with restricted permissions (0o600)
    with secure_open_write(intermediate_file) as f:
        json.dump(data, f, indent=2, default=str)

    with secure_open_write(EVENTS_FILE) as f:
        json.dump(event_results, f, indent=2, default=str)

    print("[+] Events merged and saved.")