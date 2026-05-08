"""CSV report generation.

SECURITY F-05: output file created with 0o600 permissions so only the
running user can read the exported database metadata.
"""
import csv
import os

CSV_FIELDS = [
    "id", "name", "platform", "sla_name", "cluster_name",
    "is_relic", "recovery_model", "unprotected_reason",
    "newest_snapshot", "oldest_snapshot", "sla_pause_status",
    "total_missed_snapshots", "total_missed_ranges", "event_status",
    "db_engine", "region", "instance_class", "service_tier",
    "native_name", "cloud_state",
]


def write_csv_report(databases: list, filename: str):
    """Write CSV report with restricted file permissions."""
    # SECURITY F-05: O_CREAT with mode 0o600 — file is owner-read/write only
    fd = os.open(filename, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for db in databases:
            writer.writerow(db)
    print(f"[+] CSV report saved: {filename} ({len(databases)} rows, permissions: 600)")