"""Phase 4 only: Run MSSQL event checks from intermediate file."""
import json
from ..config import (
    INTERMEDIATE_FILE, EVENTS_FILE, get_scale_profile,
    ENABLE_MSSQL_EVENT_CHECKS
)
from ..auth import TokenManager
from ..graphql_client import set_rate_limit
from ..events import batched_event_check


def run_events(intermediate_file: str = None):
    """Load intermediate, run event checks, update file."""
    if intermediate_file is None:
        intermediate_file = INTERMEDIATE_FILE

    if not ENABLE_MSSQL_EVENT_CHECKS:
        print("[*] Event checks globally disabled.")
        return

    token_manager = TokenManager(buffer_seconds=60)
    token_manager.get_token()

    with open(intermediate_file, "r") as f:
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

    # Merge back
    for db in databases:
        if db["id"] in event_results:
            ev = event_results[db["id"]]
            db["total_missed_snapshots"] = ev.get("total_missed_snapshots", 0)
            db["total_missed_ranges"] = ev.get("total_missed_ranges", 0)
            db["event_status"] = ev.get("event_status", "Error")

    # Overwrite intermediate
    with open(intermediate_file, "w") as f:
        json.dump(data, f, indent=2, default=str)

    with open(EVENTS_FILE, "w") as f:
        json.dump(event_results, f, indent=2, default=str)

    print(f"[+] Events merged and saved.")
