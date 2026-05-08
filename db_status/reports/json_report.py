"""JSON report generation.

SECURITY F-05: output file created with 0o600 permissions so only the
running user can read the exported database metadata.
"""
import json
import os
from datetime import datetime
from ..config import (
    RSC_DOMAIN, STALE_SNAPSHOT_DAYS, OFFLINE_SNAPSHOT_DAYS,
    ENABLE_MSSQL_EVENT_CHECKS, MISSED_SNAPSHOT_LOOKBACK_HOURS
)


def write_json_report(databases: list, filename: str):
    """Write JSON report with metadata and restricted file permissions."""
    report = {
        "report_title": "Rubrik RSC - Database Status Report",
        "generated_at": datetime.now().isoformat(),
        "rsc_domain": RSC_DOMAIN,
        "settings": {
            "stale_snapshot_days": STALE_SNAPSHOT_DAYS,
            "offline_snapshot_days": OFFLINE_SNAPSHOT_DAYS,
            "mssql_event_checks_enabled": ENABLE_MSSQL_EVENT_CHECKS,
            "missed_snapshot_lookback_hours": MISSED_SNAPSHOT_LOOKBACK_HOURS,
        },
        "total_databases": len(databases),
        "databases": databases,
    }
    # SECURITY F-05: O_CREAT with mode 0o600 — file is owner-read/write only
    fd = os.open(filename, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"[+] JSON report saved: {filename} (permissions: 600)")